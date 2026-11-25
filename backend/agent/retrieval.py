"""Tool 2: hybrid retriever - BM25 keyword score + TF-IDF vector score, combined by convex fusion."""
import math
import re

STOP = set('the and for with of in to a an or on at by is are be as from that this not no within past years year old has have who'.split())


def tokens(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if len(w) > 1 and w not in STOP]


def trial_text(t):
    return ' '.join([t['title'], ' '.join(t['conditions']), t['summary'], ' '.join(t['inclusion']), ' '.join(t['exclusion'])])


def bm25_scores(query, docs, k1=1.2, b=0.75):
    toks = [tokens(d) for d in docs]
    n = len(docs)
    avg = sum(len(t) for t in toks) / max(n, 1)
    df = {}
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    q = tokens(query)
    scores = []
    for t in toks:
        tf = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    return scores


def tfidf_cosine(query, docs):
    all_toks = [tokens(d) for d in docs] + [tokens(query)]
    n = len(all_toks)
    df = {}
    for t in all_toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1

    def vec(t):
        tf = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        v = {w: c * math.log(n / df[w]) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    qv = vec(all_toks[-1])
    out = []
    for t in all_toks[:-1]:
        dv = vec(t)
        out.append(sum(x * dv.get(w, 0.0) for w, x in qv.items()))
    return out


def minmax(xs):
    if not xs:
        return []
    lo, hi = min(xs), max(xs)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def hybrid_rank(query, trials, alpha=0.6, top_k=8):
    """Rank trials by alpha * BM25 + (1 - alpha) * TF-IDF (both min-max normalized)."""
    docs = [trial_text(t) for t in trials]
    bm = minmax(bm25_scores(query, docs))
    cs = minmax(tfidf_cosine(query, docs))
    ranked = [{'trial': t, 'bm25': bm[i], 'vector': cs[i], 'fused': alpha * bm[i] + (1 - alpha) * cs[i]} for i, t in enumerate(trials)]
    ranked.sort(key=lambda r: -r['fused'])
    return ranked[:top_k]
