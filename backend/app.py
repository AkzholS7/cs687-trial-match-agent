"""REST API for the Trial Match Agent (Flask + SQLite).

Run:  python app.py            -> http://localhost:5000  (API under /api, React build served at /)
"""
import json
import os

from flask import Flask, g, jsonify, request, send_from_directory, abort

import db
from agent import run_agent, DEFAULTS

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'dist')
MAX_SUMMARY = 5000
SETTING_LIMITS = {'top_k': (1, 20), 'alpha': (0.0, 1.0), 'budget': (0.0, 5.0), 'price_low': (0.0, 1.0), 'price_strong': (0.0, 1.0)}


def create_app(db_path=None):
    app = Flask(__name__, static_folder=None)
    app.config['DB_PATH'] = db_path or db.DB_PATH
    with db.connect(app.config['DB_PATH']) as conn:
        db.init(conn)

    def conn():
        if 'conn' not in g:
            g.conn = db.connect(app.config['DB_PATH'])
        return g.conn

    @app.teardown_appcontext
    def close(_exc):
        c = g.pop('conn', None)
        if c is not None:
            c.close()

    def bad(msg, code=400):
        return jsonify({'error': msg}), code

    def read_json(name):
        path = os.path.join(db.DATA_DIR, name)
        if not os.path.exists(path):
            return None
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    # ---------- reference data ----------
    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok', 'collections': db.collections(conn())})

    @app.get('/api/examples')
    def examples():
        out = [{**e, 'collection': 'demo'} for e in read_json('examples.json')]
        for c in db.collections(conn()):
            pts = read_json(f"{c['name']}_patients.json")
            if pts:
                out += [{**p, 'collection': c['name']} for p in pts[:10]]
        return jsonify(out)

    @app.get('/api/collections')
    def list_collections():
        return jsonify(db.collections(conn()))

    @app.get('/api/trials')
    def trials():
        coll = request.args.get('collection', 'demo')
        try:
            limit = min(max(int(request.args.get('limit', 20)), 1), 100)
            offset = max(int(request.args.get('offset', 0)), 0)
        except ValueError:
            return bad('limit and offset must be integers')
        total, items = db.search_trials(conn(), coll, request.args.get('q', '').strip(), limit, offset)
        return jsonify({'total': total, 'items': items})

    @app.get('/api/trials/<collection>/<trial_id>')
    def trial(collection, trial_id):
        t = db.get_trial(conn(), collection, trial_id)
        return jsonify(t) if t else bad('Trial not found', 404)

    @app.get('/api/benchmark')
    def benchmark():
        data = read_json('benchmark_results.json')
        return jsonify(data) if data else bad('No benchmark results yet', 404)

    # ---------- agent ----------
    @app.post('/api/match')
    def match():
        body = request.get_json(silent=True) or {}
        summary = (body.get('summary') or '').strip()
        if not summary:
            return bad('Patient summary is required')
        if len(summary) > MAX_SUMMARY:
            return bad(f'Patient summary is too long (max {MAX_SUMMARY} characters)')
        coll = body.get('collection', 'demo')
        trials = db.get_trials(conn(), coll)
        if not trials:
            return bad(f'Unknown or empty collection: {coll}', 404)
        settings = {}
        for k, v in (body.get('settings') or {}).items():
            if k == 'use_llm':
                settings[k] = bool(v)
            elif k in SETTING_LIMITS:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    return bad(f'Setting {k} must be a number')
                lo, hi = SETTING_LIMITS[k]
                if not lo <= v <= hi:
                    return bad(f'Setting {k} must be between {lo} and {hi}')
                settings[k] = v
        answers = body.get('answers') or {}
        if not isinstance(answers, dict):
            return bad('answers must be an object')
        try:
            result = run_agent(summary, trials, settings, answers)
        except (ValueError, TypeError) as e:
            return bad(f'Could not use the clinician answers: {e}')
        if body.get('save', True):
            result['run_id'] = db.save_run(conn(), summary, coll, result['settings'], answers, result)
        return jsonify(result)

    # ---------- history and decisions ----------
    @app.get('/api/runs')
    def runs():
        return jsonify(db.list_runs(conn()))

    @app.get('/api/runs/<int:run_id>')
    def run(run_id):
        r = db.get_run(conn(), run_id)
        return jsonify(r) if r else bad('Run not found', 404)

    @app.delete('/api/runs/<int:run_id>')
    def remove_run(run_id):
        return ('', 204) if db.delete_run(conn(), run_id) else bad('Run not found', 404)

    @app.put('/api/runs/<int:run_id>/decisions/<trial_id>')
    def decide(run_id, trial_id):
        r = db.get_run(conn(), run_id)
        if not r:
            return bad('Run not found', 404)
        if trial_id not in {t['id'] for t in r['result']['trials']}:
            return bad('Trial is not part of this run', 404)
        body = request.get_json(silent=True) or {}
        if body.get('decision') not in ('accept', 'reject'):
            return bad('decision must be "accept" or "reject"')
        db.set_decision(conn(), run_id, trial_id, body['decision'], str(body.get('note', ''))[:500])
        return jsonify(db.get_decisions(conn(), run_id))

    @app.delete('/api/runs/<int:run_id>/decisions/<trial_id>')
    def undecide(run_id, trial_id):
        db.clear_decision(conn(), run_id, trial_id)
        return jsonify(db.get_decisions(conn(), run_id))

    @app.get('/api/stats')
    def stats():
        return jsonify(db.stats(conn()))

    @app.get('/api/settings/defaults')
    def defaults():
        return jsonify(DEFAULTS)

    # ---------- React build ----------
    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        if path.startswith('api/'):
            abort(404)
        if not os.path.isdir(FRONTEND_DIST):
            return ('Frontend not built yet. Run "npm run build" in frontend/, or use "npm run dev" (port 5173).', 200)
        full = os.path.join(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, path if os.path.isfile(full) else 'index.html')

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
