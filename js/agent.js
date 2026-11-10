// agent.js: Orchestrator agent: filter, retrieve, check, early stopping, budget, trace (Tool 1 filter is here)
'use strict';

function inState(t, f) { return !f.state || t.locations.some(l => l[1] === f.state); }
function ageOk(t, f) { return f.age == null || ((t.minAge == null || f.age >= t.minAge) && (t.maxAge == null || f.age <= t.maxAge)); }
function sexOk(t, f) { return !f.sex || t.sex === 'All' || t.sex === f.sex; }

function runAgent(summary, trials, opts, overrides) {
  const trace = [], log = (thought, action, obs) => trace.push({ thought, action, obs });
  const cost = { t1: 0, t2: 0, rule: 0, spent: 0, skipped: 0, fixed: 0 };
  const f = extractFacts(summary, overrides);
  log('I need the patient’s key facts before searching.', 'extract_facts(patient_summary)',
      `age ${f.age ?? '?'}, ${f.sex ?? 'sex ?'}, ${f.city ? f.city + ', ' + f.state : 'location ?'}; conditions: ${Object.keys(f.concepts).filter(k => f.concepts[k]).join(', ') || 'none found'}; labs: ${Object.entries(f.labs).map(([k, v]) => LABS[k].name.split(' (')[0] + ' ' + v).join(', ') || 'none'}`);
  const questions = new Map();
  if (f.age == null) questions.set('age', { key: 'age', kind: 'age', q: 'What is the patient\u2019s age?', trials: ['all'] });

  const s1 = trials.filter(t => t.status === 'Recruiting');
  const s2 = s1.filter(t => ageOk(t, f) && sexOk(t, f));
  const s3 = s2.filter(t => inState(t, f));
  log('Remove trials the patient cannot join before spending any model calls.', `trial_filter(status="Recruiting", age=${f.age ?? '?'}, sex=${f.sex ?? '?'}, state=${f.state ?? 'any'})`,
      `${trials.length} trials → ${s1.length} recruiting → ${s2.length} fit age and sex → ${s3.length} near ${f.state ?? 'any location'}`);
  const funnel = [trials.length, s1.length, s2.length, s3.length];

  const docs = s3.map(docText);
  const bm = minmax(bm25Scores(summary, docs)), cs = minmax(tfidfCos(summary, docs));
  const ranked = s3.map((t, i) => ({ t, bm: bm[i], cs: cs[i], fused: opts.alpha * bm[i] + (1 - opts.alpha) * cs[i] }))
                   .sort((a, b) => b.fused - a.fused).slice(0, opts.topk);
  log('Rank the remaining trials by keyword and meaning similarity.', `hybrid_retrieve(top_k=${opts.topk}, alpha=${opts.alpha})`,
      ranked.map(r => `${r.t.id} ${r.fused.toFixed(2)}`).join('  '));

  for (const r of ranked) {
    const t = r.t, rows = [];
    const crits = [...t.inclusion.map(c => ({ c, ex: false })), ...t.exclusion.map(c => ({ c, ex: true }))];
    cost.fixed += crits.length * opts.p2;
    // structured criteria first (free rule checks), then concept criteria
    const order = crits.map(x => ({ ...x, rule: ruleCheck(x.c, f) })).sort((a, b) => (b.rule ? 1 : 0) - (a.rule ? 1 : 0));
    let stopped = null, notes = []; const localQ = new Map();
    for (const x of order) {
      if (stopped) { rows.push({ ...x, res: 'skip', ev: 'Skipped: trial already ruled out', tier: '—' }); cost.skipped++; continue; }
      let out, tier;
      if (x.rule) { out = x.rule; tier = 'rule'; cost.rule++; }
      else {
        out = tier1(x.c, f, x.ex); tier = 'low-cost'; cost.t1++; cost.spent += opts.p1;
        if (out.res === 'unsure') {
          if (cost.spent + opts.p2 <= opts.budget) { const o2 = tier2(x.c, f, x.ex); cost.t2++; cost.spent += opts.p2; out = o2; tier = 'escalated'; }
          else notes.push('budget reached, no escalation');
        }
      }
      if (out.res === 'unsure' && out.missing) localQ.set(out.missing.key, out.missing);
      else if (out.res === 'unsure' && !x.rule) localQ.set('crit:' + x.c, { key: 'crit:' + x.c, kind: 'crit', crit: x.c, ex: x.ex, q: (x.ex ? 'Exclusion: ' : 'Inclusion: ') + x.c + ' — does this apply?' });
      rows.push({ ...x, res: out.res, ev: out.ev, tier });
      const fails = (!x.ex && out.res === 'no') || (x.ex && out.res === 'yes');
      if (fails) stopped = x.c;
    }
    const unsure = rows.filter(z => z.res === 'unsure').length;
    if (!stopped) for (const [k, q] of localQ) { const g = questions.get(k) || { ...q, trials: [] }; g.trials.push(t.id); questions.set(k, g); }
    r.rows = rows; r.status = stopped ? 'bad' : unsure ? 'warn' : 'ok'; r.stoppedBy = stopped;
    const used = rows.filter(z => z.tier === 'low-cost' || z.tier === 'escalated');
    log(`Check ${t.id} criteria: rules first, then the low-cost model; escalate only unsure ones.`,
        `check_criteria(${t.id}) → ${rows.filter(z => z.tier === 'rule').length} rule, ${rows.filter(z => z.tier === 'low-cost').length} low-cost, ${rows.filter(z => z.tier === 'escalated').length} escalated`,
        stopped ? `Ruled out by “${stopped}”; stopped early and skipped ${rows.filter(z => z.res === 'skip').length} criteria` :
        unsure ? `${unsure} criteria still unsure → needs clinician review` : 'All criteria satisfied → likely eligible' + (notes.length ? ' (' + notes[0] + ')' : ''));
  }
  // clinician questions: only keep those not answered
  const qs = [...questions.values()].filter(q => !(q.kind === 'crit' && overrides.crits[q.crit] !== undefined));
  // apply clinician answers on free-text criteria
  for (const r of ranked) for (const row of r.rows) {
    if (row.res === 'unsure' && overrides.crits[row.c] !== undefined) {
      const applies = overrides.crits[row.c];
      row.res = row.ex ? (applies ? 'yes' : 'no') : (applies ? 'yes' : 'no'); row.ev = 'Clinician answer'; row.tier = 'clinician';
    }
  }
  for (const r of ranked) {
    const fail = r.rows.find(z => (!z.ex && z.res === 'no') || (z.ex && z.res === 'yes'));
    const unsure = r.rows.some(z => z.res === 'unsure');
    r.status = fail ? 'bad' : unsure ? 'warn' : 'ok';
  }
  const order = { ok: 0, warn: 1, bad: 2 };
  ranked.sort((a, b) => order[a.status] - order[b.status] || b.fused - a.fused);
  if (qs.length) log('Some facts are missing; ask the clinician instead of guessing.', 'ask_clinician(' + qs.length + ' questions)', qs.map(q => '• ' + q.q).join('\n'));
  const n = s => ranked.filter(r => r.status === s).length;
  const save = cost.fixed > 0 ? 1 - cost.spent / cost.fixed : 0;
  log('Stop: every candidate trial has been scored.', 'finish()',
      `${n('ok')} likely eligible, ${n('warn')} need review, ${n('bad')} not eligible. Estimated cost $${cost.spent.toFixed(4)} vs $${cost.fixed.toFixed(3)} if a strong model checked every criterion (${Math.round(save * 100)}% lower).`);
  return { f, funnel, ranked, trace, cost, qs, save };
}

async function fetchLive(f) {
  const cond = Object.keys(f.concepts).filter(k => f.concepts[k] && !['metformin', 'insulin', 'osimertinib', 'stage iv'].includes(k)).slice(0, 2).join(' ');
  const params = new URLSearchParams({ 'query.cond': cond || 'diabetes', 'filter.overallStatus': 'RECRUITING', pageSize: '25', format: 'json' });
  if (f.city) params.set('query.locn', `${f.city}, ${f.state}`);
  const res = await fetch('https://clinicaltrials.gov/api/v2/studies?' + params.toString());
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const data = await res.json();
  const yrs = s => { const m = (s || '').match(/(\d+)/); return m ? +m[1] : null; };
  return (data.studies || []).map(s => {
    const p = s.protocolSection || {}, el = p.eligibilityModule || {}, crit = el.eligibilityCriteria || '';
    const parts = crit.split(/exclusion criteria:?/i);
    const bullets = t => (t || '').replace(/inclusion criteria:?/i, '').split(/\n+/).map(x => x.replace(/^\s*[\*\-•\d.)]+\s*/, '').trim()).filter(x => x.length > 3).slice(0, 8);
    const statusMap = { RECRUITING: 'Recruiting', NOT_YET_RECRUITING: 'Not yet recruiting', COMPLETED: 'Completed' };
    return { id: (p.identificationModule || {}).nctId || 'NCT?', title: (p.identificationModule || {}).briefTitle || 'Untitled',
      status: statusMap[(p.statusModule || {}).overallStatus] || 'Other', sex: el.sex === 'FEMALE' ? 'Female' : el.sex === 'MALE' ? 'Male' : 'All',
      minAge: yrs(el.minimumAge), maxAge: yrs(el.maximumAge), conditions: (p.conditionsModule || {}).conditions || [],
      locations: ((p.contactsLocationsModule || {}).locations || []).map(l => [l.city || '', (l.state || '').length === 2 ? l.state : stateAbbr(l.state)]),
      summary: (p.descriptionModule || {}).briefSummary || '', inclusion: bullets(parts[0]), exclusion: bullets(parts[1]) };
  });
}
const STATES = { washington: 'WA', oregon: 'OR', california: 'CA', massachusetts: 'MA', 'new york': 'NY', texas: 'TX', idaho: 'ID' };
const stateAbbr = s => STATES[(s || '').toLowerCase()] || s || '';