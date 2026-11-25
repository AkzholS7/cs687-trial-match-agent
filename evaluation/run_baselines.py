"""
run_baselines.py - Sprint 7 experiments for the Trial Match Agent (CS 687 capstone).

Runs the retrieval part of the agent on public benchmark data and writes results to results/.
Data: the SIGIR 2016, TREC 2021 and TREC 2022 files shipped in the TrialGPT repository
(https://github.com/ncbi-nlp/TrialGPT, folder dataset/). No API key or LLM is needed.

Usage:
    git clone https://github.com/ncbi-nlp/TrialGPT
    python run_baselines.py TrialGPT/dataset

Experiments:
  1. SIGIR full retrieval: rank all 3,620 SIGIR trials for each of 58 patients with
     BM25 (keyword), TF-IDF cosine (vector), and their convex fusion; sweep alpha 0..1.
  2. Re-ranking of each patient's labeled trials (TREC 2021, TREC 2022, SIGIR) with the
     same methods, plus a random-order reference.
Metrics: NDCG@10 with graded gains (2 = eligible / highly relevant, 1 = partly, 0 = not),
P@10 counting label-2 trials as relevant, and Recall@100 (label >= 1) for full retrieval.
"""
import json, math, os, random, re, sys, csv
from collections import Counter, defaultdict

DATA = sys.argv[1] if len(sys.argv) > 1 else 'TrialGPT/dataset'
OUT = 'results'; os.makedirs(OUT, exist_ok=True)
STOP = set('the a an and or of in to for with on at by is are be as from that this not no within past years year old has have who was were his her he she patient patients criteria inclusion exclusion study'.split())

def tokens(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if len(w) > 1 and w not in STOP]

class Index:
    """BM25 and TF-IDF over one list of documents."""
    def __init__(self, docs, k1=1.2, b=0.75):
        self.toks = [tokens(d) for d in docs]; self.N = len(docs); self.k1, self.b = k1, b
        self.avg = sum(map(len, self.toks)) / max(self.N, 1)
        self.df = Counter(w for t in self.toks for w in set(t))
        self.tf = [Counter(t) for t in self.toks]
        idf = {w: math.log(self.N / c) for w, c in self.df.items()}
        self.vecs = []
        for tf in self.tf:
            v = {w: n * idf[w] for w, n in tf.items()}; norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            self.vecs.append({w: x / norm for w, x in v.items()})
        self.idf = idf
    def bm25(self, q):
        q = tokens(q); out = []
        for tf, t in zip(self.tf, self.toks):
            s = 0.0
            for w in q:
                if w in tf:
                    idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(t) / self.avg))
            out.append(s)
        return out
    def tfidf(self, q):
        tf = Counter(w for w in tokens(q) if w in self.idf)
        v = {w: n * self.idf[w] for w, n in tf.items()}; norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return [sum(x / norm * d.get(w, 0.0) for w, x in v.items()) for d in self.vecs]

def minmax(xs):
    lo, hi = min(xs), max(xs)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]

def fuse(bm, tf, alpha):
    return [alpha * a + (1 - alpha) * b for a, b in zip(minmax(bm), minmax(tf))]

def ndcg_at(ranked_labels, all_labels, k=10):
    dcg = sum(l / math.log2(i + 2) for i, l in enumerate(ranked_labels[:k]))
    ideal = sorted(all_labels, reverse=True)[:k]
    idcg = sum(l / math.log2(i + 2) for i, l in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0

def p_at(ranked_labels, k=10):
    return sum(1 for l in ranked_labels[:k] if l == 2) / k

def mean(xs): return sum(xs) / len(xs) if xs else 0.0

def load_jsonl(p):
    with open(p, encoding='utf-8') as f: return [json.loads(l) for l in f if l.strip()]

def load_qrels(p):
    q = defaultdict(dict)
    with open(p, encoding='utf-8') as f:
        next(f)
        for line in f:
            qid, did, s = line.strip().split('\t'); q[qid][did] = int(s)
    return q

results = {}

# ---------------- Experiment 1: SIGIR full retrieval ----------------
corpus = load_jsonl(f'{DATA}/sigir/corpus.jsonl')
queries = load_jsonl(f'{DATA}/sigir/queries.jsonl')
qrels = load_qrels(f'{DATA}/sigir/qrels/test.tsv')
ids = [d['_id'] for d in corpus]
idx = Index([d.get('title', '') + ' ' + d.get('text', '') for d in corpus])
alphas = [round(a * 0.1, 1) for a in range(11)]
per = {a: {'ndcg': [], 'p10': [], 'r100': []} for a in alphas}
per_patient_rows = []
for q in queries:
    if q['_id'] not in qrels: continue
    rel = qrels[q['_id']]; bm, tf = idx.bm25(q['text']), idx.tfidf(q['text'])
    n_rel = sum(1 for v in rel.values() if v >= 1)
    for a in alphas:
        sc = fuse(bm, tf, a); order = sorted(range(len(ids)), key=lambda i: -sc[i])
        labels = [rel.get(ids[i], 0) for i in order]
        per[a]['ndcg'].append(ndcg_at(labels, list(rel.values())))
        per[a]['p10'].append(p_at(labels))
        per[a]['r100'].append(sum(1 for l in labels[:100] if l >= 1) / n_rel if n_rel else 0.0)
    per_patient_rows.append((q['_id'], per[0.6]['ndcg'][-1], per[1.0]['ndcg'][-1], per[0.0]['ndcg'][-1]))
results['sigir_full'] = {str(a): {k: round(mean(v), 4) for k, v in per[a].items()} for a in alphas}
results['sigir_full_n_patients'] = len(per[0.0]['ndcg'])
with open(f'{OUT}/sigir_full_per_patient.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['patient', 'ndcg10_hybrid_a0.6', 'ndcg10_bm25', 'ndcg10_tfidf']); w.writerows(per_patient_rows)

# ---------------- Experiment 2: re-ranking labeled trials ----------------
def trial_text(t):
    return ' '.join(str(t.get(k, '')) for k in ['brief_title', 'diseases_list', 'drugs_list', 'brief_summary', 'inclusion_criteria', 'exclusion_criteria'])
results['rerank'] = {}; label_counts = {}
for ds in ['trec_2021', 'trec_2022', 'sigir']:
    pats = json.load(open(f'{DATA}/{ds}/retrieved_trials.json', encoding='utf-8'))
    m = {name: {'ndcg': [], 'p10': []} for name in ['Random', 'BM25', 'TF-IDF', 'Hybrid (a=0.6)']}
    lc = Counter(); rng = random.Random(687)
    for p in pats:
        items = [(t, int(lab)) for lab in ['0', '1', '2'] for t in p[lab]]
        if not items: continue
        lc.update(l for _, l in items)
        labels_all = [l for _, l in items]
        if max(labels_all) == 0: continue
        pidx = Index([trial_text(t) for t, _ in items]); bm, tf = pidx.bm25(p['patient']), pidx.tfidf(p['patient'])
        for name, sc in [('BM25', bm), ('TF-IDF', tf), ('Hybrid (a=0.6)', fuse(bm, tf, 0.6))]:
            order = sorted(range(len(items)), key=lambda i: -sc[i]); lab = [labels_all[i] for i in order]
            m[name]['ndcg'].append(ndcg_at(lab, labels_all)); m[name]['p10'].append(p_at(lab))
        rn, rp = [], []
        for _ in range(20):
            lab = labels_all[:]; rng.shuffle(lab); rn.append(ndcg_at(lab, labels_all)); rp.append(p_at(lab))
        m['Random']['ndcg'].append(mean(rn)); m['Random']['p10'].append(mean(rp))
    results['rerank'][ds] = {name: {k: round(mean(v), 4) for k, v in d.items()} for name, d in m.items()}
    results['rerank'][ds]['_patients'] = len(m['BM25']['ndcg'])
    label_counts[ds] = {'not relevant (0)': lc[0], 'excluded / partly (1)': lc[1], 'eligible (2)': lc[2]}
results['label_counts'] = label_counts
json.dump(results, open(f'{OUT}/results.json', 'w'), indent=1)
print(json.dumps(results, indent=1))
