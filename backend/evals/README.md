# Market research evaluation

Start the backend, then run the seven-category smoke evaluation:

```powershell
cd backend
.\.venv\Scripts\python.exe evals\runner.py
```

Run every case three times to inspect stability:

```powershell
.\.venv\Scripts\python.exe evals\runner.py --runs 3
```

The runner checks the API contract, required structured output, runtime validation,
latency, citation coverage, cross-source rate, accuracy score, and applicability
score. These automatic scores are screening signals. High-impact market claims still
require source-page and human review because the first implementation extracts data
from search snippets rather than complete source pages.
