// Results.jsx: summary numbers, clinician questions, ranked trial cards, and the agent trace for one run.
import { useState } from 'react';
import TrialCard from './TrialCard.jsx';

export function Stats({ result }) {
  const c = result.cost;
  const items = [
    [`${result.funnel[0]} → ${result.trials.length}`, 'trials screened → checked'],
    [`${c.low_cost} + ${c.escalated}`, 'low-cost + escalated calls'],
    [`$${c.spent.toFixed(4)}`, `est. cost vs $${c.fixed.toFixed(3)} fixed pipeline`],
    [`${Math.round(c.saving * 100)}%`, 'estimated cost saved', 'save'],
  ];
  return (
    <>
      <div className="stats">
        {items.map(([value, label, cls]) => (
          <div key={label} className={`stat ${cls || ''}`}><b>{value}</b><span>{label}</span></div>
        ))}
      </div>
      <div className="funnel">
        Filter: {result.funnel[0]} trials → {result.funnel[1]} recruiting → {result.funnel[2]} fit age and sex → {result.funnel[3]} nearby
        → top {result.trials.length} checked · {c.rule} rule checks (free) · {c.skipped} checks skipped by early stopping · checker: {result.mode}
      </div>
    </>
  );
}

function answerKey(q) {
  return q.key;
}

export function Questions({ questions, onAnswer, busy }) {
  const [values, setValues] = useState({});
  if (!questions.length) return null;
  const set = (k, v) => setValues((old) => ({ ...old, [k]: v }));
  const submit = (e) => {
    e.preventDefault();
    const answers = { labs: {}, concepts: {}, criteria: {} };
    for (const q of questions) {
      const v = values[answerKey(q)];
      if (v === undefined || v === '') continue;
      if (q.kind === 'lab') answers.labs[q.lab] = Number(v);
      else if (q.kind === 'age') answers.age = Number(v);
      else if (q.kind === 'concept') answers.concepts[q.concept] = v === 'yes';
      else if (q.kind === 'criterion') answers.criteria[q.criterion] = v === 'yes';
    }
    onAnswer(answers);
    setValues({});
  };
  return (
    <form className="questions" onSubmit={submit}>
      <h3>Questions for the clinician ({questions.length})</h3>
      <p className="hint">The agent stops and asks instead of guessing. Answer and re-run to update the matches.</p>
      {questions.map((q, i) => (
        <div className="q" key={q.key}>
          <label htmlFor={`q${i}`}>{q.q} <span className="meta">{(q.trials || []).join(', ')}</span></label>
          {q.kind === 'lab' || q.kind === 'age' ? (
            <input type="number" step="0.1" id={`q${i}`} placeholder="value" value={values[answerKey(q)] ?? ''}
              onChange={(e) => set(answerKey(q), e.target.value)} />
          ) : (
            <select id={`q${i}`} value={values[answerKey(q)] ?? ''} onChange={(e) => set(answerKey(q), e.target.value)}>
              <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
            </select>
          )}
        </div>
      ))}
      <div><button className="small" type="submit" disabled={busy}>Apply answers and re-run</button></div>
    </form>
  );
}

export function Trace({ steps }) {
  return (
    <div className="trace" aria-live="polite">
      {steps.map((s, i) => (
        <div className="step" key={i}>
          <div><b>Step {i + 1} · Thought:</b> {s.thought}</div>
          <div><b>Action:</b> {s.action}</div>
          <div><b>Observation:</b> {s.observation}</div>
        </div>
      ))}
    </div>
  );
}

export default function Results({ result, decisions, onDecide, onAnswer, busy }) {
  return (
    <>
      <Stats result={result} />
      {onAnswer && <Questions questions={result.questions} onAnswer={onAnswer} busy={busy} />}
      <div className="list">
        {result.trials.length ? result.trials.map((t, i) => (
          <TrialCard key={t.id} trial={t} rank={i + 1} open={i < 2} decision={decisions[t.id]}
            onDecide={onDecide ? (d) => onDecide(t.id, d) : null} />
        )) : <p className="empty">No trials matched the filters. Try another patient or location.</p>}
      </div>
      <h2>Agent trace</h2>
      <Trace steps={result.trace} />
    </>
  );
}
