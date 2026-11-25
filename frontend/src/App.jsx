// App.jsx: page layout, navigation between pages (hash-based), and backend connection status.
import { useEffect, useState } from 'react';
import { api } from './api.js';
import MatchPage from './pages/MatchPage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';
import TrialsPage from './pages/TrialsPage.jsx';
import BenchmarkPage from './pages/BenchmarkPage.jsx';

const PAGES = [['match', 'Match'], ['history', 'History'], ['trials', 'Trials'], ['benchmark', 'Benchmark']];
const current = () => (PAGES.some(([k]) => `#/${k}` === window.location.hash) ? window.location.hash.slice(2) : 'match');

export default function App() {
  const [page, setPage] = useState(current);
  const [collections, setCollections] = useState([{ name: 'demo', trials: 15 }]);
  const [online, setOnline] = useState(null);

  useEffect(() => {
    const onHash = () => setPage(current());
    window.addEventListener('hashchange', onHash);
    api.health().then((h) => { setOnline(true); setCollections(h.collections); }).catch(() => setOnline(false));
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  return (
    <div className="wrap">
      <header>
        <div>
          <h1>Trial Match Agent</h1>
          <p className="sub">Agentic, cost-aware clinical trial matching · CS 687 capstone · Akzhol Suborov</p>
        </div>
        <div className="chips">
          <span className={`chip ${online === false ? 'bad' : ''}`}>{online === null ? 'Connecting…' : online ? 'Backend connected' : 'Backend offline'}</span>
          <span className="chip">React · Flask · SQLite</span>
          <span className="chip warn">Clinician makes every decision</span>
        </div>
      </header>
      <nav className="tabs" aria-label="Pages">
        {PAGES.map(([k, label]) => (
          <a key={k} href={`#/${k}`} aria-current={page === k ? 'page' : undefined}>{label}</a>
        ))}
      </nav>
      {online === false && <p className="error" role="alert">Cannot reach the backend. Start it with <code>python app.py</code> in the backend folder.</p>}
      {page === 'match' && <MatchPage collections={collections} />}
      {page === 'history' && <HistoryPage />}
      {page === 'trials' && <TrialsPage collections={collections} />}
      {page === 'benchmark' && <BenchmarkPage />}
      <footer>
        Research prototype for demonstration only. It uses synthetic sample trials (IDs start with DEMO), public benchmark data, and
        example patients; do not enter real patient data. It only suggests matches: final eligibility decisions belong to the clinician.
      </footer>
    </div>
  );
}
