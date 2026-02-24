# London Postcode Finder

A multi-agent web app that recommends where to live in London based on your lifestyle priorities — and gets smarter with every search.

---

## What It Does

You distribute 100 tokens across five dimensions that matter to you:

| Dimension | What it measures |
|---|---|
| Safety | Crime rate per capita (UK Police API) |
| Green Space | Parks and open space within walking distance (OpenStreetMap) |
| Nightlife | Bars, restaurants, and venues nearby (OpenStreetMap) |
| Transport | TfL connectivity score (TfL Unified API) |
| Rent | Median private rental cost (ONS data) |

You can also add a short note in plain English — "I'm a mother of two and need a nursery nearby" or "I want to be close to a mosque." The orchestrator reads this and either adjusts the token weights accordingly or spins up a specialised agent to score postcodes on that dimension using live map data.

The system scores all 40 London postcode districts, weights them by your priorities, and returns the top 5 with a written rationale for each.

---

## How It Gets Smarter Over Time

Every query teaches the system something. After each search, a Knowledge Writer agent saves a structured learning to a database table — what the user wanted, how the agent handled it, what the outcome was. Every 50 queries, a Distillation Engine reads all learnings and rewrites a compressed `distilled_brain` — a set of heuristics and rules that the orchestrator and synthesiser read at the start of every subsequent query.

The result is a system that, over time, gets better at interpreting open-ended requests, recognising user archetypes, and writing more accurate rationale.

You can export the accumulated knowledge at any time as a `knowledge.md` file — portable and reusable in future projects.

---

## Architecture

```
User: 100 tokens across 5 dimensions + optional context (≤500 chars)
              ↓
    [Knowledge Loader]
    Reads distilled brain + last 10 raw learnings from Supabase
              ↓
    [Orchestrator — Claude Sonnet]
    Validates tokens, classifies context:
    - Nonsensical → ignore
    - Maps to existing dimension → adjust token weights
    - New dimension → spawn Context Sub-Agent
              ↓
    ┌──────────────────────────────────────────────────┐
    │  5 Core Sub-Agents (always, in parallel)         │
    │  Crime · Green Space · Nightlife · Transport · Rent │
    │                                                  │
    │  + Context Sub-Agent (when needed)               │
    │    Overpass query or web search fallback         │
    └──────────────────────────────────────────────────┘
              ↓
    [Synthesiser — Claude Sonnet]
    Weights scores, picks top 5, writes rationale
    Populates new learnings for knowledge base
              ↓
    [Knowledge Writer]
    Saves learnings to Supabase, triggers distillation every 50 queries
              ↓
    Results streamed to Next.js frontend
```

**Claude is called twice per search** (orchestrator + synthesiser). Everything else is pure Python — zero LLM cost.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Claude API (Sonnet) |
| Data fetching | Pure Python + httpx |
| Backend | FastAPI |
| Frontend | Next.js + Vercel AI SDK |
| Database | Supabase (Postgres) |
| Hosting | Vercel |

---

## Database Tables

Three tables, all managed via migration files in `/supabase/migrations/`:

**`searches`** — every query a user runs. Tokens, context text, results, session ID.

**`learnings`** — one row per query, written by the Knowledge Writer. Full-sentence descriptions of what was asked, what the agent did, and what the outcome was. The raw material for distillation.

**`agent_config`** — a single row. Holds `distilled_brain` (the compressed heuristics rewritten every 50 queries) and `query_count`.

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (running)
- GitHub CLI (`gh`)
- Supabase CLI (`supabase`)
- Vercel CLI (`vercel`)

### Steps

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/london-postcode-finder.git
cd london-postcode-finder

# Python dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Fill in your actual keys — see .env.example for what's needed

# Start local Supabase (requires Docker running)
supabase start

# Apply database migrations
supabase db reset

# Run backend
uvicorn api.main:app --reload

# Run frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:3000` for the app.
Open `http://localhost:54323` for Supabase Studio (local database dashboard).

---

## API Keys Required

| Key | Where to get it | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | Pay per use (~$0.05/search) |
| `TFL_APP_KEY` | api.tfl.gov.uk | Free |
| `SUPABASE_URL` + `SUPABASE_KEY` | Your Supabase project dashboard | Free tier |

All other APIs (UK Police, OpenStreetMap/Overpass, ONS, postcodes.io) are free with no key required.

---

## Project Structure

```
london-postcode-finder/
├── agents/           # Orchestrator, synthesiser, context sub-agent
├── tools/            # Knowledge loader and writer
├── scorers/          # 5 core scoring functions (pure Python)
├── prompts/          # Orchestrator and synthesiser prompt files (.md)
├── api/              # FastAPI app
├── frontend/         # Next.js app
├── supabase/
│   └── migrations/   # All database schema changes — never edit DB directly
├── tests/
├── config.py         # Postcode districts, scoring dimensions
└── .env.example      # Required environment variables (no real keys)
```

---

## Development Workflow

```bash
# Start from dev, always pull first
git checkout dev && git pull origin dev
git checkout -b feature/US-XXX-description

# Build
claude  # Claude Code for implementation

# Commit with issue reference
git add .
git commit -m "feat: description (closes #N)"

# PR to dev (never directly to main)
git push origin feature/US-XXX-description
gh pr create --base dev --title "US-XXX: Title" --body "Closes #N"
gh pr merge --squash --delete-branch
```

**Branch rules:**
- `main` — production only, never commit directly
- `dev` — integration, all PRs land here first
- `feature/*` — one branch per user story

**Database rules:**
- Every schema change is a migration file in `/supabase/migrations/`
- Never edit the database via the Studio dashboard
- `supabase db reset` applies all migrations locally
- `supabase db push` applies pending migrations to production

---

## Milestones

| Milestone | What gets built |
|---|---|
| 0 — Foundation | Repo, Supabase, Vercel wired up |
| 1 — Data | All 5 scorers working independently |
| 2 — Agents | LangGraph pipeline end-to-end, knowledge base live |
| 3 — API | FastAPI with streaming search endpoint |
| 4 — Frontend | Next.js UI with sliders, context box, Redo/Start New |
| 5 — V1 Launch | Production deployment, error handling |
| 6 — V2 Auth | Login, user accounts, search history |
| 7 — V3 Distillation | Automated knowledge distillation every 50 queries |

---

## Knowledge Export

Once the system has run queries, you can export its accumulated intelligence:

```bash
GET /knowledge/export
```

Returns a `knowledge.md` file containing the current distilled brain plus all raw learnings. Portable — use it as a starting-point system prompt for other projects in the same domain.
