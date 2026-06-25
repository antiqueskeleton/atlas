# Atlas AI v0.2

Atlas AI is a starter AI market intelligence platform for tracking how AI models discuss portable power brands, competitors, features, buying scenarios, and market questions.

## What v0.2 adds

- Atlas Intelligence Library data model
- Personas
- Buying stages
- Prompt families
- Market Questions with three prompt styles:
  - search
  - natural
  - conversational
- Prompt Influence Score metadata
- Local Admin Console for reviewing/editing/exporting the library

## Quick start

From the `atlas-ai` folder:

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

## Key files

```text
data/personas.csv
data/buying_stages.csv
data/prompt_families.csv
data/market_questions.csv
frontend/admin.html
frontend/dashboard.html
backend/load_ail_data.py
```

## Current limitations

This version still uses sample/manual responses. The next major step is adding a response collection workflow so real AI responses can be pasted, imported, or collected through APIs.

## Next engineering steps

1. Add manual response entry screen.
2. Let users select Market Questions for a test run.
3. Add prompt style reporting: search vs natural vs conversational.
4. Improve dashboard around personas and buying stages.
5. Add API-based AI runners later.
