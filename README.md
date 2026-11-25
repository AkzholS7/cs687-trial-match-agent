# Trial Match Agent

**An Agentic, Cost-Aware Hybrid System for Clinical Trial Matching: Combining Rule-Based Filtering, Hybrid Retrieval, and Large Language Models**

CS 687 Capstone · City University of Seattle · Akzhol Suborov · Advisor: Prof. Sivakumar Visweswaran

A full-stack web app that matches a patient summary to clinical trials. An agent filters trials, ranks them with hybrid retrieval, checks each eligibility criterion with free rules first and a low-cost model next, escalates only unsure criteria to a stronger model within a budget, stops early when a trial is ruled out, and asks the clinician when facts are missing. The clinician makes the final decision.

## Stack

| Layer | Technology | Folder |
|---|---|---|
| Frontend | React 19 + Vite | `frontend/` |
| Backend | Python 3.10+, Flask REST API | `backend/` |
| Database | SQLite (trials, saved runs, clinician decisions) | `backend/db.py` |
| Agent | Python package (filter, retrieval, checker, orchestrator) | `backend/agent/` |
| Evaluation | Benchmark script on public data | `evaluation/` |

## Architecture

```
React UI (Match · History · Trials · Benchmark)
        │  JSON over HTTP (/api/...)
Flask REST API (app.py) ── SQLite (trials, runs, decisions)
        │
Orchestrator agent (agent/orchestrator.py)
  1. extract_facts     agent/facts.py      age, sex, location, conditions, labs, negation
  2. trial_filter      orchestrator.py     status, age, sex, location (no model cost)
  3. hybrid_retrieve   agent/retrieval.py  BM25 + TF-IDF, convex fusion with weight α
  4. check_criteria    agent/checker.py    rule check → low-cost check → escalation (budget), early stopping
  5. ask_clinician     agent/checker.py    questions for missing facts
  6. finish            trace + cost estimate
```

## Run it in GitHub Codespaces

The repo includes `.devcontainer/`, so a new Codespace installs everything. Otherwise run the install lines below.

**Terminal 1: backend**
```bash
cd backend
pip install -r requirements.txt
python app.py                  # API on http://localhost:5000
```

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev                    # app on http://localhost:5173 (calls /api on port 5000)
```
Open the forwarded port **5173**.

**One server instead of two:** run `npm run build` in `frontend/`, then `python app.py` serves the built app and the API on port 5000.

### Load real benchmark trials (optional)
```bash
cd backend
git clone https://github.com/ncbi-nlp/TrialGPT
python load_benchmark.py TrialGPT/dataset     # adds the SIGIR collection: 3,621 trials + example patients
```
Restart `python app.py`, then choose "Benchmark: SIGIR" on the Match page.

### Use real language models (optional, experimental)
```bash
export ANTHROPIC_API_KEY=...   # then choose "LLM" as the checker on the Match page
```
Without a key, a rule-based checker stands in for both model tiers, so the app runs fully offline.

## Tests
```bash
cd backend
python -m pytest               # 30 tests: agent tools, orchestrator, API, database
```

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status and trial collections |
| GET | `/api/examples` | Example patients |
| GET | `/api/trials?collection=&q=&offset=&limit=` | Search trials |
| GET | `/api/trials/<collection>/<id>` | One trial |
| POST | `/api/match` | Run the agent `{summary, collection, settings, answers, save}` |
| GET | `/api/runs` · `/api/runs/<id>` | Saved runs |
| DELETE | `/api/runs/<id>` | Delete a run (and its decisions) |
| PUT / DELETE | `/api/runs/<id>/decisions/<trial_id>` | Save or clear an accept/reject decision |
| GET | `/api/stats` | Totals across runs |
| GET | `/api/benchmark` | Benchmark results for the charts |

## Benchmark results (retrieval stage)

`evaluation/run_baselines.py` uses the public TrialGPT dataset (Jin et al., 2024). On SIGIR full retrieval, the hybrid score reaches NDCG@10 0.149 at α = 0.4, compared with 0.130 for BM25 alone and 0.129 for TF-IDF alone. When re-ranking candidate trials that are already similar to the patient, similarity alone does worse than random order. In other words, similarity is not eligibility, which is why the agent checks each criterion.

## Data and safety

- `DEMO-xxx` trials and example patients are synthetic. Benchmark data is public and de-identified.
- Do not enter real patient data. The app is a research prototype, not a medical device.
- The agent only suggests matches. The clinician decides.

## Acknowledgment

I built this project with help from an AI assistant (Claude, Anthropic) for code generation and review. I reviewed, ran, and tested the code, and I can explain every part of it.

## References

- Jin, Q., Wang, Z., Floudas, C. S., et al. (2024). Matching patients to clinical trials with large language models. *Nature Communications, 15*, 9074. https://doi.org/10.1038/s41467-024-53081-z
- Yao, S., Zhao, J., Yu, D., et al. (2023). ReAct: Synergizing reasoning and acting in language models. *ICLR 2023*. https://arxiv.org/abs/2210.03629
