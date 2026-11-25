"""Optional hook for real language models (experimental).

By default the agent uses the rule-based checker in checker.py, which needs no API key. If the setting
use_llm is true and the environment variable ANTHROPIC_API_KEY is set, tier 1 uses a low-cost model and
tier 2 a stronger model through the Anthropic Messages API. Any error falls back to the rule-based checker.
Model names can be changed with the environment variables LLM_LOW_MODEL and LLM_STRONG_MODEL.
"""
import json
import os

from .checker import tier1 as rule_tier1, tier2 as rule_tier2

API_URL = 'https://api.anthropic.com/v1/messages'
LOW_MODEL = os.environ.get('LLM_LOW_MODEL', 'claude-haiku-5-5')
STRONG_MODEL = os.environ.get('LLM_STRONG_MODEL', 'claude-sonnet-5-5')

PROMPT = """You check one clinical trial eligibility criterion against a patient's facts.
Criterion type: {kind}
Criterion: {criterion}
Patient facts: {facts}
Answer with JSON only: {{"result": "yes" | "no" | "unsure", "evidence": "<short quote or reason>"}}.
For an inclusion criterion, "yes" means the patient meets it. For an exclusion criterion, "yes" means it applies.
Say "unsure" when the facts do not say."""


def _ask(model, criterion, f, is_excl):
    import requests  # imported here so the app runs without it when LLMs are off
    facts = {'age': f.age, 'sex': f.sex, 'labs': f.labs, 'conditions': f.concepts, 'evidence': f.evidence}
    body = {'model': model, 'max_tokens': 200,
            'messages': [{'role': 'user', 'content': PROMPT.format(kind='exclusion' if is_excl else 'inclusion', criterion=criterion, facts=json.dumps(facts))}]}
    headers = {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
    resp = requests.post(API_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    text = resp.json()['content'][0]['text']
    data = json.loads(text[text.index('{'):text.rindex('}') + 1])
    res = data.get('result', 'unsure')
    return {'res': res if res in ('yes', 'no', 'unsure') else 'unsure', 'ev': f"{model}: {data.get('evidence', '')}"}


def _wrap(model, fallback):
    def check(criterion, f, is_excl):
        try:
            return _ask(model, criterion, f, is_excl)
        except Exception as e:  # network, key, or parsing problem: use the rule-based checker instead
            out = fallback(criterion, f, is_excl)
            out['ev'] = f'{out["ev"]} (LLM unavailable: {type(e).__name__})'
            return out
    return check


def checkers(use_llm):
    """Return (tier1, tier2, mode label)."""
    if use_llm and os.environ.get('ANTHROPIC_API_KEY'):
        return _wrap(LOW_MODEL, rule_tier1), _wrap(STRONG_MODEL, rule_tier2), 'llm'
    return rule_tier1, rule_tier2, 'rule-based'
