"""Load real benchmark trials (and patients) from the TrialGPT dataset into the database.

Usage:
    git clone https://github.com/ncbi-nlp/TrialGPT
    python load_benchmark.py TrialGPT/dataset            # loads the SIGIR collection (3,620 trials, 58 patients)

The SIGIR corpus does not record recruiting status, sex limits or locations, so those fields stay empty
and the agent's filter keeps such trials (it says so in the trace). Age limits are read from the criteria
text when a clear "between X and Y years" style rule exists.
"""
import json
import os
import re
import sys

import db
from agent.checker import parse_range

MAX_CRITERIA = 12


def split_criteria(text, header):
    text = re.sub(r'^\s*' + header + r'\s*:?', '', text or '', flags=re.I)
    items = [re.sub(r'^\s*[-*•\d.)]+\s*', '', x).strip() for x in re.split(r'\n\s*\n|\n\s*[-*•]\s+', text)]
    return [x for x in items if len(x) > 8 and not x.endswith(':')][:MAX_CRITERIA]


def age_limits(criteria):
    for c in criteria:
        low = c.lower()
        if re.search(r'\bage[d]?\b|years of age|years old', low):
            r = parse_range(low)
            if r and (r[0] != float('-inf') or r[1] != float('inf')):
                lo = None if r[0] == float('-inf') else round(r[0])
                hi = None if r[1] == float('inf') else round(r[1])
                if (lo is None or 0 <= lo < 120) and (hi is None or 0 < hi <= 120):
                    return lo, hi
    return None, None


def convert(rec):
    md = rec.get('metadata') or {}
    inc = split_criteria(md.get('inclusion_criteria', ''), 'inclusion criteria')
    exc = split_criteria(md.get('exclusion_criteria', ''), 'exclusion criteria')
    lo, hi = age_limits(inc)
    summary = rec.get('text', '').split('\n')[0].replace('Summary:', '').strip()
    return {'id': rec['_id'], 'title': md.get('brief_title') or rec.get('title', ''), 'status': None, 'sex': 'All',
            'min_age': lo, 'max_age': hi, 'conditions': md.get('diseases_list') or [], 'locations': [],
            'summary': summary, 'inclusion': inc, 'exclusion': exc}


def main(dataset_dir, name='sigir'):
    folder = os.path.join(dataset_dir, name)
    with open(os.path.join(folder, 'corpus.jsonl'), encoding='utf-8') as f:
        trials = [convert(json.loads(line)) for line in f if line.strip()]
    with open(os.path.join(folder, 'queries.jsonl'), encoding='utf-8') as f:
        patients = [json.loads(line) for line in f if line.strip()]
    conn = db.connect()
    db.init(conn)
    db.insert_trials(conn, name, trials)
    conn.commit()
    out = os.path.join(db.DATA_DIR, f'{name}_patients.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump([{'id': p['_id'], 'label': p['_id'], 'summary': p['text']} for p in patients], f, indent=1)
    print(f'Loaded {len(trials)} trials into collection "{name}" and wrote {len(patients)} patients to {out}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'sigir')
