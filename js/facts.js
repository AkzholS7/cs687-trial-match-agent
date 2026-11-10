// facts.js: Tool 0: read patient facts (age, sex, location, conditions, labs) from free text
'use strict';

function sentences(text) { return text.split(/(?<=[.;])\s+/); }
function findTerm(text, concept) {
  const low = text.toLowerCase();
  for (const pat of VOCAB[concept]) {
    let idx = low.indexOf(pat);
    while (idx !== -1) {
      const sStart = Math.max(low.lastIndexOf('.', idx), low.lastIndexOf(';', idx)) + 1;
      const before = low.slice(Math.max(sStart, idx - 60), idx);
      const negated = NEG_CUES.some(c => before.includes(c));
      const sent = sentences(text).find(s => s.toLowerCase().includes(pat)) || '';
      return { value: !negated, evidence: sent.trim() };
    }
  }
  return null;
}
function extractFacts(text, overrides) {
  const low = text.toLowerCase();
  const f = { age: null, sex: null, city: null, state: null, labs: {}, concepts: {}, evidence: {} };
  let m = low.match(/(\d{1,3})[- ]year[- ]old/) || low.match(/\bage[d]?\s*(\d{1,3})/);
  if (m) f.age = +m[1];
  if (/\b(woman|female|she|her)\b/.test(low)) f.sex = 'Female'; else if (/\b(man|male|he|his)\b/.test(low)) f.sex = 'Male';
  m = text.match(/(?:[Ll]ives in|[Rr]esides in|[Ll]ocated in)\s+([A-Za-z .]+?),\s*([A-Z]{2})\b/);
  if (m) { f.city = m[1].trim(); f.state = m[2]; }
  for (const [k, L] of Object.entries(LABS)) {
    const mm = low.match(L.re);
    if (mm) { const v = mm[1]; f.labs[k] = ROMAN[v] || +v; f.evidence['lab:' + k] = (sentences(text).find(s => L.re.test(s.toLowerCase())) || '').trim(); }
  }
  for (const c of Object.keys(VOCAB)) { const r = findTerm(text, c); if (r) { f.concepts[c] = r.value; f.evidence[c] = r.evidence; } }
  // clinician answers override text
  for (const [k, v] of Object.entries(overrides.labs)) { f.labs[k] = v; f.evidence['lab:' + k] = 'Clinician answer'; }
  for (const [k, v] of Object.entries(overrides.concepts)) { f.concepts[k] = v; f.evidence[k] = 'Clinician answer'; }
  if (overrides.age != null) { f.age = overrides.age; }
  return f;
}