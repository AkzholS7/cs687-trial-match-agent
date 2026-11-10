// checker.js: Tools 3-5: rule checks, low-cost check, escalation, and clinician questions
'use strict';

function parseRange(c) {
  let m;
  const num = '(\\d+(?:\\.\\d+)?)';
  if ((m = c.match(new RegExp('between\\s*' + num + '%?\\s*(?:and|to)\\s*' + num)))) return [+m[1], +m[2]];
  if ((m = c.match(new RegExp(num + '\\s*%?\\s*(?:to|-|–|or)\\s*' + num)))) return [+m[1], +m[2]];
  if ((m = c.match(new RegExp('(?:≥|>=|at least|greater than or equal to|minimum of)\\s*' + num)))) return [+m[1], Infinity];
  if ((m = c.match(new RegExp(num + '\\s*%?\\s*(?:or more|or greater|or higher|and above)')))) return [+m[1], Infinity];
  if ((m = c.match(new RegExp('(?:≤|<=|at most|less than or equal to|up to|no more than)\\s*' + num)))) return [-Infinity, +m[1]];
  if ((m = c.match(new RegExp(num + '\\s*%?\\s*(?:or less|or lower|or below)')))) return [-Infinity, +m[1]];
  if ((m = c.match(new RegExp('(?:greater than|more than|above|>)\\s*' + num)))) return [+m[1] + 1e-9, Infinity];
  if ((m = c.match(new RegExp('(?:less than|below|under|<)\\s*' + num)))) return [-Infinity, +m[1] - 1e-9];
  return null;
}
function labKey(c) {
  if (/hba1c|a1c/.test(c)) return 'hba1c';
  if (/ejection fraction|lvef/.test(c) && /\d/.test(c)) return 'ef';
  if (/\bbmi\b|body mass index/.test(c)) return 'bmi';
  if (/ecog/.test(c)) return 'ecog';
  if (/potassium/.test(c)) return 'potassium';
  if (/nyha/.test(c)) return 'nyha';
  if (/pd-?l1/.test(c)) return 'pdl1';
  if (/\begfr\b|glomerular/.test(c) && !/mutation|mutant/.test(c) && /\d/.test(c)) return 'egfr';
  return null;
}
const fmt = r => (r[0] === -Infinity ? '≤ ' + (+r[1].toFixed(2)) : r[1] === Infinity ? '≥ ' + (+r[0].toFixed(2)) : r[0] + '–' + r[1]);
/* Rule tier: free. Returns {res:'yes'|'no'|'unsure', ev, missing} or null when not a structured criterion. */
function ruleCheck(crit, f) {
  let c = crit.toLowerCase();
  if (/\bage[d]?\b|years of age/.test(c) && /\d/.test(c)) {
    const r = parseRange(c); if (!r) return null;
    if (f.age == null) return { res: 'unsure', ev: 'Age not stated', missing: { key: 'age', kind: 'age', q: 'What is the patient’s age?' } };
    return { res: f.age >= r[0] && f.age <= r[1] ? 'yes' : 'no', ev: `Age ${f.age} vs criterion ${fmt(r)}` };
  }
  const k = labKey(c); if (!k) return null;
  if (k === 'nyha') c = c.replace(/\b(iv|iii|ii|i)\b/g, x => ROMAN[x]);
  const r = parseRange(c); if (!r) return null;
  if (f.labs[k] == null) return { res: 'unsure', ev: LABS[k].name + ' not in the patient summary', missing: { key: 'lab:' + k, kind: 'lab', lab: k, q: 'What is the patient’s ' + LABS[k].name + '?' } };
  const v = f.labs[k];
  return { res: v >= r[0] && v <= r[1] ? 'yes' : 'no', ev: `${LABS[k].name.split(' (')[0]} ${v} vs criterion ${fmt(r)} · “${f.evidence['lab:' + k]}”` };
}
function conceptsIn(c) { const low = c.toLowerCase(); return Object.keys(VOCAB).filter(k => VOCAB[k].some(p => low.includes(p))); }
/* Tier 1 (low-cost model stand-in): direct matching of concepts in the patient text. */
function tier1(crit, f, isExcl) {
  const cs = conceptsIn(crit);
  if (!cs.length) return { res: 'unsure', ev: 'No matching fact found in the patient summary' };
  const vals = cs.map(k => f.concepts[k]);
  const known = cs.filter(k => f.concepts[k] !== undefined);
  if (isExcl) {
    const hit = cs.find(k => f.concepts[k] === true); if (hit) return { res: 'yes', ev: `“${f.evidence[hit]}”` };
    if (known.length === cs.length && vals.every(v => v === false)) return { res: 'no', ev: `“${f.evidence[cs[0]]}”` };
  } else {
    const neg = cs.find(k => f.concepts[k] === false); if (neg) return { res: 'no', ev: `“${f.evidence[neg]}”` };
    if (known.length === cs.length && vals.every(v => v === true)) return { res: 'yes', ev: `“${f.evidence[cs[0]]}”` };
  }
  return { res: 'unsure', ev: 'Not stated: ' + cs.filter(k => f.concepts[k] === undefined).join(', '), concepts: cs };
}
/* Tier 2 (strong model stand-in): adds clinical inference from labs, sex, age and related diagnoses. */
function tier2(crit, f, isExcl) {
  const cs = conceptsIn(crit), inferred = {}, why = [];
  for (const k of cs) {
    if (f.concepts[k] !== undefined) { inferred[k] = f.concepts[k]; continue; }
    if (k === 'chronic kidney disease' && f.labs.egfr != null) { inferred[k] = f.labs.egfr < 60; why.push(`eGFR ${f.labs.egfr} ${f.labs.egfr < 60 ? '< 60 suggests CKD' : '≥ 60, no CKD stage 3+'}`); }
    else if (k === 'obesity' && f.labs.bmi != null) { inferred[k] = f.labs.bmi >= 30; why.push(`BMI ${f.labs.bmi}`); }
    else if (k === 'prediabetes' && (f.concepts['type 2 diabetes'] || f.concepts['type 1 diabetes'])) { inferred[k] = false; why.push('Patient already has diabetes'); }
    else if (k === 'type 1 diabetes' && f.concepts['type 2 diabetes']) { inferred[k] = false; why.push('Diagnosed with type 2, not type 1'); }
    else if (k === 'type 2 diabetes' && f.concepts['type 1 diabetes']) { inferred[k] = false; why.push('Diagnosed with type 1, not type 2'); }
    else if (k === 'pregnancy' && (f.sex === 'Male' || (f.sex === 'Female' && f.age >= 55))) { inferred[k] = false; why.push(f.sex === 'Male' ? 'Male patient' : `Female, age ${f.age}`); }
    else if (k === 'heart failure' && f.labs.ef != null && f.labs.ef <= 40) { inferred[k] = true; why.push(`EF ${f.labs.ef}%`); }
    else if (!isExcl && DIAGNOSES.has(k) && Object.keys(f.concepts).some(c => DIAGNOSES.has(c) && f.concepts[c])) { inferred[k] = false; why.push(`${k} is not among the patient\u2019s documented diagnoses`); }
  }
  const vals = cs.map(k => inferred[k]);
  if (!cs.length) return { res: 'unsure', ev: 'Needs clinician review' };
  if (isExcl) {
    if (vals.some(v => v === true)) return { res: 'yes', ev: why.join('; ') || 'Inferred from record' };
    if (vals.every(v => v === false)) return { res: 'no', ev: why.join('; ') };
  } else {
    if (vals.some(v => v === false)) return { res: 'no', ev: why.join('; ') };
    if (vals.every(v => v === true)) return { res: 'yes', ev: why.join('; ') };
  }
  const miss = cs.filter(k => inferred[k] === undefined);
  return { res: 'unsure', ev: 'Still not stated: ' + miss.join(', '), missing: miss.length ? { key: 'concept:' + miss[0], kind: 'concept', concept: miss[0], q: questionFor(miss[0]) } : null };
}
function questionFor(k) {
  if (k === 'smartphone access') return 'Does the patient have smartphone access?';
  if (k === 'hospitalized for heart failure') return 'Was the patient hospitalized for heart failure in the past 30 days?';
  if (k === 'myocardial infarction') return 'Has the patient had a heart attack (myocardial infarction) in the past 3 months?';
  if (k === 'dialysis') return 'Is the patient on dialysis?';
  if (k === 'kidney transplant') return 'Has the patient had a kidney transplant?';
  if (k === 'osimertinib') return 'Has the patient been treated with osimertinib?';
  if (MEDS.has(k)) return `Is the patient currently taking ${k}?`;
  return `Does the patient have ${k}?`;
}