// MatchPage.jsx: enter a patient, tune the agent, run it on the backend, answer questions, record decisions.
import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import Results from '../components/Results.jsx';

const EMPTY_ANSWERS = { labs: {}, concepts: {}, criteria: {} };

function mergeAnswers(a, b) {
  return {
    labs: { ...a.labs, ...b.labs },
    concepts: { ...a.concepts, ...b.concepts },
    criteria: { ...a.criteria, ...b.criteria },
    ...(b.age !== undefined ? { age: b.age } : a.age !== undefined ? { age: a.age } : {}),
  };
}

export default function MatchPage({ collections }) {
  const [examples, setExamples] = useState([]);
  const [exampleId, setExampleId] = useState(null);
  const [collection, setCollection] = useState('demo');
  const [summary, setSummary] = useState('');
  const [settings, setSettings] = useState({ top_k: 8, alpha: 0.6, budget: 0.5, price_low: 0.0005, price_strong: 0.02, use_llm: false });
  const [answers, setAnswers] = useState(EMPTY_ANSWERS);
  const [result, setResult] = useState(null);
  const [decisions, setDecisions] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const started = useRef(false); // React StrictMode runs effects twice in development; run the first example once

  const run = async (text, coll, ans) => {
    if (!text.trim()) { setError('Enter a patient summary first.'); return; }
    setBusy(true); setError('');
    try {
      const out = await api.match({ summary: text, collection: coll, settings, answers: ans });
      setResult(out); setDecisions({});
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const pick = (ex) => {
    setExampleId(ex.id); setSummary(ex.summary); setCollection(ex.collection); setAnswers(EMPTY_ANSWERS);
    run(ex.summary, ex.collection, EMPTY_ANSWERS);
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api.examples().then((list) => { setExamples(list); if (list[0]) pick(list[0]); }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onAnswer = (newAnswers) => {
    const merged = mergeAnswers(answers, newAnswers);
    setAnswers(merged);
    run(summary, collection, merged);
  };

  const onDecide = async (trialId, decision) => {
    if (!result?.run_id) return;
    try {
      const same = decisions[trialId]?.decision === decision;
      setDecisions(same ? await api.undecide(result.run_id, trialId) : await api.decide(result.run_id, trialId, decision));
    } catch (e) {
      setError(e.message);
    }
  };

  const num = (key, label, attrs) => (
    <div className="field">
      <label htmlFor={key}>{label}</label>
      <input type="number" id={key} value={settings[key]} {...attrs}
        onChange={(e) => setSettings({ ...settings, [key]: e.target.value === '' ? '' : Number(e.target.value) })} />
    </div>
  );
  const shown = examples.filter((e) => e.collection === collection);

  return (
    <div className="grid">
      <section className="panel" aria-label="Patient and settings">
        <h2>Patient</h2>
        <div className="field">
          <label htmlFor="collection">Trial collection</label>
          <select id="collection" value={collection} onChange={(e) => { setCollection(e.target.value); setAnswers(EMPTY_ANSWERS); }}>
            {collections.map((c) => <option key={c.name} value={c.name}>{c.name === 'demo' ? 'Demo sample trials' : `Benchmark: ${c.name.toUpperCase()}`} ({c.trials})</option>)}
          </select>
        </div>
        {shown.length > 0 && (
          <div className="examples" role="group" aria-label="Example patients">
            {shown.slice(0, 6).map((ex) => (
              <button key={ex.id} className="small" aria-pressed={exampleId === ex.id} onClick={() => pick(ex)}>{ex.label}</button>
            ))}
          </div>
        )}
        <div className="field">
          <label htmlFor="summary">Patient summary (example, not a real patient)</label>
          <textarea id="summary" value={summary} onChange={(e) => { setSummary(e.target.value); setExampleId(null); }} />
        </div>
        <button className="primary" disabled={busy} onClick={() => { setAnswers(EMPTY_ANSWERS); run(summary, collection, EMPTY_ANSWERS); }}>
          {busy ? 'Running…' : 'Run agent'}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
        <h2>Agent settings</h2>
        <div className="settings">
          {num('top_k', 'Trials to check', { min: 1, max: 20 })}
          {num('alpha', 'Keyword weight (α)', { min: 0, max: 1, step: 0.1 })}
          {num('budget', 'Budget per patient ($)', { min: 0, step: 0.01 })}
          {num('price_strong', 'Strong model ($/call)', { min: 0, step: 0.001 })}
          {num('price_low', 'Low-cost model ($/call)', { min: 0, step: 0.0001 })}
          <div className="field">
            <label htmlFor="use_llm">Checker</label>
            <select id="use_llm" value={settings.use_llm ? 'llm' : 'rule'} onChange={(e) => setSettings({ ...settings, use_llm: e.target.value === 'llm' })}>
              <option value="rule">Rule-based (offline)</option>
              <option value="llm">LLM (needs API key)</option>
            </select>
          </div>
          <p className="hint full">Costs are estimates per criterion check. Without an API key on the server, a rule-based checker stands in for the low-cost and strong models.</p>
        </div>
      </section>

      <section className="panel" aria-label="Results" aria-busy={busy}>
        <h2>Results {result?.run_id && <span className="saved">· saved as run #{result.run_id}</span>}</h2>
        {result ? <Results result={result} decisions={decisions} onDecide={onDecide} onAnswer={onAnswer} busy={busy} />
          : <p className="empty">{busy ? 'Running the agent…' : 'Run the agent to see matches.'}</p>}
      </section>
    </div>
  );
}
