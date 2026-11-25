"""SQLite storage: trials (by collection), saved agent runs, and clinician decisions."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get('TRIAL_DB', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trialmatch.db'))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    id TEXT NOT NULL,
    collection TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT,
    sex TEXT NOT NULL DEFAULT 'All',
    min_age REAL,
    max_age REAL,
    conditions TEXT NOT NULL DEFAULT '[]',
    locations TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    inclusion TEXT NOT NULL DEFAULT '[]',
    exclusion TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (collection, id)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    patient_summary TEXT NOT NULL,
    collection TEXT NOT NULL,
    settings TEXT NOT NULL,
    answers TEXT NOT NULL,
    result TEXT NOT NULL,
    likely_eligible INTEGER NOT NULL,
    needs_review INTEGER NOT NULL,
    not_eligible INTEGER NOT NULL,
    cost_spent REAL NOT NULL,
    cost_saving REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    trial_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (run_id, trial_id)
);
"""
JSON_COLS = ('conditions', 'locations', 'inclusion', 'exclusion')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM trials WHERE collection = 'demo' LIMIT 1").fetchone():
        with open(os.path.join(DATA_DIR, 'sample_trials.json'), encoding='utf-8') as f:
            insert_trials(conn, 'demo', json.load(f))
    conn.commit()


def insert_trials(conn, collection, trials):
    conn.executemany(
        'INSERT OR REPLACE INTO trials (id, collection, title, status, sex, min_age, max_age, conditions, locations, summary, inclusion, exclusion) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [(t['id'], collection, t['title'], t.get('status'), t.get('sex') or 'All', t.get('min_age'), t.get('max_age'),
          *(json.dumps(t.get(c) or []) for c in ('conditions', 'locations')), t.get('summary') or '',
          json.dumps(t.get('inclusion') or []), json.dumps(t.get('exclusion') or [])) for t in trials])


def _trial(row):
    t = dict(row)
    for c in JSON_COLS:
        t[c] = json.loads(t[c])
    return t


def collections(conn):
    return [dict(r) for r in conn.execute('SELECT collection AS name, COUNT(*) AS trials FROM trials GROUP BY collection ORDER BY collection')]


def get_trials(conn, collection):
    return [_trial(r) for r in conn.execute('SELECT * FROM trials WHERE collection = ? ORDER BY id', (collection,))]


def search_trials(conn, collection, q='', limit=20, offset=0):
    where, args = 'collection = ?', [collection]
    if q:
        where += ' AND (id LIKE ? OR title LIKE ? OR conditions LIKE ?)'
        args += [f'%{q}%'] * 3
    total = conn.execute(f'SELECT COUNT(*) FROM trials WHERE {where}', args).fetchone()[0]
    rows = conn.execute(f'SELECT * FROM trials WHERE {where} ORDER BY id LIMIT ? OFFSET ?', args + [limit, offset])
    return total, [_trial(r) for r in rows]


def get_trial(conn, collection, trial_id):
    r = conn.execute('SELECT * FROM trials WHERE collection = ? AND id = ?', (collection, trial_id)).fetchone()
    return _trial(r) if r else None


def save_run(conn, summary, collection, settings, answers, result):
    cur = conn.execute(
        'INSERT INTO runs (created_at, patient_summary, collection, settings, answers, result, likely_eligible, needs_review, not_eligible, cost_spent, cost_saving) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (now(), summary, collection, json.dumps(settings), json.dumps(answers), json.dumps(result),
         result['counts']['likely_eligible'], result['counts']['needs_review'], result['counts']['not_eligible'],
         result['cost']['spent'], result['cost']['saving']))
    conn.commit()
    return cur.lastrowid


def list_runs(conn, limit=50):
    rows = conn.execute('SELECT r.id, r.created_at, r.patient_summary, r.collection, r.likely_eligible, r.needs_review, r.not_eligible, '
                        'r.cost_spent, r.cost_saving, (SELECT COUNT(*) FROM decisions d WHERE d.run_id = r.id) AS decisions '
                        'FROM runs r ORDER BY r.id DESC LIMIT ?', (limit,))
    return [dict(r) for r in rows]


def get_run(conn, run_id):
    r = conn.execute('SELECT * FROM runs WHERE id = ?', (run_id,)).fetchone()
    if not r:
        return None
    run = dict(r)
    for c in ('settings', 'answers', 'result'):
        run[c] = json.loads(run[c])
    run['decisions'] = get_decisions(conn, run_id)
    return run


def delete_run(conn, run_id):
    n = conn.execute('DELETE FROM runs WHERE id = ?', (run_id,)).rowcount
    conn.commit()
    return n > 0


def get_decisions(conn, run_id):
    return {r['trial_id']: {'decision': r['decision'], 'note': r['note'], 'created_at': r['created_at']}
            for r in conn.execute('SELECT * FROM decisions WHERE run_id = ?', (run_id,))}


def set_decision(conn, run_id, trial_id, decision, note=''):
    conn.execute('INSERT INTO decisions (run_id, trial_id, decision, note, created_at) VALUES (?, ?, ?, ?, ?) '
                 'ON CONFLICT (run_id, trial_id) DO UPDATE SET decision = excluded.decision, note = excluded.note, created_at = excluded.created_at',
                 (run_id, trial_id, decision, note, now()))
    conn.commit()


def clear_decision(conn, run_id, trial_id):
    conn.execute('DELETE FROM decisions WHERE run_id = ? AND trial_id = ?', (run_id, trial_id))
    conn.commit()


def stats(conn):
    r = conn.execute('SELECT COUNT(*) AS runs, AVG(cost_saving) AS avg_saving, SUM(likely_eligible) AS likely, SUM(needs_review) AS review FROM runs').fetchone()
    d = conn.execute("SELECT SUM(decision = 'accept') AS accepted, SUM(decision = 'reject') AS rejected FROM decisions").fetchone()
    return {'runs': r['runs'], 'avg_saving': round(r['avg_saving'] or 0, 4), 'likely_eligible': r['likely'] or 0,
            'needs_review': r['review'] or 0, 'accepted': d['accepted'] or 0, 'rejected': d['rejected'] or 0}
