"""Unit tests for the agent tools and the orchestrator."""
import json
import os

import pytest

from agent import run_agent
from agent.facts import extract_facts
from agent.checker import parse_range, rule_check, tier1, tier2
from agent.retrieval import bm25_scores, minmax, hybrid_rank

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
TRIALS = json.load(open(os.path.join(DATA, 'sample_trials.json'), encoding='utf-8'))
EXAMPLES = {e['id']: e['summary'] for e in json.load(open(os.path.join(DATA, 'examples.json'), encoding='utf-8'))}


def test_extract_facts_reads_age_sex_location_labs_and_negation():
    f = extract_facts(EXAMPLES['ex1'])
    assert (f.age, f.sex, f.city, f.state) == (62, 'Female', 'Seattle', 'WA')
    assert f.labs['hba1c'] == 8.4 and f.labs['bmi'] == 33
    assert f.concepts['type 2 diabetes'] is True
    assert f.concepts['pancreatitis'] is False      # "No history of pancreatitis"
    assert f.concepts['insulin'] is False           # "Not on insulin"


def test_clinician_answers_override_text():
    f = extract_facts('Patient with diabetes.', {'age': 50, 'labs': {'hba1c': 7.1}, 'concepts': {'pregnancy': False}})
    assert f.age == 50 and f.labs['hba1c'] == 7.1 and f.concepts['pregnancy'] is False


@pytest.mark.parametrize('text,expected', [
    ('hba1c between 7% and 10.5%', (7, 10.5)),
    ('age 18 to 75 years', (18, 75)),
    ('egfr ≥ 30', (30, float('inf'))),
    ('bmi 40 or less', (float('-inf'), 40)),
])
def test_parse_range(text, expected):
    assert parse_range(text) == expected


def test_rule_check_age_and_lab():
    f = extract_facts(EXAMPLES['ex1'])
    assert rule_check('Age 18 to 75 years', f)['res'] == 'yes'
    assert rule_check('HbA1c between 7% and 10.5%', f)['res'] == 'yes'
    assert rule_check('HbA1c between 6% and 7%', f)['res'] == 'no'
    assert rule_check('History of pancreatitis', f) is None        # not structured -> model tier


def test_rule_check_asks_for_missing_lab():
    out = rule_check('LVEF of 40% or less', extract_facts('A 70-year-old man.'))
    assert out['res'] == 'unsure' and out['missing']['key'] == 'lab:ef'


def test_tier1_and_tier2():
    f = extract_facts(EXAMPLES['ex1'])
    assert tier1('History of pancreatitis', f, True)['res'] == 'no'      # negated in text
    assert tier1('Chronic kidney disease', f, True)['res'] == 'unsure'   # not stated
    assert tier2('Chronic kidney disease', f, True)['res'] == 'no'       # inferred from eGFR 75


def test_hybrid_retrieval():
    assert minmax([2, 4, 6]) == [0, 0.5, 1]
    assert minmax([3, 3]) == [0, 0]
    scores = bm25_scores('diabetes metformin', ['type 2 diabetes metformin trial', 'heart failure trial'])
    assert scores[0] > scores[1] == 0
    top = hybrid_rank(EXAMPLES['ex1'], TRIALS, alpha=0.6, top_k=3)
    assert len(top) == 3 and top[0]['fused'] >= top[1]['fused'] >= top[2]['fused']


def test_run_agent_matches_prototype_results():
    """Same results as the JavaScript prototype (checked when the backend was ported)."""
    r = run_agent(EXAMPLES['ex1'], TRIALS)
    assert r['funnel'] == [15, 13, 13, 10]
    assert r['trials'][0]['id'] == 'DEMO-001' and r['trials'][0]['status'] == 'likely_eligible'
    assert r['counts'] == {'likely_eligible': 1, 'needs_review': 1, 'not_eligible': 6}
    assert r['cost']['spent'] == 0.147 and r['cost']['skipped'] == 14
    assert 0 < r['cost']['saving'] < 1
    assert [s['action'].split('(')[0] for s in r['trace']][:3] == ['extract_facts', 'trial_filter', 'hybrid_retrieve']
    assert r['trace'][-1]['action'] == 'finish()'


def test_early_stopping_skips_remaining_criteria():
    r = run_agent(EXAMPLES['ex1'], TRIALS)
    ruled_out = [t for t in r['trials'] if t['status'] == 'not_eligible']
    assert ruled_out and all(t['stopped_by'] for t in ruled_out)
    assert any(c['result'] == 'skip' for t in ruled_out for c in t['criteria'])


def test_zero_budget_means_no_escalation():
    r = run_agent(EXAMPLES['ex3'], TRIALS, {'budget': 0})
    assert r['cost']['escalated'] == 0
    assert all(c['tier'] != 'escalated' for t in r['trials'] for c in t['criteria'])


def test_answering_a_question_changes_the_result():
    before = run_agent(EXAMPLES['ex2'], TRIALS)
    assert before['questions']
    q = before['questions'][0]
    answers = {'criteria': {q['criterion']: False}} if q['kind'] == 'criterion' else \
              {'concepts': {q['concept']: False}} if q['kind'] == 'concept' else {}
    after = run_agent(EXAMPLES['ex2'], TRIALS, answers=answers)
    assert len(after['questions']) < len(before['questions'])


def test_trials_without_status_or_location_are_kept():
    t = {**TRIALS[0], 'id': 'BENCH-1', 'status': None, 'locations': []}
    r = run_agent(EXAMPLES['ex1'], [t])
    assert r['funnel'] == [1, 1, 1, 1]
    assert 'do not report status' in r['trace'][1]['observation']
