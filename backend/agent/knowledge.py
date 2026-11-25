"""Medical vocabulary and lab patterns used by the fact extractor and the criterion checker."""
import json
import os
import re

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

with open(os.path.join(_DATA, 'vocabulary.json'), encoding='utf-8') as f:
    VOCAB = json.load(f)  # concept -> list of text patterns, in a fixed order

# Words that mark a concept as absent when they appear shortly before it ("No history of pancreatitis").
NEG_CUES = ['no history of', 'no evidence of', 'negative for', 'denies', 'without', 'not on', 'no ', 'never had', 'free of']

# Lab values the agent can read from text: key -> (display name, pattern on lowercase text).
LABS = {
    'hba1c': ('HbA1c (%)', re.compile(r'(?:hba1c|a1c)\s*(?:of|was|is|=|:)?\s*(\d+(?:\.\d+)?)')),
    'egfr': ('eGFR (mL/min/1.73m2)', re.compile(r'\begfr\s*(?:of|was|is|=|:)?\s*(\d{1,3})\b')),
    'ef': ('Ejection fraction (%)', re.compile(r'(?:ejection fraction|lvef|\bef)\s*(?:of|was|is|=|:)?\s*(\d{1,2})\s*%')),
    'bmi': ('BMI (kg/m2)', re.compile(r'\bbmi\s*(?:of|was|is|=|:)?\s*(\d{2}(?:\.\d+)?)')),
    'ecog': ('ECOG status (0-4)', re.compile(r'\becog(?: performance status)?\s*(?:of|was|is|=|:)?\s*([0-4])\b')),
    'potassium': ('Potassium (mmol/L)', re.compile(r'potassium\s*(?:of|was|is|=|:)?\s*(\d(?:\.\d+)?)')),
    'nyha': ('NYHA class (1-4)', re.compile(r'nyha(?: functional)?(?: class)?\s*(iv|iii|ii|i|[1-4])\b')),
    'pdl1': ('PD-L1 expression (%)', re.compile(r'pd-?l1[^0-9]{0,15}(\d{1,3})\s*%')),
}
ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}

DIAGNOSES = {'type 2 diabetes', 'type 1 diabetes', 'prediabetes', 'chronic kidney disease', 'heart failure',
             'atrial fibrillation', 'hypertension', 'non-small cell lung cancer', 'breast cancer', 'asthma', 'copd',
             'major depressive disorder', 'obesity'}
MEDS = {'metformin', 'insulin', 'osimertinib'}


def lab_name(key):
    return LABS[key][0]


def lab_short(key):
    return LABS[key][0].split(' (')[0]
