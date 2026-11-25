// BenchmarkPage.jsx: retrieval results on public benchmarks (TrialGPT data: SIGIR 2016, TREC CT 2021/2022),
// produced by evaluation/run_baselines.py and served by GET /api/benchmark.
import { useEffect, useState } from 'react';
import { api } from '../api.js';

// Validated categorical palette (fixed order): blue, orange, aqua; gray for the random reference.
const COLORS = { BM25: '#2a78d6', 'TF-IDF': '#eb6834', Hybrid: '#1baf7a', Random: '#9a9994' };
const METHODS = ['Random', 'BM25', 'TF-IDF', 'Hybrid'];
const DATASETS = [['trec_2021', 'TREC 2021'], ['trec_2022', 'TREC 2022'], ['sigir', 'SIGIR']];

function Tooltip({ tip }) {
  if (!tip) return null;
  return <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>;
}

function AlphaChart({ sweep }) {
  const [tip, setTip] = useState(null);
  const pts = Object.entries(sweep).map(([a, v]) => ({ a: Number(a), y: v.ndcg })).sort((p, q) => p.a - q.a);
  const W = 560, H = 260, L = 48, R = 16, T = 20, B = 40;
  const lo = 0.12, hi = 0.155;
  const x = (a) => L + a * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const best = pts.reduce((m, p) => (p.y > m.y ? p : m), pts[0]);
  const ticks = [0.12, 0.13, 0.14, 0.15];
  return (
    <figure className="chart">
      <figcaption>Full retrieval on SIGIR (3,621 trials, 58 patients): NDCG@10 by keyword weight α</figcaption>
      <div className="chartbox">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Line chart of NDCG at 10 by alpha; best at alpha 0.4">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid" />
              <text x={L - 8} y={y(t) + 4} textAnchor="end" className="axis">{t.toFixed(2)}</text>
            </g>
          ))}
          {pts.map((p) => <text key={p.a} x={x(p.a)} y={H - B + 18} textAnchor="middle" className="axis">{p.a.toFixed(1)}</text>)}
          <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="axis">α (0 = only TF-IDF vector score, 1 = only BM25 keyword score)</text>
          <polyline fill="none" stroke={COLORS.BM25} strokeWidth="2" points={pts.map((p) => `${x(p.a)},${y(p.y)}`).join(' ')} />
          {pts.map((p) => (
            <g key={p.a} onMouseEnter={() => setTip({ x: `${(x(p.a) / W) * 100}%`, y: `${(y(p.y) / H) * 100}%`, text: `α ${p.a.toFixed(1)}: NDCG@10 ${p.y.toFixed(4)}` })}
              onMouseLeave={() => setTip(null)}>
              <circle cx={x(p.a)} cy={y(p.y)} r="12" fill="transparent" />
              <circle cx={x(p.a)} cy={y(p.y)} r="4" fill={COLORS.BM25} stroke="var(--panel)" strokeWidth="2" />
            </g>
          ))}
          <text x={x(best.a)} y={y(best.y) - 12} textAnchor="middle" className="label">best {best.y.toFixed(3)} at α {best.a}</text>
        </svg>
        <Tooltip tip={tip} />
      </div>
    </figure>
  );
}

function RerankChart({ rerank }) {
  const [tip, setTip] = useState(null);
  const W = 560, H = 270, L = 48, R = 16, T = 16, B = 40, max = 0.5;
  const groupW = (W - L - R) / DATASETS.length, barW = 22, gap = 2;
  const y = (v) => T + (1 - v / max) * (H - T - B);
  const val = (ds, m) => (m === 'Hybrid' ? Object.entries(rerank[ds]).find(([k]) => k.startsWith('Hybrid'))[1] : rerank[ds][m]).ndcg;
  return (
    <figure className="chart">
      <figcaption>Re-ranking the labeled candidate trials: NDCG@10 by method</figcaption>
      <div className="legend">
        {METHODS.map((m) => <span key={m}><i style={{ background: COLORS[m] }} />{m === 'Hybrid' ? 'Hybrid (α 0.6)' : m}</span>)}
      </div>
      <div className="chartbox">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Grouped bar chart: on these candidate pools random order scores higher than the similarity rankers">
          {[0, 0.1, 0.2, 0.3, 0.4, 0.5].map((t) => (
            <g key={t}>
              <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className={t === 0 ? 'base' : 'grid'} />
              <text x={L - 8} y={y(t) + 4} textAnchor="end" className="axis">{t.toFixed(1)}</text>
            </g>
          ))}
          {DATASETS.map(([ds, name], gi) => {
            const x0 = L + gi * groupW + (groupW - (METHODS.length * (barW + gap) - gap)) / 2;
            return (
              <g key={ds}>
                {METHODS.map((m, mi) => {
                  const v = val(ds, m), bx = x0 + mi * (barW + gap), top = y(v), h = y(0) - top;
                  return (
                    <g key={m} onMouseEnter={() => setTip({ x: `${((bx + barW / 2) / W) * 100}%`, y: `${(top / H) * 100}%`, text: `${name} · ${m}: ${v.toFixed(3)}` })}
                      onMouseLeave={() => setTip(null)}>
                      <rect x={bx - 1} y={T} width={barW + 2} height={y(0) - T} fill="transparent" />
                      <path d={`M${bx},${y(0)} V${top + 4} Q${bx},${top} ${bx + 4},${top} H${bx + barW - 4} Q${bx + barW},${top} ${bx + barW},${top + 4} V${y(0)} Z`} fill={COLORS[m]} />
                    </g>
                  );
                })}
                <text x={L + gi * groupW + groupW / 2} y={H - B + 18} textAnchor="middle" className="axis">{name} ({rerank[ds]._patients} patients)</text>
              </g>
            );
          })}
        </svg>
        <Tooltip tip={tip} />
      </div>
    </figure>
  );
}

export default function BenchmarkPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.benchmark().then(setData).catch((e) => setError(e.message)); }, []);
  if (error) return <section className="panel"><p className="error">{error}</p></section>;
  if (!data) return <section className="panel"><p className="empty">Loading…</p></section>;
  const s = data.sigir_full;
  return (
    <div className="stack">
      <section className="panel">
        <h2>Benchmark results (public data, retrieval stage)</h2>
        <div className="stats">
          <div className="stat"><b>{s['0.4'].ndcg.toFixed(3)}</b><span>best hybrid NDCG@10 (α 0.4)</span></div>
          <div className="stat"><b>+{Math.round((s['0.4'].ndcg / s['1.0'].ndcg - 1) * 100)}%</b><span>vs BM25 alone ({s['1.0'].ndcg.toFixed(3)})</span></div>
          <div className="stat"><b>+{Math.round((s['0.4'].ndcg / s['0.0'].ndcg - 1) * 100)}%</b><span>vs TF-IDF alone ({s['0.0'].ndcg.toFixed(3)})</span></div>
          <div className="stat"><b>{s['0.4'].r100.toFixed(3)}</b><span>recall@100 at α 0.4</span></div>
        </div>
        <div className="charts">
          <AlphaChart sweep={s} />
          <RerankChart rerank={data.rerank} />
        </div>
        <p className="insight"><b>Insight:</b> fusing keyword and vector scores helps when searching the whole collection, but inside a pool of
          similar trials, similarity alone ranks worse than random order, because the most similar trials are often the ones a patient is excluded from.
          Similarity is not eligibility, which is why the agent checks each criterion.</p>
      </section>
      <section className="panel">
        <h2>Table view</h2>
        <div className="tablewrap">
          <table>
            <thead><tr><th>Dataset</th><th>Patients</th>{METHODS.map((m) => <th key={m}>{m} NDCG@10</th>)}</tr></thead>
            <tbody>
              {DATASETS.map(([ds, name]) => (
                <tr key={ds}>
                  <td>{name}</td><td>{data.rerank[ds]._patients}</td>
                  {METHODS.map((m) => {
                    const v = m === 'Hybrid' ? Object.entries(data.rerank[ds]).find(([k]) => k.startsWith('Hybrid'))[1] : data.rerank[ds][m];
                    return <td key={m}>{v.ndcg.toFixed(3)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">Source: TrialGPT dataset (Jin et al., 2024), public domain. Run <code>python evaluation/run_baselines.py TrialGPT/dataset</code> to reproduce.</p>
      </section>
    </div>
  );
}
