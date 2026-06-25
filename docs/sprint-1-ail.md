# Sprint 1 — Atlas Intelligence Library

Sprint 1 converts Atlas from a simple response dashboard into a structured market intelligence system.

## Core idea

Atlas should not only track prompts. It should track **Market Questions** connected to personas, buying stages, scenarios, topics, and business value.

Each Market Question has three prompt styles:

1. **Search** — Google-style keyword behavior.
2. **Natural** — clean sentence-style AI behavior.
3. **Conversational** — detailed real-life customer behavior.

## New files

- `data/personas.csv`
- `data/buying_stages.csv`
- `data/prompt_families.csv`
- `data/market_questions.csv`
- `backend/load_ail_data.py`
- `frontend/admin.html`

## Admin Console

Open:

```text
frontend/admin.html
```

Use it to review, search, edit, add, and export personas and Market Questions. It saves edits in browser localStorage and can export JSON or CSV.

## Load Sprint 1 data

From the project folder:

```bash
python backend/init_db.py
python backend/load_ail_data.py
python backend/load_sample_responses.py
python backend/analyze_responses.py
python backend/generate_report.py
```

Then open:

```text
frontend/admin.html
frontend/dashboard.html
```
