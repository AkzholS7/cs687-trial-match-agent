"""Tools 3-5: free rule checks, tier 1 (low-cost) check, tier 2 escalation, and clinician questions.

In this version a rule-based checker stands in for the low-cost and strong LLMs (see llm.py for the
optional model hook). Each check returns a dict: {'res': 'yes'|'no'|'unsure', 'ev': evidence, 'missing': question}.
For inclusion criteria 'yes' means met; for exclusion criteria 'yes' means the exclusion applies.
"""
import math
import re

from .knowledge import VOCAB, LABS, ROMAN, DIAGNOSES, MEDS, lab_name, lab_short

INF = math.inf
_NUM = r'(\d+(?:\.\d+)?)'


def fmt_num(x):
    """Print numbers the way a person writes them: 7, 10.5, 0.3."""
    x = round(float(x), 2)
    return str(int(x)) if x == int(x) else str(x)


def parse_range(c):
    m = re.search(r'between\s*' + _NUM + r'%?\s*(?:and|to)\s*' + _NUM, c)
    if m: return float(m.group(1)), float(m.group(2))
    m = re.search(_NUM + r'\s*%?\s*(?:to|-|–|or)\s*' + _NUM, c)
    if m: return float(m.group(1)), float(m.group(2))
    m = re.search(r'(?:≥|>=|at least|greater than or equal to|minimum of)\s*' + _NUM, c)
    if m: return float(m.group(1)), INF
    m = re.search(_NUM + r'\s*%?\s*(?:or more|or greater|or higher|and above)', c)
    if m: return float(m.group(1)), INF
    m = re.search(r'(?:≤|<=|at most|less than or equal to|up to|no more than)\s*' + _NUM, c)
    if m: return -INF, float(m.group(1))
    m = re.search(_NUM + r'\s*%?\s*(?:or less|or lower|or below)', c)
    if m: return -INF, float(m.group(1))
    m = re.search(r'(?:greater than|more than|above|>)\s*' + _NUM, c)
    if m: return float(m.group(1)) + 1e-9, INF
    m = re.search(r'(?:less than|below|under|<)\s*' + _NUM, c)
    if m: return -INF, float(m.group(1)) - 1e-9
    return None


def fmt_range(r):
    if r[0] == -INF: return '≤ ' + fmt_num(r[1])
    if r[1] == INF: return '≥ ' + fmt_num(r[0])
    return fmt_num(r[0]) + '–' + fmt_num(r[1])


def lab_key(c):
    if re.search(r'hba1c|a1c', c): return 'hba1c'
    if re.search(r'ejection fraction|lvef', c) and re.search(r'\d', c): return 'ef'
    if re.search(r'\bbmi\b|body mass index', c): return 'bmi'
    if 'ecog' in c: return 'ecog'
    if 'potassium' in c: return 'potassium'
    if 'nyha' in c: return 'nyha'
    if re.search(r'pd-?l1', c): return 'pdl1'
    if re.search(r'\begfr\b|glomerular', c) and not re.search(r'mutation|mutant', c) and re.search(r'\d', c): return 'egfr'
    return None


def rule_check(crit, f):
    """Free check for age and lab-value criteria. Returns None when the criterion is not structured."""
    c = crit.lower()
    if re.search(r'\bage[d]?\b|years of age', c) and re.search(r'\d', c):
        r = parse_range(c)
        if not r: return None
        if f.age is None:
            return {'res': 'unsure', 'ev': 'Age not stated', 'missing': {'key': 'age', 'kind': 'age', 'q': 'What is the patient’s age?'}}
        return {'res': 'yes' if r[0] <= f.age <= r[1] else 'no', 'ev': f'Age {f.age} vs criterion {fmt_range(r)}'}
    k = lab_key(c)
    if not k: return None
    if k == 'nyha':
        c = re.sub(r'\b(iv|iii|ii|i)\b', lambda m: str(ROMAN[m.group(1)]), c)
    r = parse_range(c)
    if not r: return None
    if k not in f.labs:
        return {'res': 'unsure', 'ev': lab_name(k) + ' not in the patient summary',
                'missing': {'key': 'lab:' + k, 'kind': 'lab', 'lab': k, 'q': 'What is the patient’s ' + lab_name(k) + '?'}}
    v = f.labs[k]
    return {'res': 'yes' if r[0] <= v <= r[1] else 'no',
            'ev': f'{lab_short(k)} {fmt_num(v)} vs criterion {fmt_range(r)} · “{f.evidence.get("lab:" + k, "")}”'}


def concepts_in(c):
    low = c.lower()
    return [k for k, pats in VOCAB.items() if any(p in low for p in pats)]


def tier1(crit, f, is_excl):
    """Low-cost check (stand-in): direct matching of the criterion's concepts against the patient facts."""
    cs = concepts_in(crit)
    if not cs:
        return {'res': 'unsure', 'ev': 'No matching fact found in the patient summary'}
    known = [k for k in cs if k in f.concepts]
    if is_excl:
        hit = next((k for k in cs if f.concepts.get(k) is True), None)
        if hit: return {'res': 'yes', 'ev': f'“{f.evidence[hit]}”'}
        if len(known) == len(cs) and all(f.concepts[k] is False for k in cs):
            return {'res': 'no', 'ev': f'“{f.evidence[cs[0]]}”'}
    else:
        neg = next((k for k in cs if f.concepts.get(k) is False), None)
        if neg: return {'res': 'no', 'ev': f'“{f.evidence[neg]}”'}
        if len(known) == len(cs) and all(f.concepts[k] is True for k in cs):
            return {'res': 'yes', 'ev': f'“{f.evidence[cs[0]]}”'}
    return {'res': 'unsure', 'ev': 'Not stated: ' + ', '.join(k for k in cs if k not in f.concepts)}


def tier2(crit, f, is_excl):
    """Escalated check (stand-in for a stronger model): adds clinical inference from labs, sex, age, diagnoses."""
    cs = concepts_in(crit)
    inferred, why = {}, []
    for k in cs:
        if k in f.concepts:
            inferred[k] = f.concepts[k]; continue
        if k == 'chronic kidney disease' and 'egfr' in f.labs:
            e = f.labs['egfr']; inferred[k] = e < 60
            why.append(f'eGFR {fmt_num(e)} ' + ('< 60 suggests CKD' if e < 60 else '≥ 60, no CKD stage 3+'))
        elif k == 'obesity' and 'bmi' in f.labs:
            inferred[k] = f.labs['bmi'] >= 30; why.append(f'BMI {fmt_num(f.labs["bmi"])}')
        elif k == 'prediabetes' and (f.concepts.get('type 2 diabetes') or f.concepts.get('type 1 diabetes')):
            inferred[k] = False; why.append('Patient already has diabetes')
        elif k == 'type 1 diabetes' and f.concepts.get('type 2 diabetes'):
            inferred[k] = False; why.append('Diagnosed with type 2, not type 1')
        elif k == 'type 2 diabetes' and f.concepts.get('type 1 diabetes'):
            inferred[k] = False; why.append('Diagnosed with type 1, not type 2')
        elif k == 'pregnancy' and (f.sex == 'Male' or (f.sex == 'Female' and f.age is not None and f.age >= 55)):
            inferred[k] = False; why.append('Male patient' if f.sex == 'Male' else f'Female, age {f.age}')
        elif k == 'heart failure' and 'ef' in f.labs and f.labs['ef'] <= 40:
            inferred[k] = True; why.append(f'EF {fmt_num(f.labs["ef"])}%')
        elif not is_excl and k in DIAGNOSES and any(c in DIAGNOSES and v for c, v in f.concepts.items()):
            inferred[k] = False; why.append(f'{k} is not among the patient’s documented diagnoses')
    if not cs:
        return {'res': 'unsure', 'ev': 'Needs clinician review'}
    vals = [inferred.get(k) for k in cs]
    if is_excl:
        if any(v is True for v in vals): return {'res': 'yes', 'ev': '; '.join(why) or 'Inferred from record'}
        if all(v is False for v in vals): return {'res': 'no', 'ev': '; '.join(why)}
    else:
        if any(v is False for v in vals): return {'res': 'no', 'ev': '; '.join(why)}
        if all(v is True for v in vals): return {'res': 'yes', 'ev': '; '.join(why)}
    miss = [k for k in cs if k not in inferred]
    return {'res': 'unsure', 'ev': 'Still not stated: ' + ', '.join(miss),
            'missing': {'key': 'concept:' + miss[0], 'kind': 'concept', 'concept': miss[0], 'q': question_for(miss[0])} if miss else None}


def question_for(k):
    special = {'smartphone access': 'Does the patient have smartphone access?',
               'hospitalized for heart failure': 'Was the patient hospitalized for heart failure in the past 30 days?',
               'myocardial infarction': 'Has the patient had a heart attack (myocardial infarction) in the past 3 months?',
               'dialysis': 'Is the patient on dialysis?',
               'kidney transplant': 'Has the patient had a kidney transplant?',
               'osimertinib': 'Has the patient been treated with osimertinib?'}
    if k in special: return special[k]
    if k in MEDS: return f'Is the patient currently taking {k}?'
    return f'Does the patient have {k}?'
