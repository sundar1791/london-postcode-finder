# BUILD_SPEC — London Postcode Finder: Ship the Live Prototype

> **For Claude Code.** Read this file and `PROJECT.md` in full before starting. Then execute the phases below in order, end to end, with minimal check-ins. Sundar will handle anything that needs his accounts or a dashboard (listed in Phase 6). Everything else is yours.

---

## 0. Goal and Definition of Done

Turn the working terminal pipeline (Milestone 2, complete) into a **live, deployed, demo-ready web product** this week, including the **distillation engine** (the continuous-learning loop).

**Done means all of these are true:**

1. A public URL where a user sets 100 tokens across 5 dimensions, optionally adds context, and gets 5 recommendations.
2. The UI shows the agents working in real time: orchestrator decision, spawn, scoring, research per district, synthesis.
3. A "What the system has learned" page shows the distilled brain, recent learnings, query count and distillation history.
4. Distillation runs automatically every N queries (default 10) and can be triggered manually by an admin endpoint.
5. Rate limits and a daily cap protect API spend.
6. Demo fallbacks exist: spawn results are cached, and a recorded example run can be shown if the live pipeline fails.
7. All existing tests pass (`pytest`; plus `RUN_E2E_TESTS=1` suite once at the end).
8. `MANUAL_STEPS.md` gives Sundar an exact, copy-pasteable checklist for every account/dashboard step.
9. `PROJECT.md` is updated to reflect what was built.

---

## 1. Operating Rules

- **Autonomy:** make implementation decisions yourself. Do not stop to ask about naming, library choice, styling details or file layout. Prefer boring, well-supported choices.
- **Branching:** work on `feature/v1-live-prototype` cut from `dev`. Never commit to `main`. Commit and push at the end of **every phase** (and any time something meaningful works). Do not leave tested work uncommitted.
- **Secrets:** never commit `.env` or any key. Every new env var goes into `.env.example` with a comment, and into `MANUAL_STEPS.md`.
- **Blocked on a manual step?** Write it into `MANUAL_STEPS.md`, stub or mock around it, and keep going. Do not stop the build.
- **Schema changes:** migration files only (`supabase migration new ...`). Apply locally with `supabase db reset` — but **first export `cached_scores` to JSON and reimport afterwards** (see gotchas). Record in `MANUAL_STEPS.md` that Sundar must run `supabase db push` for hosted.
- **Prompts live in `/prompts/*.md`.** Scorers in `/scorers`, agents in `/agents`.
- **Python 3.9 compatible:** `Optional[str]`, never `str | None`.

### Known gotchas (learned the hard way — respect these)

- `claude-sonnet-5` returns a `thinking` block before the `text` block. Always extract text by filtering `block.type == "text"`. Never use `content[0]`.
- Parse Claude JSON with `json.loads(..., strict=False)`. If you see "Unterminated string", it's `max_tokens` truncation — raise the budget.
- Current budgets: orchestrator 1500, synthesiser pass 2 8000, research agents 500.
- Overpass requires `User-Agent: london-postcode-finder/1.0 (portfolio project)` or it returns 406. The Context Sub-Agent has it; **the green and nightlife scorers do not** (issue #76).
- `overpass.kumi.systems` is frequently down; `overpass-api.de` with the User-Agent works.
- All modules call `load_dotenv(override=True)`.
- Local Supabase: `http://127.0.0.1:54321`. `supabase db reset` wipes `cached_scores` and `rent_data`.
- `learnings` decomposed columns are nullable; category values are `context_methodology | token_pattern | synthesiser_insight` (British spelling).

---

## 2. Target Deployment Architecture

```
Browser ──► Next.js frontend (Vercel)
                │  fetch + Server-Sent Events
                ▼
          FastAPI backend (Railway, Docker) ──► LangGraph pipeline
                │                                   │
                ▼                                   ▼
          Supabase (hosted Postgres)          Anthropic API, Overpass, TfL
```

**Why the backend is not on Vercel:** a full pipeline run takes 30–90 s (minutes with a spawn) and streams progress. A long-running container avoids serverless timeouts and cold starts. Railway is the default; if you judge Render or Fly.io materially simpler, use it and update `MANUAL_STEPS.md` accordingly.

The existing `vercel.json` cron (`/api/cron/refresh-scores`, monthly) should hit a Next.js route that proxies to the backend endpoint with the `CRON_SECRET` header.

---

## 3. Phase 1 — Preflight and Tech Debt

1. Cut the branch. Run `pytest` and note the baseline (some scorer tests hit live Overpass and may flake — don't chase those).
2. **Fix issue #76:** add the Overpass User-Agent header to `scorers/green_scorer.py` and `scorers/nightlife_scorer.py`. Drop `overpass.openstreetmap.fr` if present.
3. **Restore parallel research agents:** `asyncio.gather` with an `asyncio.Semaphore` (default concurrency 5, configurable via `RESEARCH_CONCURRENCY`), keeping the existing 429 retry/backoff.
4. Centralise config in `config.py` (model names, max_tokens, thresholds, rate limits), read from env with sensible defaults.
5. Commit: `Phase 1: preflight, Overpass UA on scorers, parallel research (closes #76)`.

---

## 4. Phase 2 — Distillation Engine (Milestone 7, US-039–041)

The Knowledge Writer already has a `_trigger_distillation(query_count)` placeholder. Replace it with the real engine.

**Files:** `prompts/distiller.md`, `agents/distiller.py`, migration for `distillation_history`.

**Behaviour:**

1. **Inputs:** the current `distilled_brain`, plus all `learnings` rows created after `agent_config.last_distilled` (or all rows if null).
2. **Model call:** `claude-sonnet-5` with the distiller prompt. The output is a new brain in markdown:
   - At most ~12 heuristics, grouped under: *Interpreting user context*, *Token allocation patterns*, *District insights*.
   - Each heuristic is a full sentence, with an evidence note (e.g. "seen in 7 queries").
   - It merges with, refines or retires existing heuristics rather than appending.
   - A short `change_summary` (added / refined / retired).
3. Return JSON `{ "distilled_brain": str, "change_summary": str }`.
4. **Write:** update `agent_config.distilled_brain` and `last_distilled`; insert a row into `distillation_history` (`id, created_at, query_count, learnings_consumed, previous_brain, new_brain, change_summary`).
5. **Safety:** if the call fails or the output is empty or unparseable, keep the old brain, log it, and never raise into the user pipeline.
6. **Trigger:** every `DISTILL_EVERY_N` queries (default **10**, env-configurable). Run it as a background task **after** the user's response is complete, so the user never waits for it.
7. **Manual trigger:** `POST /api/admin/distill`, protected by an `ADMIN_TOKEN` header.
8. **Tests:** unit tests with a mocked Anthropic client covering the happy path, bad JSON keeping the old brain, and the threshold logic.

Commit: `Phase 2: distillation engine + history (closes US-039/040/041 issues)`. Use `gh issue list` to find the actual issue numbers and verify each with `gh issue view N --json title` before writing `closes #N`.

---

## 5. Phase 3 — API Layer (Milestone 3)

Create `api/` with FastAPI.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness check plus DB connectivity |
| `POST /api/search` | Body `{token_allocation, context_text, session_id}`. Validates the sum is 100, each value is 0–100, and context is ≤500 chars. Returns an **SSE stream**. |
| `GET /api/knowledge` | `{distilled_brain, recent_learnings[10], query_count, last_distilled, distillation_history[]}` |
| `POST /api/admin/distill` | Manual distillation (needs `ADMIN_TOKEN`) |
| `GET /api/cron/refresh-scores` | Runs `tools/precompute_scores.py` logic (needs `CRON_SECRET`) |
| `GET /api/demo/recorded` | Returns a stored example run for the fallback |

**SSE events.** Use LangGraph `astream(stream_mode="updates")` and map each node to a typed event. Each event should carry enough data for the UI to show *why*, not just *that*:

- `knowledge_loaded`: char count and cold-start flag
- `orchestrator`: type, reasoning, original vs adjusted allocation, spawn intent
- `spawn_started` / `spawn_complete`: intent, number of districts with >0 score, whether it came from cache
- `scoring_complete`: top 10 with weighted scores
- `shortlist`: top 5, plus any districts removed by the spawn filter
- `research_started` / `research_complete`: per district
- `synthesis_complete`: the 5 recommendations
- `learning_saved`: count and new query_count
- `done` / `error`

**Persistence:** save every search to the existing `searches` table (inputs, adjusted allocation, top 5, full result JSON, duration, session_id).

**Spawn cache:** new table `spawn_cache (overpass_query text primary key, scores jsonb, created_at)`. The Context Sub-Agent checks it first and uses the entry if it is less than 30 days old. This keeps repeat demo queries fast.

**Rate limiting and cost protection:**
- Per-IP limit: `RATE_LIMIT_PER_HOUR`, default 5.
- Global daily cap: `DAILY_SEARCH_CAP`, default 100. When hit, return a friendly 429 that the UI can use to offer the recorded demo instead.
- Both are in-memory or backed by a Supabase table — your choice.

**Other requirements:**
- CORS allows `FRONTEND_ORIGIN` (comma-separated) plus localhost.
- Pipeline timeout of 240 s, which emits an `error` event.

**Tests:** add API tests with `httpx`/`TestClient` for validation, rate limiting and health. Use a mocked pipeline — no real API calls.

Commit: `Phase 3: FastAPI + SSE streaming, spawn cache, rate limits (closes US-018..021 issues as applicable)`.

---

## 6. Phase 4 — Frontend (Milestone 4)

Next.js (App Router, TypeScript, Tailwind) in `/frontend`. Replace the scaffold if needed.

**Design direction:** calm, credible and editorial. This should look like a considered product, not a hackathon dashboard. Use one accent colour, good typography, generous whitespace and a subtle London feel (e.g. muted line-map colours as dimension accents). It must be mobile responsive, with light and dark mode.

### Page `/` — Search

- **Token allocation:** 5 sliders (Safety, Green space, Nightlife, Transport, Affordability) that enforce a total of exactly 100.
  - Show a live "remaining" counter.
  - Disable submit unless the total is 100.
  - Add presets: *Young professional*, *Family*, *Budget first*, *Balanced*.
- **Context:** textarea with a 500-character counter, plus example chips — "I'm terrified of crime", "I need a nursery nearby for my daughter", "I love parks and quiet streets".
- **Agent activity panel:** driven by the SSE stream, shown as a vertical timeline that reveals each stage as it happens. It surfaces the orchestrator's decision and a one-line version of its reasoning, and shows a before/after weight diff when weights were adjusted.
- **Results:** 5 recommendation cards, each with:
  - Rank, district code and area name (add a small district→area-name map)
  - Verdict, rationale, tradeoff and tip
  - A mini bar breakdown of the 5 dimension scores
- **"Why these results" drawer:** orchestrator reasoning, weight changes, spawn filter effect (districts removed and why), and the knowledge base that was injected.
- **Redo and Start New:**
  - Redo keeps the sliders and clears the results.
  - Start New resets everything.
  - No history UI in v1.
- **Error, rate-limit and daily-cap states:** each offers "See a recorded example run" (the fallback).

### Page `/learning` — What the system has learned

- Current distilled brain, rendered as markdown.
- Query count, and a countdown to the next distillation.
- Last 10 raw learnings.
- Distillation history as a timeline: each version's change summary, with an expandable diff of the brain.

### Page `/how-it-works`

- A clean architecture diagram (inline SVG or React), matching the two-pass design: Knowledge Loader → Orchestrator → (Context Sub-Agent) → 5 parallel Scorers → Synthesiser P1 → 5 parallel Research Agents → Synthesiser P2 → Knowledge Writer → Distiller.
- Short plain-English captions.
- The scorers-vs-agents distinction.
- The spawn-as-filter decision.
- Layered memory vs RAG.

**Other frontend requirements:**
- `NEXT_PUBLIC_API_URL` env var.
- Next.js route `/api/cron/refresh-scores`, which proxies to the backend with `CRON_SECRET`.
- Keep `vercel.json` cron config working.

Commit: `Phase 4: frontend — search, live agent timeline, learning page, how-it-works (closes US-022..027, US-049 as applicable)`.

---

## 7. Phase 5 — Deployment Prep, Demo Readiness and Docs

1. **`Dockerfile`** for the backend (python:3.11-slim, uvicorn), plus `railway.json` or equivalent. Health check on `/api/health`.
2. **`.env.example`** (backend) and `frontend/.env.example`, with every variable commented.
3. **`tools/seed_demo.py`:** runs ~12 varied queries against the pipeline (covering ignore, adjust, spawn and combination cases), so learnings accumulate and distillation fires at least once. Print a summary. It needs `--yes` to run, because it costs about $2 in API calls.
4. **Recorded fallback:** `tools/record_demo_run.py` runs one rich query (e.g. "I need a nursery nearby for my daughter" with a Family preset) and saves the full event sequence to Supabase (or a JSON file in `api/demo/`). The frontend can replay it at realistic pace, clearly labelled "Recorded example run".
5. **`README.md`:** what it is, the architecture, how to run locally, env vars, and how to deploy. Link to `/how-it-works`.
6. **`MANUAL_STEPS.md`:** see Phase 6.
7. **Update `PROJECT.md`:**
   - Mark Milestones 3, 4 and 7 (distillation) as done where true.
   - Add a changelog entry.
   - Note that Milestone 2.5 evals (US-044, US-045, US-048) are deferred.

Commit: `Phase 5: deploy config, seed + recorded demo, docs`.

---

## 8. Phase 6 — MANUAL_STEPS.md (for Sundar)

Write an exact, ordered checklist with copy-pasteable commands and the precise env var names and values to set. It must include, at minimum:

1. **Anthropic Console:** set a monthly spend limit, e.g. £30–50.
2. **Supabase:**
   - Restore the project if it's paused.
   - `export $(grep SUPABASE_DB_PASSWORD .env | xargs) && supabase db push --password $SUPABASE_DB_PASSWORD`
   - Confirm hosted `cached_scores` has 200 rows. Include a one-liner to check, and a reimport one-liner if needed.
3. **Railway:**
   - New project from the GitHub repo, root directory, Dockerfile.
   - Env vars: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `TFL_APP_KEY`, `ADMIN_TOKEN`, `CRON_SECRET`, `FRONTEND_ORIGIN`, `DISTILL_EVERY_N`, `RATE_LIMIT_PER_HOUR`, `DAILY_SEARCH_CAP`.
   - Copy the public URL.
4. **Vercel:**
   - Import the repo, set the root directory to `frontend`.
   - Env vars: `NEXT_PUBLIC_API_URL`, `CRON_SECRET`, `BACKEND_URL`.
   - Deploy.
5. Set `FRONTEND_ORIGIN` on Railway to the Vercel URL, and redeploy.
6. **Optional custom domain:** `postcodes.sundarsubramanian.xyz` via a Cloudflare CNAME to Vercel. Give the exact record.
7. **Warm up:**
   - `python tools/seed_demo.py --yes` against hosted.
   - `python tools/record_demo_run.py`.
   - Check that `/learning` shows a distilled brain.
8. **Smoke test:** the three demo queries, the rate limit, and the recorded fallback.
9. Merge `feature/v1-live-prototype` → `dev` → `main` via PRs.

---

## 9. Out of Scope (do not build)

- Auth, user accounts, search history UI (Milestone 6).
- New evals (US-044, US-045, US-048). Keep the existing tests green only.
- Realigning the district list with the ONS rent dataset.
- Enriching the synthesiser to the full decomposed learnings schema.

---

## 10. Final Verification Before Handing Back

- [ ] `pytest` passes (excluding known-flaky live-Overpass scorer tests, which should be listed).
- [ ] `RUN_E2E_TESTS=1 pytest tests/test_pipeline_e2e.py` passes once.
- [ ] Backend runs locally: `uvicorn api.main:app` plus the three demo queries stream correctly.
- [ ] The frontend runs locally against the local backend. The full flow works on desktop and at mobile width.
- [ ] Distillation fires at threshold, and history shows up on `/learning`.
- [ ] The spawn query runs fast on its second run (cache hit).
- [ ] The rate-limit and daily-cap states show the recorded-run fallback.
- [ ] Everything is committed and pushed. A PR is open to `dev` with a clear summary.
- [ ] `MANUAL_STEPS.md`, `README.md` and `PROJECT.md` are updated.

When done, reply with:
- A short summary of what was built.
- Any deviations from this spec and why.
- Anything left for Sundar beyond `MANUAL_STEPS.md`.
