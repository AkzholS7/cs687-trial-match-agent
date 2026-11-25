// HistoryPage.jsx: saved agent runs from the database, with their results and clinician decisions.
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import Results from '../components/Results.jsx';

export default function HistoryPage() {
  const [runs, setRuns] = useState(null);
  const [stats, setStats] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState('');

  const load = () => Promise.all([api.runs(), api.stats()])
    .then(([r, s]) => { setRuns(r); setStats(s); })
    .catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const show = async (id) => {
    try { setOpen(await api.run(id)); } catch (e) { setError(e.message); }
  };
  const remove = async (id) => {
    try {
      await api.deleteRun(id);
      if (open?.id === id) setOpen(null);
      load();
    } catch (e) { setError(e.message); }
  };
  const decide = async (trialId, decision) => {
    const same = open.decisions[trialId]?.decision === decision;
    const d = same ? await api.undecide(open.id, trialId) : await api.decide(open.id, trialId, decision);
    setOpen({ ...open, decisions: d });
    load();
  };

  return (
    <div className="grid">
      <section className="panel" aria-label="Saved runs">
        <h2>Saved runs</h2>
        {stats && (
          <div className="stats two">
            <div className="stat"><b>{stats.runs}</b><span>runs saved</span></div>
            <div className="stat save"><b>{Math.round(stats.avg_saving * 100)}%</b><span>average cost saved</span></div>
            <div className="stat"><b>{stats.accepted}</b><span>trials accepted</span></div>
            <div className="stat"><b>{stats.rejected}</b><span>trials rejected</span></div>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        {runs === null ? <p className="empty">Loading…</p> : runs.length === 0 ? <p className="empty">No runs yet. Run the agent on the Match page.</p> : (
          <ul className="runs">
            {runs.map((r) => (
              <li key={r.id} className={open?.id === r.id ? 'active' : ''}>
                <button className="runbtn" onClick={() => show(r.id)}>
                  <span className="meta">#{r.id} · {new Date(r.created_at).toLocaleString()} · {r.collection}</span>
                  <span className="runtext">{r.patient_summary}</span>
                  <span className="meta">{r.likely_eligible} likely · {r.needs_review} review · {r.not_eligible} not eligible · {Math.round(r.cost_saving * 100)}% saved · {r.decisions} decisions</span>
                </button>
                <button className="small" aria-label={`Delete run ${r.id}`} onClick={() => remove(r.id)}>Delete</button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel" aria-label="Run details">
        <h2>{open ? `Run #${open.id}` : 'Run details'}</h2>
        {open ? (
          <>
            <p className="patient">{open.patient_summary}</p>
            <Results result={open.result} decisions={open.decisions} onDecide={decide} />
          </>
        ) : <p className="empty">Select a run to see its matches, evidence, and trace.</p>}
      </section>
    </div>
  );
}
