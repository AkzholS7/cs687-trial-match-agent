// TrialsPage.jsx: browse and search the trials stored in the database.
import { useEffect, useState } from 'react';
import { api } from '../api.js';

const PAGE = 20;

export default function TrialsPage({ collections }) {
  const [collection, setCollection] = useState('demo');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.trials(collection, query, offset, PAGE).then(setPage).catch((e) => setError(e.message));
  }, [collection, query, offset]);

  const search = (e) => { e.preventDefault(); setOffset(0); setQuery(q.trim()); };

  return (
    <div className="grid">
      <section className="panel" aria-label="Trial list">
        <h2>Trials in the database</h2>
        <form className="searchbar" onSubmit={search}>
          <select aria-label="Collection" value={collection} onChange={(e) => { setCollection(e.target.value); setOffset(0); setSelected(null); }}>
            {collections.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.trials})</option>)}
          </select>
          <input type="text" aria-label="Search trials" placeholder="Search ID, title, condition" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" className="small">Search</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
        {page && (
          <>
            <ul className="runs">
              {page.items.map((t) => (
                <li key={t.id} className={selected?.id === t.id ? 'active' : ''}>
                  <button className="runbtn" onClick={() => setSelected(t)}>
                    <span className="meta">{t.id} · {t.status || 'status not reported'}</span>
                    <span className="runtext">{t.title}</span>
                    <span className="meta">{t.conditions.slice(0, 3).join(', ')}</span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="pager">
              <button className="small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
              <span className="meta">{page.total ? `${offset + 1}–${Math.min(offset + PAGE, page.total)} of ${page.total}` : 'No trials found'}</span>
              <button className="small" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
            </div>
          </>
        )}
      </section>
      <section className="panel" aria-label="Trial details">
        {selected ? (
          <>
            <h2>{selected.id}</h2>
            <h3 className="trialtitle">{selected.title}</h3>
            <p className="meta">
              {selected.status || 'Status not reported'} · sex: {selected.sex} · age: {selected.min_age ?? 'any'}–{selected.max_age ?? 'any'}
              {selected.locations.length > 0 && ` · ${selected.locations.map((l) => `${l.city}, ${l.state}`).join(' · ')}`}
            </p>
            {selected.summary && <p>{selected.summary}</p>}
            <h2>Inclusion criteria</h2>
            <ul className="crit">{selected.inclusion.map((c, i) => <li key={i}>{c}</li>)}</ul>
            <h2>Exclusion criteria</h2>
            <ul className="crit">{selected.exclusion.length ? selected.exclusion.map((c, i) => <li key={i}>{c}</li>) : <li>None listed</li>}</ul>
          </>
        ) : <><h2>Trial details</h2><p className="empty">Select a trial to see its criteria.</p></>}
      </section>
    </div>
  );
}
