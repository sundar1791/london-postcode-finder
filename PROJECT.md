# London Postcode Finder — Project Plan

## What We're Building

A web app that helps people new to London figure out where to live. Users are given 100 tokens to distribute across 5 lifestyle dimensions, and can optionally add a short natural language context (up to 500 characters) to personalise their search further — for example, "I'm a mother of two and need access to a nursery." A multi-agent system scores every London postcode district against those dimensions using cached data from public APIs, then performs qualitative web research on the top 5 results to surface insights that data alone can't capture. Claude synthesises quantitative scores and qualitative research into 5 personalised recommendations with rich rationale.

Users can try different token allocations and contexts. A Redo button lets them iterate from their last query; Start New resets everything. Past searches are saved to the database for developer inspection but not shown in the UI until V2 (when auth is added). No login required in V1.

The agent system gets smarter over time — every query appends a structured learning to a knowledge base that the orchestrator and synthesizer read at the start of each subsequent query.

---

## The Agent Architecture

The pipeline runs in two passes. Pass 1 is fast (cached data lookups). Pass 2 is where genuine agency happens (qualitative web research on the top 5 results only).

```
User submits token allocation (100 tokens) + optional context text (≤500 chars)
              ↓
    [Knowledge Loader]
    Reads distilled_brain from agent_config + last 10 raw learnings
    Compiles into knowledge_base markdown string, injects into graph state
              ↓
    [Orchestrator Agent — Claude Sonnet]
    Reads knowledge base + current input
    1. Validates tokens sum to 100
    2. Reads context text and classifies it:
       - Irrelevant / nonsensical → ignore, run standard pipeline
       - Weight hint (e.g. "love parks") → silently adjust token weights
       - New dimension (e.g. "need a nursery") → spawn Context Sub-Agent
              ↓
    ╔══════════════════════════════════════════════════╗
    ║  PASS 1 — SCORING (all 40 districts, from cache) ║
    ║                                                  ║
    ║  5 Scorers run in PARALLEL (DB lookups)          ║
    ║                                                  ║
    ║  Crime Scorer     → cached_scores table          ║
    ║  Green Scorer     → cached_scores table          ║
    ║  Nightlife Scorer → cached_scores table          ║
    ║  Transport Scorer → cached_scores table          ║
    ║  Rent Scorer      → cached_scores table          ║
    ║                                                  ║
    ║  + Context Sub-Agent (spawned only when needed)  ║
    ║    → Overpass query (nurseries, schools, etc.)   ║
    ║    → Live API call (query-specific, can't cache) ║
    ╚══════════════════════════════════════════════════╝
              ↓
    [Synthesizer — Pass 1]
    Weights scores, selects top 5 postcode districts
              ↓
    ╔══════════════════════════════════════════════════╗
    ║  PASS 2 — QUALITATIVE RESEARCH (top 5 only)     ║
    ║                                                  ║
    ║  5 Research Agents run in PARALLEL               ║
    ║  One per top postcode district                   ║
    ║                                                  ║
    ║  Each agent makes a Claude API call with         ║
    ║  web search enabled, searching for:              ║
    ║  - Recent news about the postcode                ║
    ║  - Reddit/forum discussions                      ║
    ║  - Qualitative insights across all dimensions    ║
    ║    (new tube extension, crime trends,            ║
    ║     green space developments, etc.)              ║
    ║                                                  ║
    ║  Returns: {postcode, qualitative_insights: [...]}║
    ╚══════════════════════════════════════════════════╝
              ↓
    [Synthesizer — Pass 2]
    Reads knowledge base + quantitative scores + qualitative insights + context
    Writes final top 5 recommendations with rich rationale
    Populates new_learnings list in state
              ↓
    [Knowledge Writer]
    Inserts new_learnings rows into learnings table
    Increments query_count in agent_config
    If query_count % 50 == 0: trigger distillation (async, non-blocking)
              ↓
    Results + search saved to Supabase
    Response streamed to Next.js frontend
    Frontend shows agent activity animation during both passes
```

**Claude API usage per search:**
- Orchestrator call: ~600 tokens in (includes knowledge), ~150 out
- Context Sub-Agent call: ~300 tokens in, ~100 out — only when needed
- Synthesizer Pass 1 call: ~1,500 tokens in, ~300 out
- 5 Research Agent calls (parallel): ~500 tokens in, ~300 out each — ~$0.08 total
- Synthesizer Pass 2 call: ~4,000 tokens in (includes qualitative insights), ~900 out
- **Total per search: ~$0.15–0.20**

Pass 1 completes in under 2 seconds (cache lookups). Pass 2 takes 15–30 seconds (web research). The frontend animation communicates what's happening during Pass 2 to keep users engaged.

### The Orchestrator's Context Classification Logic

This is the most important reasoning step in the system. The orchestrator receives the context text and makes one of three decisions:

**Ignore** — context is nonsensical, offensive, or completely unrelated to London living (e.g. "I like pizza"). Pipeline runs as normal with the original token weights.

**Weight adjustment** — context maps to an existing dimension and should shift the token weights silently. The orchestrator recalculates weights before dispatching.
- "I'm terrified of crime" → boost safety tokens
- "I need to be outdoors" → boost green space tokens
- "I'm on a very tight budget" → boost rent tokens

**Spawn Context Sub-Agent** — context requires data that no existing agent covers. The orchestrator extracts the core intent and passes it as a structured query.
- "I need a nursery nearby" → Overpass query: `amenity=kindergarten` within 500m
- "I want to be near a mosque" → Overpass query: `amenity=place_of_worship + religion=muslim`
- "I need good schools" → Overpass query: `amenity=school` within 1km
- "I want a strong Tamil community" → Claude web search fallback

The Context Sub-Agent returns scores in the same `{postcode, normalised_score}` format as every other scorer, so the Synthesizer needs no special handling.

### Scorers vs Agents — An Important Distinction

The 5 core data pipelines (crime, green, nightlife, transport, rent) are **scorers**, not agents. They are deterministic data fetchers that read from a cache and return normalised numbers. There is no reasoning, no decision-making, no handling of ambiguity. Calling them agents would be misleading.

Genuine agency in this system lives in three places:
1. **The Orchestrator** — classifies ambiguous context and makes routing decisions
2. **The Context Sub-Agent** — constructs queries from natural language intent and handles fallback strategies
3. **The Research Agents** — reason about web search results and extract qualitative insights

This distinction is reflected in the folder structure: `/scorers` for the 5 data pipelines, `/agents` for the genuine decision-making components.

---

## The Score Cache

All 5 scorer dimensions use pre-computed scores stored in Supabase. This keeps Pass 1 under 2 seconds regardless of API reliability.

**Why cache instead of live API calls?** The free public APIs (Police, Overpass, TfL) are slow, rate-limited, and occasionally unavailable. Running 40 concurrent API calls on every user query produces 30–60 second response times and frequent failures — not a product. Pre-computing once a month and serving from a database gives users instant results and eliminates rate limiting entirely.

**The Context Sub-Agent is the exception.** It handles query-specific criteria (nurseries, mosques, schools) that are unique to each user request and cannot be pre-computed. It always runs live.

### Cache Schema

```sql
cached_scores table
─────────────────────────────────────────────────────
id               uuid, primary key
district         text not null
dimension        text not null  — 'crime' | 'green' | 'nightlife' | 'transport' | 'rent'
raw_value        numeric        — raw value from the API
score            numeric not null  — normalised 0–1
needs_retry      boolean default false  — true if API failed, score is placeholder
last_updated     timestamptz default now()

unique constraint on (district, dimension)
```

### Monthly Refresh Job

A Vercel cron job runs at midnight on the first of every month (`0 0 1 * *`). It:
1. Runs all 5 scorers against all 40 postcode districts
2. Upserts results into the cached_scores table
3. For any district that returned 0 due to a timeout, marks `needs_retry = true`
4. Runs a targeted retry pass: fetches only the failed districts individually with 60-second delays
5. Updates `needs_retry = false` once real data is obtained

---

## The 5 Scoring Dimensions

| Dimension | Source | Cache | Notes |
|---|---|---|---|
| Safety | UK Police API (data.police.uk) | Monthly | Inverted: lower crime = higher score |
| Green Space | Overpass API (OpenStreetMap) | Monthly | Parks, nature reserves, grass, forest within 800m |
| Nightlife | Overpass API (OpenStreetMap) | Monthly | Bars, pubs, clubs, restaurants within 800m |
| Transport | TfL Unified API | Monthly | Stop count + line diversity score |
| Rent | ONS PIPR via Supabase | Monthly | Borough-level, inverted: lower rent = higher score |
| Postcode backbone | postcodes.io | On demand | Validates districts, returns lat/lng centroids |

---

## The LangGraph State Object

```python
class LondonSearchState(TypedDict):
    # Input
    token_allocation: dict      # {safety: 40, green: 20, ...} — original from user
    context_text: str           # raw user input (≤500 chars, empty string if none)
    session_id: str             # browser-generated UUID

    # Knowledge base (loaded first, read by orchestrator + synthesizer)
    knowledge_base: str         # compiled markdown: distilled_brain + last 10 raw learnings

    # Orchestrator output
    adjusted_allocation: dict   # token weights after context adjustment
    context_analysis: dict      # {relevant: bool, type: "ignore"|"weight"|"spawn",
                                #  intent: str, overpass_query: str|None}

    # Scorer output (Pass 1)
    postcode_scores: dict       # raw scores per postcode per dimension
    weighted_scores: dict       # after applying adjusted allocation
    top_5_districts: list       # top 5 postcode districts from Pass 1

    # Research agent output (Pass 2)
    qualitative_insights: dict  # {district: [insight1, insight2, ...]} for top 5 only

    # Synthesizer output (Pass 2)
    top_5: list                 # final ranked postcodes with rich rationale

    # Knowledge writer input (populated by synthesizer, saved last)
    new_learnings: list         # structured entries to append to learnings table
                                # each entry: {category, context_intent, methodology,
                                #              token_pattern, outcome_summary}
```

---

## The Knowledge Base Design

The knowledge base is the mechanism by which the agents get smarter over time. It lives in Supabase — not a flat file — so it's queryable, appendable without race conditions, and exportable on demand as `knowledge.md`.

**Why not a file?** Vercel serverless functions are stateless — they can't write to disk between requests. A file in the repo would require a commit per query. Concurrent writes to a blob file cause silent data loss. A Supabase table solves all three problems.

### The Memory Model — Inspired by How LLMs Handle Long Conversations

Claude and Gemini don't have persistent memory — they have a context window. Every message re-sends the full conversation history until it gets too long, at which point older content gets compressed into summaries while recent messages stay verbatim. The model always has: a compressed representation of old history + the full detail of recent events.

Your system uses the same pattern:

```
Distilled brain  ←→  Compressed old history  (stable heuristics, always injected)
Last 10 raw entries  ←→  Recent verbatim messages  (specific, recent, high-recency value)
```

### Three Types of Knowledge — Different Shapes, Different Needs

**Methodological knowledge** — how to handle classes of request. "When a user asks about nurseries, use Overpass `amenity=kindergarten` within 500m." Grows slowly, highly compressible into rules.

**Domain knowledge** — facts about London. "SW postcodes consistently score poorly on rent. E1 scores high on nightlife but low on green space." Moderately stable, compressible into heuristics.

**Pattern knowledge** — user archetypes. "Users allocating >50 tokens to safety often implicitly care about schools even when they don't mention it." Emerges over time, becomes most valuable after hundreds of queries.

### Schema — Designed for Distillation

```sql
learnings table
─────────────────────────────────────────────────────
id               uuid, primary key
category         text  — 'context_methodology' | 'token_pattern' | 'synthesizer_insight'
context_intent   text  — full sentence: what the user wanted
methodology      text  — full sentence: exactly what the agent did and why
token_pattern    text  — full sentence: what the token allocation implied about the user
outcome_summary  text  — full sentence: top result and why it scored well
created_at       timestamptz

agent_config table  (single row, always exists)
─────────────────────────────────────────────────────
id               integer, always 1
distilled_brain  text  — compressed markdown of all accumulated heuristics
last_distilled   timestamptz  — when the brain was last rewritten
query_count      integer  — total queries run, used to trigger distillation
```

**Critical writing discipline for all learnings text columns:** Every entry must be a complete, meaningful sentence — not shorthand. The distillation process reads these entries and uses them to write rules. Bad input produces bad rules.

```
❌ Bad:  "Overpass: amenity=kindergarten r=500m"
✅ Good: "User wanted nurseries within walking distance — queried Overpass for
         amenity=kindergarten within 500 metres of each postcode centroid,
         returned a normalised count score across all 40 districts."
```

### Why Not RAG?

RAG is the right answer when the knowledge base is large and heterogeneous — thousands of entries across many diverse domains. Your domain is deliberately narrow: London postcodes, ~20-30 distinct context intent types, fixed scoring dimensions. After 1,000 queries, you'll have deep repeated coverage of a small number of patterns — exactly the scenario where distillation produces denser, more useful heuristics than retrieval would. The distilled brain gets *smarter*, not just longer. RAG remains a valid upgrade path if this framework is later applied to a much broader domain.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Agent orchestration | LangGraph | Parallel node execution, shared state, two-pass pipeline |
| LLM | Claude API (Sonnet) | Orchestrator, Research Agents, Synthesizer |
| Web research | Claude API with web search enabled | Qualitative research pass — no third-party dependency |
| Scorers | Pure Python + httpx | Deterministic DB lookups, no LLM needed |
| Backend | FastAPI | Lightweight, async, Vercel-compatible |
| Frontend | Next.js + Vercel AI SDK | Streaming responses, agent activity animation |
| Database | Supabase (Postgres) | Free tier, CLI-managed, auth-ready for V2 |
| Hosting | Vercel | Auto-deploy on merge to main, cron job support |
| Infra management | GitHub CLI + Supabase CLI + Vercel CLI | No dashboard clicks |

---

## Folder Structure

```
/scorers        ← 5 deterministic data pipelines (crime, green, nightlife, transport, rent)
/agents         ← genuine decision-making components (orchestrator, research agents, context sub-agent)
/tools          ← shared utilities (postcode.py, load_rent_data.py)
/prompts        ← Claude system prompt .md files
/data           ← ONS rent CSV and other static data
/supabase       ← migrations and local config
/frontend       ← Next.js app
/tests          ← pytest test files
```

---

## Repository and Branch Strategy

```
main          ← production, always deployable, never commit directly
  └── dev     ← integration branch, all PRs merge here first
        └── feature/US-XXX-description
```

**Rule:** Every day ends with at least one PR merged into `dev`.
**Rule:** Never commit directly to `main` or `dev`.
**Rule:** Create feature branch from `dev` before any file edits — always.
**Rule:** Every PR closes a GitHub Issue with `closes #N` in the commit message.

---

## Database Migration Discipline

Every schema change is a migration file — never a manual dashboard change.

```bash
supabase migration new add_cached_scores_table
supabase db reset       # apply locally
supabase db push        # push to production
```

---

## Full Backlog

### Milestone 0 — Developer Foundation ✅
*Goal: Repo, tooling, and infra set up.*

| Issue | User Story | Status |
|---|---|---|
| US-001 | Project scaffold — folder structure, requirements, config | ✅ |
| US-002 | GitHub repo, branch strategy, project board, all issues created | ✅ |
| US-003 | Supabase local setup — searches, learnings, agent_config migrations | ✅ |
| US-004 | Vercel project init, environment variable structure | ✅ |

### Milestone 1 — Data Foundation ✅
*Goal: All 5 scorers work independently. Verified data pipelines.*

| Issue | User Story | Status |
|---|---|---|
| US-005 | Postcode utility — postcodes.io, validate and get lat/lng | ✅ |
| US-006 | ONS rent CSV — download, load into Supabase via migration | ✅ |
| US-007 | Crime scorer — Police API, normalised score per postcode | ✅ |
| US-008 | Green space scorer — Overpass API, parks within radius | ✅ |
| US-009 | Nightlife scorer — Overpass API, bars/restaurants within radius | ✅ |
| US-010 | Transport scorer — TfL API, connectivity score per postcode | ✅ |
| US-011 | Rent scorer — ONS lookup, normalised score per postcode | ✅ |
| US-012 | Integration test — all 5 scorers against 5 real postcodes | ✅ |

### Milestone 1.5 — Score Cache
*Goal: Pre-compute all scorer results. User queries become instant DB lookups.*

| Issue | User Story | Notes |
|---|---|---|
| US-042 | Score cache — create cached_scores table migration, pre-computation job that runs all 5 scorers and upserts results, targeted retry logic for districts where API returned 0 (marks needs_retry=true, retries individually with 60s delays) | Claude Code |
| US-042b | Monthly refresh cron — Vercel cron job (`0 0 1 * *`) that triggers the pre-computation job on the first of each month | Claude Code |
| US-042c | Update all 5 scorer graph nodes to read from cached_scores table instead of calling APIs live | Claude Code |

### Milestone 2 — Agent Orchestration
*Goal: Full two-pass LangGraph pipeline works end-to-end in terminal.*

| Issue | User Story | Notes |
|---|---|---|
| US-013 | LangGraph state definition — full TypedDict including knowledge, qualitative_insights, and learnings fields | Claude Code |
| US-014 | Pass 1: parallel scoring — all 5 scorers run as graph nodes reading from cache | Claude Code |
| US-015 | Orchestrator prompt — validates tokens, reads knowledge, classifies context | Manual + Claude Code |
| US-016 | Synthesizer Pass 1 prompt — weights scores, selects top 5, writes intermediate state | Manual + Claude Code |
| US-046 | Pass 2: Research Agents — 5 parallel Claude API calls with web search enabled, one per top postcode, searching for recent news/Reddit/local insights across all relevant dimensions | Claude Code |
| US-047 | Synthesizer Pass 2 prompt — reads knowledge + scores + qualitative insights + context, writes final top 5 recommendations with rich rationale, populates new_learnings | Manual + Claude Code |
| US-017 | End-to-end pipeline test — token input + context → top 5 with qualitative insights in terminal | Claude Code |
| US-033 | Context Sub-Agent — Overpass or Claude web search, spawned dynamically by orchestrator | Claude Code |
| US-034 | Knowledge Loader — reads distilled_brain + last 10 raw learnings, compiles into knowledge_base markdown | Claude Code |
| US-035 | Knowledge Writer — inserts new_learnings rows, increments query_count, triggers distillation at query_count % 50 | Claude Code |

### Milestone 2.5 — Evals
*Goal: Professional-grade evaluation framework covering all agent decision points.*

| Issue | User Story | Notes |
|---|---|---|
| US-043 | Scorer eval harness — for each of the 5 scorers, define 5 postcodes with known expected rank ordering (e.g. "E1 should score higher on nightlife than SE22"), assert rank ordering deterministically | Claude Code |
| US-044 | Orchestrator context classification eval — 15 test cases covering all three classification types (ignore, weight adjustment, spawn), LLM-as-judge grading against expected classification | Manual + Claude Code |
| US-045 | Synthesizer recommendation eval — 5 fixed-score test cases, check top 5 recommendations are defensible and rationale references user's actual highest-weighted dimension, LLM-as-judge + structural checks | Manual + Claude Code |
| US-048 | Research agent eval — 5 test cases with known postcode/dimension combinations, LLM-as-judge grading of qualitative insight quality against a rubric (specific, recent, actionable, references real sources) | Manual + Claude Code |

### Milestone 3 — API Layer
*Goal: Pipeline accessible via HTTP with streaming.*

| Issue | User Story | Notes |
|---|---|---|
| US-018 | FastAPI app scaffold, health check endpoint | Claude Code |
| US-019 | Search endpoint — accepts tokens + context_text, returns streaming response covering both passes | Claude Code |
| US-020 | Supabase save — persists tokens, context_text, and results with session UUID | Claude Code |
| US-021 | Knowledge export endpoint — GET /knowledge/export returns knowledge.md file | Claude Code |

### Milestone 4 — Frontend
*Goal: A real browser UI with agent activity animation.*

| Issue | User Story | Notes |
|---|---|---|
| US-022 | Next.js scaffold with Vercel AI SDK, deploy shell to Vercel | Claude Code |
| US-023 | Token allocation UI — sliders enforcing 100 total + context textarea + 500 char counter | Claude Code |
| US-024 | Streaming results UI — recommendations appear as Claude writes | Claude Code |
| US-049 | Agent activity animation — visual display of pipeline activity during both passes. Shows real-time status: "Scoring all districts...", "Researching SE22...", "Researching SW1A..." etc. Makes the wait feel like something meaningful is happening | Claude Code |
| US-025 | Redo button — repopulates last token allocation, clears context box | Claude Code |
| US-026 | Start New button — resets all sliders to 0, clears context and results | Claude Code |
| US-027 | Polish and mobile responsiveness | Claude Code |

### Milestone 5 — V1 Production Release
*Goal: Live, shareable, stable.*

| Issue | User Story | Notes |
|---|---|---|
| US-028 | Dev → main merge, production deployment | CLI |
| US-029 | Error handling — invalid tokens, irrelevant context, API failures, cache misses | Claude Code |
| US-030 | Public README and demo documentation | Manual |

### Milestone 6 — V2: Auth, History, and User Accounts
*Goal: Users log in, own their searches, view history.*

| Issue | User Story | Notes |
|---|---|---|
| US-031 | Supabase Auth — email + Google OAuth via CLI | CLI + Claude Code |
| US-032 | Schema migration — replace session UUID with user ID in searches table | Claude Code |
| US-036 | History endpoint — retrieve past searches by user ID | Claude Code |
| US-037 | History UI — display past searches per logged-in user | Claude Code |
| US-038 | Frontend auth flow — login, logout, protected history | Claude Code |

### Milestone 7 — V3: Distillation Engine
*Goal: Agents get genuinely smarter over time through automated distillation.*

| Issue | User Story | Notes |
|---|---|---|
| US-039 | Distillation prompt — Claude reads all learnings rows and writes compressed brain as structured markdown covering methodological rules, London domain knowledge, and user archetypes | Manual + Claude Code |
| US-040 | Distillation trigger — async job called by Knowledge Writer every 50 queries, updates agent_config.distilled_brain and last_distilled | Claude Code |
| US-041 | Distillation quality test — compare orchestrator decisions before and after distillation against a fixed set of test queries, assert improvement | Claude Code |

---

## Infrastructure Flexibility Principles

1. **Supabase is the single source of truth for data.** Adding new features means adding migrations, not rearchitecting.
2. **Each scorer is one file.** Adding a new scoring dimension = one new file + one graph node change + one cache column.
3. **The Context Sub-Agent is a template.** Any new query type the orchestrator learns to classify requires no architecture change — just a new pattern added to the knowledge base.
4. **The knowledge base is portable.** The `/knowledge/export` endpoint produces a standalone `knowledge.md` file reusable in future projects with zero modification.
5. **History is gated behind auth.** Data is always saved; it's only surfaced in the UI once users have accounts. This keeps V1 simple without losing any data.
6. **Prompts live in `/prompts/*.md`.** Improving orchestration logic or synthesis quality doesn't touch production code.
7. **Environment variables are the only difference between local and production.** `supabase start` + `vercel dev` mirrors prod exactly.
8. **Every infrastructure change goes through CLI.** No dashboard clicks = reproducible, version-controlled infra.
9. **Scorers are not agents.** The 5 data pipelines are deterministic and live in `/scorers`. Genuine agency lives in `/agents`. This distinction is architectural, not cosmetic.

---

## V2 Notes (Future Considerations)

- **Scorer confidence flags** — scorers could self-evaluate output quality and flag suspected data gaps vs genuine zeros. The synthesizer would weight uncertain results accordingly. Currently scorers return 0 for failed API calls; confidence flags would make this explicit and allow the synthesizer to reason about it.
- **RAG upgrade** — if this framework is applied to a much broader domain (multiple cities, many more dimensions), replace distillation with RAG for the knowledge base retrieval layer.

---

## Changelog

| Date | Change |
|---|---|
| Day 1 | Initial plan created — 32 user stories across 6 milestones |
| Day 2 | Added context text feature, Context Sub-Agent (US-033), knowledge base (US-034, US-035), /knowledge/export (US-021). Total 38 user stories |
| Day 2 | Replaced RAG with layered memory + distillation. New agent_config table. Milestone 7 redesigned as distillation engine (US-039–041). Total 41 user stories |
| Post-Milestone 1 | Added score cache (US-042, US-042b, US-042c) after discovering live API calls are too slow for production use |
| Post-Milestone 1 | Renamed /agents to /scorers for 5 data pipelines. New /agents folder for genuine decision-making components. Architecture note added clarifying scorer vs agent distinction |
| Post-Milestone 1 | Added two-pass architecture: Pass 1 (scoring from cache) + Pass 2 (qualitative research via Claude web search on top 5 only). Research agents always on. New user stories US-046, US-047, US-049 |
| Post-Milestone 1 | Added Milestone 2.5 — Evals (US-043, US-044, US-045, US-048) between Milestone 2 and Milestone 3 |
| Post-Milestone 1 | Added agent activity animation (US-049) to frontend milestone |
| Post-Milestone 1 | Updated Claude API cost estimate to ~$0.15–0.20 per search including qualitative research pass |
| Post-Milestone 1 | Added V2 notes section: scorer confidence flags, RAG upgrade path |
| Post-Milestone 1 | Total user stories: 49 across 8 milestones (including Milestone 1.5 and 2.5) |
