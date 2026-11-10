// retrieval.js: Tool 2: hybrid retriever (BM25 keyword score + TF-IDF vector score, convex fusion)
'use strict';

const tok = s => (s.toLowerCase().match(/[a-z0-9]+/g) || []).filter(w => w.length > 1 && !STOP.has(w));
const STOP = new Set('the and for with of in to a an or on at by is are be as from that this not no within past years year old has have who'.split(' '));
function docText(t) { return [t.title, t.conditions.join(' '), t.summary, t.inclusion.join(' '), t.exclusion.join(' ')].join(' '); }
function bm25Scores(query, docs, k1 = 1.2, b = 0.75) {
  const toks = docs.map(d => tok(d)), N = docs.length, avg = toks.reduce((a, t) => a + t.length, 0) / Math.max(N, 1);
  const df = {}; toks.forEach(t => new Set(t).forEach(w => df[w] = (df[w] || 0) + 1));
  const q = tok(query);
  return toks.map(t => { const tf = {}; t.forEach(w => tf[w] = (tf[w] || 0) + 1);
    return q.reduce((s, w) => { if (!tf[w]) return s; const idf = Math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5));
      return s + idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * t.length / avg)); }, 0); });
}
function tfidfCos(query, docs) {
  const all = [...docs, query].map(tok), N = all.length, df = {};
  all.forEach(t => new Set(t).forEach(w => df[w] = (df[w] || 0) + 1));
  const vec = t => { const tf = {}; t.forEach(w => tf[w] = (tf[w] || 0) + 1); const v = {}; let n = 0;
    for (const w in tf) { v[w] = tf[w] * Math.log(N / df[w]); n += v[w] ** 2; } n = Math.sqrt(n) || 1; for (const w in v) v[w] /= n; return v; };
  const qv = vec(all[N - 1]);
  return all.slice(0, -1).map(t => { const dv = vec(t); let s = 0; for (const w in qv) if (dv[w]) s += qv[w] * dv[w]; return s; });
}
const minmax = a => { const lo = Math.min(...a), hi = Math.max(...a); return a.map(x => hi > lo ? (x - lo) / (hi - lo) : 0); };