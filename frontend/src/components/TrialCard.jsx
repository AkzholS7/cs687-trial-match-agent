// TrialCard.jsx: one ranked trial with its criterion-by-criterion evidence and the clinician's decision.
const STATUS = {
  likely_eligible: ['ok', 'Likely eligible'],
  needs_review: ['warn', 'Needs review'],
  not_eligible: ['bad', 'Not eligible'],
};

function resultLabel(row) {
  if (row.result === 'skip') return ['skip', 'Skipped'];
  if (row.result === 'unsure') return ['warn', 'Unsure'];
  if (row.exclusion) return row.result === 'yes' ? ['bad', 'Applies'] : ['ok', 'Does not apply'];
  return row.result === 'yes' ? ['ok', 'Met'] : ['bad', 'Not met'];
}

export default function TrialCard({ trial, rank, open, decision, onDecide }) {
  const [cls, label] = STATUS[trial.status];
  const where = trial.locations.slice(0, 2).map((l) => `${l.city}, ${l.state}`).join(' · ') || 'location not reported';
  return (
    <details className="trial" open={open}>
      <summary>
        <span className="rank">#{rank}</span>
        <span className="ttl">
          {trial.title}
          <div className="meta">
            {trial.id} · {where} · match {trial.match.toFixed(2)} (BM25 {trial.bm25.toFixed(2)}, vector {trial.vector.toFixed(2)})
          </div>
        </span>
        <span className={`pill ${cls}`}>{label}</span>
      </summary>
      <div className="body">
        <div className="tablewrap">
          <table>
            <thead><tr><th>Type</th><th>Criterion</th><th>Result</th><th>Evidence</th><th>Checked by</th></tr></thead>
            <tbody>
              {trial.criteria.map((row, i) => {
                const [lc, lt] = resultLabel(row);
                return (
                  <tr key={i}>
                    <td>{row.exclusion ? 'Exclusion' : 'Inclusion'}</td>
                    <td>{row.criterion}</td>
                    <td><span className={`lab ${lc}`}>{lt}</span></td>
                    <td className="ev">{row.evidence}</td>
                    <td className="tier">{row.tier}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {onDecide && (
          <div className="decide">
            <button className="small" aria-pressed={decision?.decision === 'accept'} onClick={() => onDecide('accept')}>Accept for referral</button>
            <button className="small" aria-pressed={decision?.decision === 'reject'} onClick={() => onDecide('reject')}>Reject</button>
            {decision && (
              <span className="decision" style={{ color: `var(${decision.decision === 'accept' ? '--ok' : '--bad'})` }}>
                Clinician decision: {decision.decision === 'accept' ? 'Accepted' : 'Rejected'} (saved)
              </span>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
