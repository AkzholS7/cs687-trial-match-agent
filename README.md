# Trial Match Agent

Prototype of an agentic, cost-aware hybrid system for clinical trial matching.
CS 687 Computer Science Capstone, City University of Seattle, Fall 2026. Author: Akzhol Suborov.

The agent filters trials by rules, ranks them with hybrid search, checks each eligibility
criterion with free rules and a low-cost model, escalates only unsure criteria to a stronger
model, and asks the clinician when a fact is missing. A clinician makes every final decision.

![Architecture](docs/architecture.png)

## Files

| File | What it does |
|---|---|
| `index.html` | Page layout; loads the style and scripts |
| `style.css` | Colors, fonts, and layout |
| `js/data.js` | Sample trials, example patients, medical vocabulary |
| `js/facts.js` | Reads age, sex, location, conditions, and labs from the patient text |
| `js/retrieval.js` | Hybrid retriever: BM25 + TF-IDF vectors with convex fusion |
| `js/checker.js` | Rule checks, low-cost check (tier 1), escalation (tier 2), clinician questions |
| `js/agent.js` | Orchestrator: filter, retrieve, check, early stopping, budget, trace |
| `js/app.js` | User interface: results, questions, decisions, trace |

## Run it

In GitHub Codespaces or any terminal, from this folder:

```
python3 -m http.server 8000
```

Then open the forwarded port 8000 in the browser. Or simply open `index.html` in a browser.

## Status

- Working prototype of the agent loop with a clinician view and an agent trace
- Uses 15 synthetic sample trials (IDs start with `DEMO`) and example patients, not real data
- A rule-based checker stands in for the low-cost and strong LLMs; costs are estimates
- Next: TREC 2021/2022 and SIGIR 2016 data, ClinicalTrials.gov API, real LLMs, evaluation

## How this was built

The system design comes from my capstone papers (Weeks 3 to 5). This first prototype was built
with the help of an AI coding assistant (Claude); I reviewed, ran, and modified the code, and I
am extending it in the following sprints.

## Data and ethics

Only public, de-identified, or synthetic data is used. The system only suggests matches;
clinicians make all eligibility decisions.