# LangGraph Agent Starter

This project is a small research agent system built with:

- FastAPI
- LangGraph
- Next.js
- Skill Loader
- Search Tool
- Markdown report generation with normalized formatting
- Planner Agent
- Report Scoring Agent

Current workflow:

```text
User Input
  -> prepare_context
  -> planner_node
  -> research_agent
  -> search_tool
  -> evidence
  -> metric_extractor
  -> market_analysis
  -> report
  -> validation_agent
  -> scorer
  -> output
```

The backend now normalizes the generated report into stable Markdown, and the
frontend renders headings, lists, links, quotes, tables, and inline code so the
output is easier to read.

## Directory

```text
backend/   FastAPI + LangGraph backend
frontend/  Next.js frontend
skills/    Skill definitions, including SKILL.md
tools/     Project tools, such as web search
```

## Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000 --env-file .env
```

Open the API docs at:

```text
http://localhost:8000/docs
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## API Contract

`POST /api/agent`

Request:

```json
{
  "message": "Analyze the robot vision sensor market",
  "research_type": "market_size"
}
```

Response:

```json
{
  "answer": "markdown report",
  "research": "markdown report",
  "research_type": "market_size",
  "metrics": [],
  "calculated_metrics": [],
  "time_series": [],
  "competitors": [],
  "warnings": [],
  "validation": {
    "accuracy_score": 0,
    "applicability_score": 0,
    "citation_coverage": 0,
    "cross_source_rate": 0,
    "status": "warning",
    "applicability": "scope statement",
    "claims": [],
    "warnings": []
  },
  "score": {
    "score": 88,
    "dimension_scores": {
      "coverage": 90
    },
    "issues": [],
    "improvement_suggestions": [],
    "pass_or_fail": "pass"
  }
}
```

`score` is optional in the API response, but it is now exposed when the graph
produces a score payload.

Supported `research_type` values are `comprehensive`, `market_size`,
`competitor`, `product_price`, `customer_demand`, `supply_chain`, and
`market_entry`. Requests containing only `message` remain valid.

## Market Data Validation

The backend extracts traceable numeric metrics, calculates CAGR in deterministic
Python code, and checks citation coverage, numeric presence in collected evidence,
cross-source agreement, and applicability scope. The first implementation uses
search snippets, so the UI explicitly warns that its score is not a full-page or
human fact check.

With the API running, execute the reusable seven-category evaluation suite:

```bash
cd backend
.\.venv\Scripts\python.exe evals\runner.py --runs 3
```

## Skill Loader

`backend/app/skill_loader.py` loads `skills/<skill_name>/SKILL.md` verbatim.
The application uses the installable `company-research` skill as its research-method source of truth.

## Testing

Run the test suite:

```bash
cd backend
.\.venv\Scripts\activate
python -m unittest discover -s tests -v
```

To run a single test module from the `backend` directory, use:

```bash
python -m unittest tests.test_api_contract -v
python -m unittest tests.test_graph_flow -v
```

Useful tests:

- `backend/tests/test_api_contract.py` checks the API shape and score field
- `backend/tests/test_planner.py` checks structured planning and fallback
- `backend/tests/test_graph_flow.py` checks graph connectivity
- `backend/tests/test_scorer.py` checks the default score fallback

## Markdown Formatting Notes

If the report looks unformatted, check these two layers first:

1. Backend report cleanup in `backend/app/report_format.py`
2. Frontend Markdown rendering in `frontend/app/page.tsx`

The API returns plain Markdown text in `answer` and `research`, not HTML.

## Notes

- The API still returns `answer` and `research` for backward compatibility.
- The scoring result is now surfaced as `score`.
- The report generation flow still works even when external APIs fail, because
  the graph has fallback logic.
