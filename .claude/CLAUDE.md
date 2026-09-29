# London Postcode Finder — Claude Code Instructions

Full project plan: @PROJECT.md

---

## What This Project Is

A web app that recommends London postcode districts based on a user's lifestyle priorities. Users allocate 100 tokens across 5 dimensions (safety, green space, nightlife, transport, rent) and optionally add natural language context. A multi-agent LangGraph system scores all 40 districts via free public APIs, then Claude synthesises the top 5 recommendations with rationale.

---

## Repository and Branch Rules

- **Never commit directly to `main` or `dev`**
- All work goes on `feature/US-XXX-short-name` branches cut from `dev`
- PRs always target `dev`, never `main`
- Every PR must close a GitHub Issue: include `Closes #N` in the PR body
- Commit format: `feat:`, `fix:`, `chore:`, `test:`, `refactor:` + short description

---

## Project Structure

```
/agents         — one scorer per file (crime_scorer.py, green_scorer.py, ...)
/tools          — shared utilities (postcode.py coordinates via postcodes.io)
/data           — ONS rent CSV (not committed)
/prompts        — Claude system prompt .md files
/supabase       — migrations only, managed by Supabase CLI
/frontend       — Next.js app (not yet built)
/tests          — pytest files, one per agent/tool
config.py       — env vars + LONDON_POSTCODE_DISTRICTS (40 districts) + SCORING_DIMENSIONS
```

---

## The 40 Postcode Districts

Defined in `config.py` as `LONDON_POSTCODE_DISTRICTS`. Always 40 entries. Tests assert `len(results) == 40`. Never hardcode this list in agents — always import from config.

---

## Scorer Conventions

Every scorer in `/agents` follows this exact pattern — do not deviate:

**Function signatures:**
```python
async def score_all_postcodes() -> list[dict]
async def score_single_postcode(district: str) -> dict
```

**Return shape:**
```python
{"district": "E1", "raw_count": 12, "score": 0.65}
```

**Normalisation:**
- Green space / nightlife / transport: higher raw = higher score → `(count - min) / (max - min)`
- Crime / rent: higher raw = lower score → `1 - (count - min) / (max - min)`
- If `max == min`: return `score = 0.5` for all districts
- `score_single_postcode` always returns `score = 0.5` (placeholder — normalisation needs all districts)

**Batching:** process coordinates in small batches with `asyncio.sleep` between batches to respect free API rate limits. Current settings per scorer vary — check the file before changing.

**Error handling:**
- API unreachable → `raise RuntimeError("Could not reach <API name>: ...")`
- Empty or missing result → use `raw_count = 0` (never raise)
- Use `timeout=30.0` for slow APIs (Overpass), `timeout=10.0` for fast ones (postcodes.io)

**Type hints:** use `Optional[str]` from `typing`, not `str | None` (Python 3.9 compatibility)

**Imports:** always use `from tools.postcode import get_all_postcode_coordinates`

---

## External APIs Used

| API | Base URL | Auth | Notes |
|---|---|---|---|
| postcodes.io | `https://api.postcodes.io` | None | Validates districts, returns lat/lng |
| UK Police | `https://data.police.uk/api/crimes-street/all-crime` | None | Requires `date=YYYY-MM` param |
| Overpass (OSM) | `https://overpass-api.de/api/interpreter` | None | POST with `data=<query>`, slow — use 30s timeout |
| TfL | TBD | `TFL_APP_KEY` env var | Not yet implemented |
| ONS (rent) | CSV loaded via Supabase migration | None | Borough-to-district mapping in `/data` |

---

## Testing Conventions

- All async tests use `@pytest.mark.asyncio`
- Tests live in `/tests/test_<module_name>.py`
- Each scorer has three standard tests:
  1. `score_all_postcodes` returns exactly 40 dicts
  2. All scores are between 0.0 and 1.0 inclusive
  3. `score_single_postcode("E1")` returns a dict with keys `district`, `raw_count`, `score`
- Run tests: `python -m pytest tests/ -v` (activate `.venv` first)

---

## Environment Variables

Defined in `.env` (never committed). See `.env.example` for all keys.

```
ANTHROPIC_API_KEY    — Anthropic Console
TFL_APP_KEY          — api.tfl.gov.uk
SUPABASE_URL         — Supabase project settings → API
SUPABASE_KEY         — Supabase project settings → API (anon public)
GROQ_API_KEY         — optional, console.groq.com
```

Loaded in `config.py` via `python-dotenv`. Import from `config`, never `os.getenv` directly in agents.

---

## Tech Stack

- **Python** — agents, tools, FastAPI backend
- **httpx** — all async HTTP requests (not `requests`, not `aiohttp`)
- **LangGraph** — agent orchestration with shared state
- **Claude Sonnet** — orchestrator + synthesizer only (not the scorer agents)
- **FastAPI + uvicorn** — API layer
- **Next.js** — frontend (not yet built)
- **Supabase** — Postgres database, managed via CLI migrations only
- **Vercel** — hosting

---

## Database Rules

- Every schema change is a migration file in `/supabase/migrations/` — never a manual dashboard edit
- `supabase migration new <name>` → edit → `supabase db reset` (local) → `supabase db push` (prod)

---

## What Not To Do

- Do not add docstrings, comments, or type hints to code you didn't change
- Do not create helpers or abstractions for one-time use
- Do not add error handling for scenarios that can't happen in practice
- Do not push to `main` or `dev` directly — always via PR
- Do not use `str | None` syntax — use `Optional[str]` from `typing`
- Do not use `requests` or `aiohttp` — httpx only
