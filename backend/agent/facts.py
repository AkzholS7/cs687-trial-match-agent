"""Tool 0: read patient facts (age, sex, location, conditions, labs) from a free-text summary."""
import re
from dataclasses import dataclass, field

from .knowledge import VOCAB, NEG_CUES, LABS, ROMAN

_SENT_SPLIT = re.compile(r'(?<=[.;])\s+')


@dataclass
class Facts:
    age: int | None = None
    sex: str | None = None
    city: str | None = None
    state: str | None = None
    labs: dict = field(default_factory=dict)       # lab key -> number
    concepts: dict = field(default_factory=dict)   # concept -> True (present) / False (negated)
    evidence: dict = field(default_factory=dict)   # concept or 'lab:<key>' -> quoted sentence

    def to_dict(self):
        return {'age': self.age, 'sex': self.sex, 'city': self.city, 'state': self.state,
                'labs': self.labs, 'conditions': [k for k, v in self.concepts.items() if v],
                'negated': [k for k, v in self.concepts.items() if not v]}


def sentences(text):
    return _SENT_SPLIT.split(text)


def find_term(text, concept):
    """Return (present, evidence sentence) for the first pattern of a concept found in the text, or None."""
    low = text.lower()
    for pat in VOCAB[concept]:
        idx = low.find(pat)
        if idx != -1:
            s_start = max(low.rfind('.', 0, idx + 1), low.rfind(';', 0, idx + 1)) + 1
            before = low[max(s_start, idx - 60):idx]
            negated = any(c in before for c in NEG_CUES)
            sent = next((s for s in sentences(text) if pat in s.lower()), '')
            return (not negated), sent.strip()
    return None


def extract_facts(text, answers=None):
    """Read facts from the summary; clinician answers override what the text says."""
    answers = answers or {}
    low = text.lower()
    f = Facts()
    m = re.search(r'(\d{1,3})[- ]year[- ]old', low) or re.search(r'\bage[d]?\s*(\d{1,3})', low)
    if m:
        f.age = int(m.group(1))
    if re.search(r'\b(woman|female|she|her)\b', low):
        f.sex = 'Female'
    elif re.search(r'\b(man|male|he|his)\b', low):
        f.sex = 'Male'
    m = re.search(r'(?:[Ll]ives in|[Rr]esides in|[Ll]ocated in)\s+([A-Za-z .]+?),\s*([A-Z]{2})\b', text)
    if m:
        f.city, f.state = m.group(1).strip(), m.group(2)
    for key, (_, pattern) in LABS.items():
        mm = pattern.search(low)
        if mm:
            v = mm.group(1)
            f.labs[key] = ROMAN.get(v) or float(v)
            f.evidence['lab:' + key] = next((s for s in sentences(text) if pattern.search(s.lower())), '').strip()
    for concept in VOCAB:
        r = find_term(text, concept)
        if r is not None:
            f.concepts[concept], f.evidence[concept] = r
    for k, v in (answers.get('labs') or {}).items():
        f.labs[k] = float(v)
        f.evidence['lab:' + k] = 'Clinician answer'
    for k, v in (answers.get('concepts') or {}).items():
        f.concepts[k] = bool(v)
        f.evidence[k] = 'Clinician answer'
    if answers.get('age') is not None:
        f.age = int(answers['age'])
    return f
