# London Postcode Finder

A multi-agent web app that recommends where to live in London based on what you care about — and gets smarter with every search.

You spend 100 tokens across five dimensions (safety, green space, nightlife, transport, affordability) and can add a sentence of context ("I need a nursery nearby for my daughter"). A LangGraph pipeline scores 40 London postcode districts, sends five research agents to the web for the best fits, and writes five recommendations with an honest tradeoff for each. The UI shows every agent decision live as it happens.

- **Search** (`/`) — sliders, context, a live agent timeline, results and a "Why these results" drawer
- **What it has learned** (`/learning`) — the distilled memory, raw notes, and how the rules changed over time
- **How it works** (`/how-it-works`) — the architecture, in plain English

---

## Architecture

```
Browser ──► Next.js (Vercel) ──fetch + Server-Sent Events──► FastAPI (Railway, Docker)
                                                                  │
                                                                  ▼
                                                          LangGraph pipeline
                                                                  │
                                        Supabase (Postgres) ◄─────┴─────► Anthropic · Overpass · TfL
```

The backend is a long-running container rather than a serverless function because a search takes 45–90 seconds and streams progress the whole way.

### The pipeline

```
Knowledge Loader        distilled brain + last 10 raw learnings
      ↓
Orchestrator            Claude: ignore / adjust weights / spawn a context agent
      ↓
Context Sub-Agent       only when spawned — one combined Overpass query (or web search), cached 30 days
      ↓
5 Scorers (parallel)    deterministic lookups of monthly pre-computed scores — no LLM
      ↓
Synthesiser pass 1      weight, rank, apply the spawn filter, keep top 5
      ↓
5 Research Agents       Claude + web search, one per district, bounded concurrency
      ↓
Synthesiser pass 2      Claude: verdict, rationale, tradeoff, tip + 2–3 learnings
      ↓
Knowledge Writer        save learnings, count the query
      ↓
Distiller               every DISTILL_EVERY_N searches, after the response is sent
```

**Scorers are not agents.** The five data pipelines in `/scorers` are deterministic. Judgement lives in `/agents`: the orchestrator, the context sub-agent, the research agents and the distiller.

**Spawn is a filter.** A district with no nursery nearby is removed from the shortlist rather than averaged in.

**Layered memory, not RAG.** The distilled brain (compressed, ≤12 heuristics) plus the last 10 raw notes are injected into every search, like a long conversation's summary plus its recent turns.

### Streaming events

`POST /api/search` returns `text/event-stream` with typed events: `started`, `knowledge_loaded`, `orchestrator`, `spawn_started`, `spawn_complete`, `scorer_complete`, `scoring_complete`, `shortlist`, `research_started`, `research_complete`, `synthesis_complete`, `learning_saved`, `done` / `error`.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness + DB connectivity |
| `POST /api/search` | `{token_allocation, context_text, session_id}` → SSE stream. Tokens use keys `crime, green, nightlife, transport, rent`, each 0–100, summing to 100; context ≤ 500 chars |
| `GET /api/knowledge` | Distilled brain, 10 recent learnings, query count, distillation history |
| `GET /api/knowledge/export` | The knowledge base as `knowledge.md` |
| `POST /api/admin/distill` | Run distillation now (header `X-Admin-Token`) |
| `GET /api/cron/refresh-scores` | Re-run the monthly score pre-computation (header `Authorization: Bearer $CRON_SECRET`) |
| `GET /api/demo/recorded` | A recorded example run the UI can replay |

Cost protection: `RATE_LIMIT_PER_HOUR` per IP (default 5) and `DAILY_SEARCH_CAP` across everyone (default 100). Both return a 429 that the UI turns into "See a recorded example run". Each search has a 240 s hard timeout.

---

## Run it locally

Prerequisites: Python 3.11, Node 20+, Docker Desktop, Supabase CLI.

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in ANTHROPIC_API_KEY, SUPABASE_URL/KEY (local values from `supabase status`)

supabase start
supabase migration up --local   # apply migrations without wiping data
python tools/load_rent_data.py  # rent_data from data/ons_rent.xlsx
python tools/precompute_scores.py   # fills cached_scores (slow: live Police/Overpass/TfL calls)

uvicorn api.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
cp .env.example .env.local
npm install && npm run dev      # http://localhost:3000
```

> `supabase db reset` wipes `cached_scores` and `rent_data`. Prefer `supabase migration up --local`; if you must reset, re-run the two data scripts afterwards.

Useful scripts:

| Command | What it does |
|---|---|
| `python tools/seed_demo.py --yes` | 12 varied searches so learnings accumulate and distillation fires (~$2–3) |
| `python tools/record_demo_run.py` | Records the fallback demo run into `api/demo/` and `frontend/public/` (~$0.20) |
| `python agents/distiller.py [--force]` | Run a distillation from the command line |

### Tests

```bash
python -m pytest tests/ -v                                  # unit + live scorer tests
python -m pytest tests/test_api.py tests/test_distiller.py tests/test_context_sub_agent.py   # fast, no network
RUN_E2E_TESTS=1 python -m pytest tests/test_pipeline_e2e.py # real Anthropic calls
```

The scorer tests call live public APIs (Police, Overpass, TfL) and can flake when those are overloaded.

---

## Environment variables

Backend: see [`.env.example`](.env.example) — every variable is commented. Frontend: see [`frontend/.env.example`](frontend/.env.example).

| Backend | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | |
| `SUPABASE_URL`, `SUPABASE_KEY` | yes | |
| `TFL_APP_KEY` | for score refresh | |
| `ADMIN_TOKEN` | recommended | manual distillation; bypasses rate limits |
| `CRON_SECRET` | for monthly refresh | must match Vercel |
| `FRONTEND_ORIGIN` | in production | comma-separated CORS origins |
| `RATE_LIMIT_PER_HOUR`, `DAILY_SEARCH_CAP`, `DISTILL_EVERY_N` | no | defaults 5 / 100 / 10 |

| Frontend | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | public backend URL, called from the browser |
| `BACKEND_URL`, `CRON_SECRET` | server-only, used by the cron proxy route |

---

## Deploy

Backend on Railway from the repo root (`Dockerfile`, `railway.json`, health check `/api/health`); frontend on Vercel with root directory `frontend` (`frontend/vercel.json` holds the monthly cron). The exact click-by-click checklist is in [`MANUAL_STEPS.md`](MANUAL_STEPS.md).

---

## Project structure

```
agents/      orchestrator + graph, context sub-agent, knowledge loader/writer, distiller
api/         FastAPI app, SSE event mapping, rate limiter, recorded demo run
scorers/     5 deterministic scorers (live fetch + cached read)
tools/       postcodes.io, Supabase client, spawn cache, precompute, seed + record scripts
prompts/     orchestrator, synthesiser, distiller system prompts
supabase/    migrations — every schema change is a migration
frontend/    Next.js app
tests/       pytest
```

Development workflow and branch rules: `feature/*` → PR to `dev` → PR to `main`. See `PROJECT.md` for the full plan and backlog.
