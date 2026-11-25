"""The orchestrator agent: extract facts, filter, retrieve, check criteria with early stopping and a cost
budget, ask the clinician for missing facts, and keep a trace of every step (thought, action, observation)."""
from .facts import extract_facts
from .retrieval import hybrid_rank
from .checker import rule_check, tier1, tier2, fmt_num
from .knowledge import lab_short
from . import llm

DEFAULTS = {'top_k': 8, 'alpha': 0.6, 'budget': 0.50, 'price_low': 0.0005, 'price_strong': 0.02, 'use_llm': False}


def age_ok(t, f):
    return f.age is None or ((t['min_age'] is None or f.age >= t['min_age']) and (t['max_age'] is None or f.age <= t['max_age']))


def sex_ok(t, f):
    return not f.sex or t['sex'] == 'All' or t['sex'] == f.sex


def recruiting(t):
    return t.get('status') in ('Recruiting', None)  # None = status not reported (benchmark data): keep


def near(t, f):
    return not f.state or not t['locations'] or any(loc['state'] == f.state for loc in t['locations'])


def fails(row):
    return (not row['exclusion'] and row['result'] == 'no') or (row['exclusion'] and row['result'] == 'yes')


def run_agent(summary, trials, settings=None, answers=None):
    s = {**DEFAULTS, **(settings or {})}
    answers = answers or {}
    crit_answers = answers.get('criteria') or {}
    trace = []
    log = lambda thought, action, obs: trace.append({'thought': thought, 'action': action, 'observation': obs})
    cost = {'rule': 0, 'low_cost': 0, 'escalated': 0, 'skipped': 0, 'spent': 0.0, 'fixed': 0.0}
    checker1, checker2, mode = llm.checkers(s['use_llm'])

    f = extract_facts(summary, answers)
    conds = ', '.join(k for k, v in f.concepts.items() if v) or 'none found'
    labs = ', '.join(f'{lab_short(k)} {fmt_num(v)}' for k, v in f.labs.items()) or 'none'
    log('I need the patient’s key facts before searching.', 'extract_facts(patient_summary)',
        f"age {f.age if f.age is not None else '?'}, {f.sex or 'sex ?'}, {f'{f.city}, {f.state}' if f.city else 'location ?'}; conditions: {conds}; labs: {labs}")
    questions = {}
    if f.age is None:
        questions['age'] = {'key': 'age', 'kind': 'age', 'q': 'What is the patient’s age?', 'trials': ['all']}

    s1 = [t for t in trials if recruiting(t)]
    s2 = [t for t in s1 if age_ok(t, f) and sex_ok(t, f)]
    s3 = [t for t in s2 if near(t, f)]
    funnel = [len(trials), len(s1), len(s2), len(s3)]
    log('Remove trials the patient cannot join before spending any model calls.',
        f"trial_filter(status=\"Recruiting\", age={f.age if f.age is not None else '?'}, sex={f.sex or '?'}, state={f.state or 'any'})",
        f"{len(trials)} trials → {len(s1)} recruiting → {len(s2)} fit age and sex → {len(s3)} near {f.state or 'any location'}"
        + (f" ({unreported} trials do not report status or location and were kept)" if (unreported := sum(1 for t in trials if t.get('status') is None)) else ''))

    ranked = hybrid_rank(summary, s3, s['alpha'], int(s['top_k']))
    log('Rank the remaining trials by keyword and meaning similarity.', f"hybrid_retrieve(top_k={int(s['top_k'])}, alpha={s['alpha']})",
        '  '.join(f"{r['trial']['id']} {r['fused']:.2f}" for r in ranked))

    for r in ranked:
        t = r['trial']
        crits = [{'criterion': c, 'exclusion': False} for c in t['inclusion']] + [{'criterion': c, 'exclusion': True} for c in t['exclusion']]
        cost['fixed'] += len(crits) * s['price_strong']
        for x in crits:
            x['rule'] = rule_check(x['criterion'], f)
        order = sorted(crits, key=lambda x: 0 if x['rule'] else 1)  # free rule checks first (stable)
        rows, stopped, notes, local_q = [], None, [], {}
        for x in order:
            if stopped:
                rows.append({'criterion': x['criterion'], 'exclusion': x['exclusion'], 'result': 'skip', 'evidence': 'Skipped: trial already ruled out', 'tier': '—'})
                cost['skipped'] += 1
                continue
            if x['rule']:
                out, tier = x['rule'], 'rule'; cost['rule'] += 1
            else:
                out, tier = checker1(x['criterion'], f, x['exclusion']), 'low-cost'
                cost['low_cost'] += 1; cost['spent'] += s['price_low']
                if out['res'] == 'unsure':
                    if cost['spent'] + s['price_strong'] <= s['budget']:
                        out, tier = checker2(x['criterion'], f, x['exclusion']), 'escalated'
                        cost['escalated'] += 1; cost['spent'] += s['price_strong']
                    else:
                        notes.append('budget reached, no escalation')
            if out['res'] == 'unsure' and out.get('missing'):
                local_q[out['missing']['key']] = out['missing']
            elif out['res'] == 'unsure' and not x['rule']:
                local_q['crit:' + x['criterion']] = {'key': 'crit:' + x['criterion'], 'kind': 'criterion', 'criterion': x['criterion'],
                                                     'q': ('Exclusion: ' if x['exclusion'] else 'Inclusion: ') + x['criterion'] + ' — does this apply?'}
            row = {'criterion': x['criterion'], 'exclusion': x['exclusion'], 'result': out['res'], 'evidence': out['ev'], 'tier': tier}
            rows.append(row)
            if fails(row):
                stopped = x['criterion']
        unsure = sum(1 for z in rows if z['result'] == 'unsure')
        if not stopped:
            for k, q in local_q.items():
                g = questions.get(k) or {**q, 'trials': []}
                g['trials'].append(t['id']); questions[k] = g
        r['rows'], r['stopped_by'] = rows, stopped
        log(f"Check {t['id']} criteria: rules first, then the low-cost model; escalate only unsure ones.",
            f"check_criteria({t['id']}) → {sum(z['tier'] == 'rule' for z in rows)} rule, {sum(z['tier'] == 'low-cost' for z in rows)} low-cost, {sum(z['tier'] == 'escalated' for z in rows)} escalated",
            f"Ruled out by “{stopped}”; stopped early and skipped {sum(z['result'] == 'skip' for z in rows)} criteria" if stopped else
            (f'{unsure} criteria still unsure → needs clinician review' if unsure else 'All criteria satisfied → likely eligible' + (f' ({notes[0]})' if notes else '')))

    qs = [q for q in questions.values() if not (q['kind'] == 'criterion' and q['criterion'] in crit_answers)]
    for r in ranked:
        for row in r['rows']:
            if row['result'] == 'unsure' and row['criterion'] in crit_answers:
                row['result'] = 'yes' if crit_answers[row['criterion']] else 'no'
                row['evidence'], row['tier'] = 'Clinician answer', 'clinician'
    for r in ranked:
        r['status'] = 'not_eligible' if any(fails(z) for z in r['rows']) else ('needs_review' if any(z['result'] == 'unsure' for z in r['rows']) else 'likely_eligible')
    rank_order = {'likely_eligible': 0, 'needs_review': 1, 'not_eligible': 2}
    ranked.sort(key=lambda r: (rank_order[r['status']], -r['fused']))
    if qs:
        log('Some facts are missing; ask the clinician instead of guessing.', f'ask_clinician({len(qs)} questions)', '\n'.join('• ' + q['q'] for q in qs))
    counts = {k: sum(r['status'] == k for r in ranked) for k in rank_order}
    saving = 1 - cost['spent'] / cost['fixed'] if cost['fixed'] > 0 else 0.0
    log('Stop: every candidate trial has been scored.', 'finish()',
        f"{counts['likely_eligible']} likely eligible, {counts['needs_review']} need review, {counts['not_eligible']} not eligible. "
        f"Estimated cost ${cost['spent']:.4f} vs ${cost['fixed']:.3f} if a strong model checked every criterion ({round(saving * 100)}% lower).")
    return {
        'facts': f.to_dict(), 'funnel': funnel, 'counts': counts, 'mode': mode,
        'cost': {**cost, 'spent': round(cost['spent'], 4), 'fixed': round(cost['fixed'], 4), 'saving': round(saving, 4)},
        'trials': [{'id': r['trial']['id'], 'title': r['trial']['title'], 'locations': r['trial']['locations'],
                    'bm25': round(r['bm25'], 3), 'vector': round(r['vector'], 3), 'match': round(r['fused'], 3),
                    'status': r['status'], 'stopped_by': r['stopped_by'], 'criteria': r['rows']} for r in ranked],
        'questions': qs, 'trace': trace, 'settings': s,
    }
