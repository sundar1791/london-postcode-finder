# London Postcode Finder — Project Plan

## What We're Building

A web app that helps people new to London figure out where to live. Users are given 100 tokens to distribute across 5 lifestyle dimensions, and can optionally add a short natural language context (up to 500 characters) to personalise their search further — for example, "I'm a mother of two and need access to a nursery." A multi-agent system scores every London postcode district against those dimensions using free public APIs, with the orchestrator interpreting any natural language context and spawning additional agents or adjusting weights accordingly. Claude synthesises all results into 5 personalised recommendations with rationale.

Users can try different token allocations and contexts. A Redo button lets them iterate from their last query; Start New resets everything. Past searches are saved to the database for developer inspection but not shown in the UI until V2 (when auth is added). No login required in V1.

The agent system gets smarter over time — every query appends a structured learning to a knowledge base that the orchestrator and synthesizer read at the start of each subsequent query.

---

## The Agent Architecture

```
User submits token allocation (100 tokens) + optional context text (≤500 chars)
              ↓
    [Knowledge Loader] — NEW
    Fetches last 100 learnings from Supabase learnings table
    Compiles into markdown string, injects into graph state
              ↓
    [Orchestrator Agent — Claude Sonnet]
    Reads knowledge base + current input
    1. Validates tokens sum to 100
    2. Reads context text and classifies it:
       - Irrelevant / nonsensical → ignore, run standard pipeline
       - Weight hint (e.g. "love parks") → silently adjust token weights
       - New dimension (e.g. "need a nursery") → spawn Context Sub-Agent
              ↓
    ┌──────────────────────────────────────────────────┐
    │  5 Core Sub-Agents always run in PARALLEL        │
    │                                                  │
    │  Crime Agent      → UK Police API                │
    │  Green Agent      → Overpass (OSM)               │
    │  Nightlife Agent  → Overpass (OSM)               │
    │  Transport Agent  → TfL API                      │
    │  Rent Agent       → ONS CSV lookup               │
    │                                                  │
    │  + Context Sub-Agent (spawned only when needed)  │
    │    → Overpass query (nurseries, schools, etc.)   │
    │    → Web search fallback (community, culture)    │
    └──────────────────────────────────────────────────┘
              ↓
    Each agent returns: {postcode, raw_value, normalised_score}
              ↓
    [Synthesizer Agent — Claude Sonnet]
    Reads knowledge base + all scores + context
    Weights scores, picks top 5, writes rationale
              ↓
    [Knowledge Writer] — NEW
    Extracts learnings from this query:
    - What context intent was classified as
    - What methodology / Overpass query was used
    - What token weight adjustments were made
    Appends structured rows to learnings table in Supabase
              ↓
    Results + search saved to Supabase
    Response streamed to Next.js frontend
```

**Claude API usage per search:**
- Orchestrator call: ~600 tokens in (includes knowledge), ~150 out
- Context Sub-Agent call: ~300 tokens in, ~100 out — only when needed
- Synthesizer call: ~3,000 tokens in (includes knowledge), ~900 out — ~$0.06 per search

Standard searches without context remain at ~$0.05. Every call slightly increases as the knowledge base grows — this is intentional and the value compounds. Knowledge is capped at last 100 entries to control token growth.

### The Orchestrator's Context Classification Logic

This is the most important new piece of reasoning in the system. The orchestrator receives the context text and makes one of three decisions:

**Ignore** — context is nonsensical, offensive, or completely unrelated to London living (e.g. "I like pizza"). Pipeline runs as normal with the original token weights.

**Weight adjustment** — context maps to an existing dimension and should shift the token weights silently. The orchestrator recalculates weights before dispatching.
- "I'm terrified of crime" → boost safety tokens
- "I need to be outdoors" → boost green space tokens
- "I'm on a very tight budget" → boost rent tokens

**Spawn Context Sub-Agent** — context requires data that no existing agent covers. The orchestrator extracts the core intent and passes it as a structured query.
- "I need a nursery nearby" → Overpass query: `amenity=kindergarten` within 500m
- "I want to be near a mosque" → Overpass query: `amenity=place_of_worship + religion=muslim`
- "I need good schools" → Overpass query: `amenity=school` within 1km
- "I want a strong Tamil community" → Web search fallback

The Context Sub-Agent returns scores in the same `{postcode, normalised_score}` format as every other agent, so the Synthesizer needs no special handling.

---

## The 5 Scoring Dimensions

| Dimension | API | Cost |
|---|---|---|
| Safety | UK Police API (data.police.uk) | Free, no key |
| Green Space | Overpass API (OpenStreetMap) | Free, no key |
| Nightlife | Overpass API (OpenStreetMap) | Free, no key |
| Transport | TfL Unified API | Free, key required |
| Rent | ONS Private Rental Statistics CSV | Free, no key |
| Postcode backbone | postcodes.io | Free, no key |

---

## The LangGraph State Object

```python
class LondonSearchState(TypedDict):
    # Input
    token_allocation: dict      # {safety: 40, green: 20, ...} — original from user
    context_text: str           # raw user input (≤500 chars, empty string if none)
    session_id: str             # browser-generated UUID

    # Knowledge base (loaded first by Knowledge Loader, read by orchestrator + synthesizer)
    knowledge_base: str         # compiled markdown: distilled_brain + last 10 raw learnings

    # Orchestrator output
    adjusted_allocation: dict   # token weights after context adjustment
    context_analysis: dict      # {relevant: bool, type: "ignore"|"weight"|"spawn",
                                #  intent: str, overpass_query: str|None}

    # Sub-agent output
    postcode_scores: dict       # raw scores per postcode per dimension
    weighted_scores: dict       # after applying adjusted allocation

    # Synthesizer output
    top_5: list                 # final ranked postcodes with rationale

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

Claude and Gemini don't have persistent memory — they have a context window. Every message re-sends the full conversation history until it gets too long, at which point older content gets compressed into summaries while recent messages stay verbatim. The model always has: a compressed representation of old history + the full detail of recent events. This layered approach is the right answer to the same problem your system faces: how do you give an agent the benefit of accumulated experience without blowing the context window?

Your system uses the same pattern:

```
Distilled brain  ←→  Compressed old history  (stable heuristics, always injected)
Last 10 raw entries  ←→  Recent verbatim messages  (specific, recent, high-recency value)
```

### Three Types of Knowledge — Different Shapes, Different Needs

**Methodological knowledge** — how to handle classes of request. "When a user asks about nurseries, use Overpass `amenity=kindergarten` within 500m." Grows slowly, highly compressible into rules.

**Domain knowledge** — facts about London. "SW postcodes consistently score poorly on rent. E1 scores high on nightlife but low on green space." Moderately stable, compressible into heuristics.

**Pattern knowledge** — user archetypes. "Users allocating >50 tokens to safety often implicitly care about schools even when they don't mention it." Emerges over time, becomes most valuable after hundreds of queries.

All three types accumulate in the raw learnings table and get distilled into the brain. This is intentional — the distillation process is where the agent turns experience into wisdom.

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

The synthesizer prompt (US-016) must enforce this writing discipline when it populates `new_learnings`.

### How the Layered Memory System Works

```
Query starts
      ↓
[Knowledge Loader]
  → Read distilled_brain from agent_config (always — compressed heuristics)
  → Read last 10 rows from learnings ORDER BY created_at DESC (recent specifics)
  → Combine into knowledge_base markdown string, inject into state
      ↓
[Orchestrator] reads knowledge_base as system context
      ↓
[Sub-agents run in parallel]
      ↓
[Synthesizer] reads knowledge_base as system context
  → Writes top 5 recommendations
  → Populates new_learnings list in state
      ↓
[Knowledge Writer]
  → Inserts new_learnings rows into learnings table
  → Increments query_count in agent_config
  → If query_count % 50 == 0: trigger distillation
      ↓
[Distillation — every 50 queries]
  → Claude reads ALL raw learnings rows
  → Rewrites distilled_brain as compressed markdown (~500 words of heuristics and rules)
  → Updates agent_config.distilled_brain and agent_config.last_distilled
      ↓
Next query starts with a smarter brain
```

### The Distillation Process in Detail

Distillation is a Claude call that runs asynchronously after every 50th query (not in the critical path — it doesn't block the user). It reads all raw learnings and produces a compressed brain with this structure:

```markdown
## Methodological Rules
- For nursery/childcare requests: Overpass amenity=kindergarten within 500m. Confirmed 12 times.
- For religious institution requests: Overpass amenity=place_of_worship + religion filter. 8 times.
- For "good schools" requests: Overpass amenity=school within 1km, weight by count. 6 times.

## London Domain Knowledge
- SW postcodes (SW1-SW20): strong on safety and green space, consistently poor on rent.
- E1/E2/E3: high nightlife, low green space, improving on rent.
- SE22/SE21: strong family profile — green space, safety, school proximity.

## User Archetypes
- High safety (>40 tokens): often implicitly values schools. Consider boosting if children mentioned.
- High nightlife (>40 tokens): correlates with younger users, less concerned with transport reliability.
- Balanced allocation (15-25 per dimension): hardest to synthesise, needs strongest contextual rationale.

## Synthesizer Insights
- Postcodes that score well across 4+ dimensions make stronger recommendations than those
  excelling in 1-2 with weaknesses elsewhere — users respond better to balanced profiles.
```

This is your portable knowledge artifact. The `/knowledge/export` endpoint returns this brain plus all raw entries as a formatted `knowledge.md` file, reusable in future projects as a starting-point system prompt.

### Why Not RAG?

RAG (vector similarity search) is the right answer when the knowledge base is large and heterogeneous — thousands of entries across many diverse domains where only a small subset is relevant to any given query. Your domain is deliberately narrow: London postcodes, ~20-30 distinct context intent types, fixed scoring dimensions. After 1,000 queries, you'll have deep repeated coverage of a small number of patterns — exactly the scenario where distillation produces denser, more useful heuristics than retrieval would. The distilled brain gets *smarter*, not just longer. RAG would give you a more sophisticated way to retrieve mediocre raw entries; distillation gives you genuinely compressed wisdom. RAG remains a valid upgrade path if this framework is later applied to a much broader domain.

### Exporting as knowledge.md

The `/knowledge/export` endpoint compiles the distilled brain plus all raw entries into a clean, formatted markdown file. This is your portable knowledge asset — the accumulated intelligence of every query the system has run, structured for reuse in future projects.

---


## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Agent orchestration | LangGraph | Parallel node execution, shared state |
| LLM | Claude API (Sonnet) | Orchestrator + Synthesizer only |
| Sub-agents | Pure Python + httpx | No LLM needed for API calls |
| Backend | FastAPI | Lightweight, async, Vercel-compatible |
| Frontend | Next.js + Vercel AI SDK | Streaming responses, fast to build |
| Database | Supabase (Postgres) | Free tier, CLI-managed, auth-ready for V2 |
| Hosting | Vercel | Auto-deploy on merge to main |
| Infra management | GitHub CLI + Supabase CLI + Vercel CLI | No dashboard clicks |

---

## Repository and Branch Strategy

```
main          ← production, always deployable, never commit directly
  └── dev     ← integration branch, all PRs merge here first
        └── feature/US-001-project-scaffold
        └── feature/US-002-github-setup
        └── feature/US-003-supabase-setup
        └── ...
```

**Rule:** Every day ends with at least one PR merged into `dev`.
**Rule:** Never commit directly to `main` or `dev`.
**Rule:** Every PR closes a GitHub Issue (user story).

---

## Daily Workflow (CLI-first)

```bash
# Morning: pick your story
gh issue view 7

# ALWAYS start a feature branch from dev, never from main
# ALWAYS pull first to get the latest integrated work
git checkout dev
git pull origin dev
git checkout -b feature/US-007-crime-scorer

# Build using Claude Code
claude

# Commit with closing reference
git add .
git commit -m "feat: crime scorer with Police API normalised output (closes #7)"

# Push and open PR via CLI — always targeting dev, never main
git push origin feature/US-007-crime-scorer
gh pr create --base dev --title "US-007: Crime scorer" --body "Closes #7"

# Review, then merge via CLI
gh pr merge --squash --delete-branch

# Check deployment
vercel ls
```

---

## Database Migration Discipline

Every schema change is a migration file — never a manual dashboard change.

```bash
# Create migration
supabase migration new add_searches_table

# Apply locally
supabase db reset

# Push to production
supabase db push
```

The `/supabase/migrations/` folder is the complete, reproducible history of your database schema.

---

## Full Backlog

### Milestone 0 — Developer Foundation
*Goal: Repo, tooling, and infra set up. Nothing works yet but everything is wired.*

| Issue | User Story | Notes |
|---|---|---|
| US-001 | Project scaffold — folder structure, requirements, config | Claude Code ✅ |
| US-002 | GitHub repo, branch strategy, project board, all issues created | Manual + CLI ✅ |
| US-003 | Supabase local setup — searches table + learnings table + agent_config table migrations | CLI + Claude Code |
| US-004 | Vercel project init, environment variable structure | CLI |

### Milestone 1 — Data Foundation
*Goal: All 5 scorers work independently. No agents, no Claude. Just verified data pipelines.*

| Issue | User Story | Notes |
|---|---|---|
| US-005 | Postcode utility — postcodes.io, validate and get lat/lng | Claude Code |
| US-006 | ONS rent CSV — download, load into Supabase via migration | Claude Code |
| US-007 | Crime scorer — Police API, normalised score per postcode | Claude Code |
| US-008 | Green space scorer — Overpass API, parks within radius | Claude Code |
| US-009 | Nightlife scorer — Overpass API, bars/restaurants within radius | Claude Code |
| US-010 | Transport scorer — TfL API, connectivity score per postcode | Claude Code |
| US-011 | Rent scorer — ONS lookup, normalised score per postcode | Claude Code |
| US-012 | Integration test — all 5 scorers against 5 real postcodes | Claude Code |

### Milestone 2 — Agent Orchestration
*Goal: LangGraph pipeline works end-to-end in terminal. Claude is in the loop. Knowledge base is live.*

| Issue | User Story | Notes |
|---|---|---|
| US-013 | LangGraph state definition — full TypedDict including knowledge and learnings fields | Claude Code |
| US-014 | Parallel execution — all 5 scorers run simultaneously as graph nodes | Claude Code |
| US-015 | Orchestrator prompt — validates tokens, reads knowledge, classifies context | Manual + Claude Code |
| US-016 | Synthesizer prompt — reads knowledge, writes rationale + populates new_learnings | Manual + Claude Code |
| US-017 | End-to-end pipeline test — token input + context → top 5 in terminal | Claude Code |
| US-033 | Context Sub-Agent — Overpass or web search, spawned dynamically by orchestrator | Claude Code |
| US-034 | Knowledge Loader — reads distilled_brain from agent_config + last 10 raw learnings, compiles into knowledge_base markdown string injected into state | Claude Code |
| US-035 | Knowledge Writer — inserts new_learnings rows, increments query_count in agent_config, triggers distillation when query_count % 50 == 0 | Claude Code |

### Milestone 3 — API Layer
*Goal: Pipeline accessible via HTTP with streaming.*

| Issue | User Story | Notes |
|---|---|---|
| US-018 | FastAPI app scaffold, health check endpoint | Claude Code |
| US-019 | Search endpoint — accepts tokens + context_text, returns streaming response | Claude Code |
| US-020 | Supabase save — persists tokens, context_text, and results with session UUID | Claude Code |
| US-021 | Knowledge export endpoint — GET /knowledge/export returns knowledge.md file | Claude Code |

### Milestone 4 — Frontend
*Goal: A real browser UI. No terminal required.*

| Issue | User Story | Notes |
|---|---|---|
| US-022 | Next.js scaffold with Vercel AI SDK, deploy shell to Vercel | Claude Code |
| US-023 | Token allocation UI — sliders enforcing 100 total + context textarea + 500 char counter | Claude Code |
| US-024 | Streaming results UI — postcodes appear as Claude writes | Claude Code |
| US-025 | Redo button — repopulates last token allocation, clears context box | Claude Code |
| US-026 | Start New button — resets all sliders to 0, clears context box and results | Claude Code |
| US-027 | Polish and mobile responsiveness | Claude Code |

### Milestone 5 — V1 Production Release
*Goal: Live, shareable, stable.*

| Issue | User Story | Notes |
|---|---|---|
| US-028 | Dev → main merge, production deployment | CLI |
| US-029 | Error handling — invalid tokens, irrelevant context, API failures, timeouts | Claude Code |
| US-030 | Public README and demo documentation | Manual |

### Milestone 6 — V2: Auth, History, and User Accounts
*Goal: Users log in, own their searches, view history, compare across sessions.*

| Issue | User Story | Notes |
|---|---|---|
| US-031 | Supabase Auth — email + Google OAuth via CLI | CLI + Claude Code |
| US-032 | Schema migration — replace session UUID with user ID in searches table | Claude Code |
| US-036 | History endpoint — retrieve past searches by user ID | Claude Code |
| US-037 | History UI — display past searches per logged-in user | Claude Code |
| US-038 | Frontend auth flow — login, logout, protected history | Claude Code |

### Milestone 7 — V3: Distillation Engine
*Goal: Knowledge Writer triggers automatic distillation every 50 queries. Claude reads all raw learnings and rewrites the distilled_brain as compressed heuristics. Agents get genuinely smarter rather than just accumulating longer context.*

| Issue | User Story | Notes |
|---|---|---|
| US-039 | Distillation prompt — Claude reads all learnings rows and writes compressed brain as structured markdown covering methodological rules, London domain knowledge, and user archetypes | Manual + Claude Code |
| US-040 | Distillation trigger — async job called by Knowledge Writer every 50 queries, updates agent_config.distilled_brain and last_distilled | Claude Code |
| US-041 | Distillation quality test — compare orchestrator decisions before and after distillation against a fixed set of test queries, assert improvement | Claude Code |

---

## Infrastructure Flexibility Principles

1. **Supabase is the single source of truth for data.** Adding new features means adding migrations, not rearchitecting.
2. **Each sub-agent is one file.** Adding a new scoring dimension = one new file + one graph node change.
3. **The Context Sub-Agent is a template.** Any new Overpass query type the orchestrator learns to classify requires no architecture change — just a new query pattern added to the knowledge base.
4. **The knowledge base is portable.** The `/knowledge/export` endpoint produces a standalone `knowledge.md` file reusable in future projects with zero modification.
5. **History is gated behind auth.** Data is always saved; it's only surfaced in the UI once users have accounts. This keeps V1 simple without losing any data.
6. **Prompts live in `/prompts/*.md`.** Improving orchestration logic or synthesis quality doesn't touch production code.
7. **Environment variables are the only difference between local and production.** `supabase start` + `vercel dev` mirrors prod exactly.
8. **Every infrastructure change goes through CLI.** No dashboard clicks = reproducible, version-controlled infra.

---
---

# Day 1 Execution Guide — US-001 and US-002

**Goal by end of Day 1:** A GitHub repo with `main` and `dev` branches, a GitHub Project board with all 32 issues created, and the project scaffold merged as your first PR.

**What you'll run manually:** The commands that teach you how GitHub CLI, branching, and project boards work.
**What Claude Code builds:** The scaffold files — there's no learning value in typing boilerplate by hand.

---

## Before Anything: Install Your CLI Toolkit

Run each of these and confirm they succeed before moving on.

```bash
# GitHub CLI
brew install gh
gh auth login
# Follow the prompts: select GitHub.com → HTTPS → Login with browser
gh --version  # should print a version number

# Supabase CLI
brew install supabase/tap/supabase
supabase login
supabase --version

# Vercel CLI
npm install -g vercel
vercel login
vercel --version
```

**Why you're doing this manually:** These are the three tools that will manage your entire infrastructure. Understanding how to authenticate each one is foundational — not something to delegate to Claude Code.

---

## Get Your Free API Keys (Do This Now)

Takes 10 minutes. Painful to do mid-build.

| Service | Where | What you need |
|---|---|---|
| Anthropic | console.anthropic.com | API Key |
| TfL | api.tfl.gov.uk → Register | App Key |
| Supabase | supabase.com → New Project | Project URL + anon public key |
| Groq (optional) | console.groq.com | API Key (for non-critical steps, saves Claude credits) |

Police API, Overpass, and postcodes.io need no keys — just call them directly.

---

## US-001: Project Scaffold

### Step 1 — Create your project folder

```bash
mkdir london-postcode-finder
cd london-postcode-finder
```

### Step 2 — Run Claude Code to build the scaffold

Open Claude Code inside your project folder:

```bash
claude
```

Paste this prompt:

```
Create a Python project scaffold for a "London Postcode Finder" app.

Folder structure to create:
- /agents          — one file per scoring sub-agent
- /tools           — shared API utility functions used by multiple agents
- /data            — ONS rent CSV will live here (add .gitkeep)
- /prompts         — Claude system prompt .md files (add .gitkeep)
- /supabase        — Supabase CLI will manage this folder
- /frontend        — Next.js app will go here later (add .gitkeep)
- /tests           — pytest test files

Files to create:

1. requirements.txt with:
   langgraph, anthropic, httpx, fastapi, uvicorn,
   python-dotenv, supabase, pandas, pytest, pytest-asyncio

2. .env.example with a comment explaining each variable:
   ANTHROPIC_API_KEY=        # Anthropic Console → API Keys
   TFL_APP_KEY=              # api.tfl.gov.uk → Register
   SUPABASE_URL=             # Supabase project settings → API
   SUPABASE_KEY=             # Supabase project settings → API (anon public)
   GROQ_API_KEY=             # console.groq.com (optional, for non-critical agent steps)

3. .gitignore ignoring:
   .env, __pycache__, .DS_Store, node_modules, *.pyc,
   /data/*.csv, .vercel, *.egg-info, dist/, .pytest_cache/

4. config.py in root that:
   - Loads all env vars using python-dotenv
   - Defines LONDON_POSTCODE_DISTRICTS: a list of 40 postcode districts
     covering inner and outer London across all compass directions and zones.
     Include a mix of: central (EC1, WC1, SW1, W1), inner (N1, E1, SE1, SW4,
     W6, NW3), and outer (E17, N13, SE9, SW16, W13, NW9, HA1, BR1, CR0,
     DA1, EN1, IG1, KT1, RM1, SM1, TW1, UB1). Aim for good zone spread.
   - Defines SCORING_DIMENSIONS as a dict:
     {"safety": "Safety", "green_space": "Green Space",
      "nightlife": "Nightlife", "transport": "Transport", "rent": "Rent"}

5. README.md with sections:
   - What this project does (one clear paragraph)
   - Architecture overview (copy the ASCII diagram from the plan)
   - The 5 scoring dimensions and which API each uses
   - Local setup instructions (pip install, copy .env, run api.py)
   - CLI tools required (gh, supabase, vercel)
   - Contributing guide (branch naming, PR process, commit format)

6. tests/__init__.py (empty)
7. tests/test_config.py with one test: assert len(LONDON_POSTCODE_DISTRICTS) >= 30

Do not write any agent logic, API calls, or database code yet.
Show me the complete folder structure when done using the tree command.
```

### Step 3 — Review what Claude Code built

After it finishes, read these two files yourself before anything else:

```bash
cat config.py
cat README.md
```

Ask yourself: do the postcode districts cover London well geographically? Does the README make sense in plain English? If anything is off, ask Claude Code to fix it before moving on.

Then run your first test:

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your actual keys in .env

python -m pytest tests/ -v
```

The test should pass. If it fails, Claude Code fixes it before you move on.

---

## US-002: GitHub Repo and Project Board

This is mostly manual — because understanding how GitHub CLI works is the point.

### Step 0 — Confirm your GitHub identity and set a session variable

Run this first, before any other command in this section:

```bash
# Confirm gh CLI knows who you are
gh api user --jq '.login'
# Should print your GitHub username

# Set it as a shell variable so every command below uses it automatically
export GITHUB_USER=$(gh api user --jq '.login')
echo $GITHUB_USER  # confirm it printed correctly
```

**Why this matters:** Several commands need your GitHub username explicitly. Using `$GITHUB_USER` instead of hardcoding your name means these commands are reproducible — they work for any authenticated user without modification. This is the professional pattern.

> Note: You'll need to re-run the `export` line if you open a new terminal session, since shell variables don't persist between sessions.

### Step 1 — Initialise git and create the GitHub repo

```bash
# Inside london-postcode-finder/
git init
git add .
git commit -m "chore: initial project scaffold (US-001)"

# Create the GitHub repo under your account and push in one command
gh repo create $GITHUB_USER/london-postcode-finder --public --source=. --remote=origin --push
```

**What just happened:** `gh repo create` created the repo on GitHub, set it as your remote called `origin`, and pushed your first commit — all without opening a browser.

### Step 2 — Set up your branch strategy

```bash
# Rename current branch to main (if it's called master)
git branch -M main

# Create dev branch from main and push it
git checkout -b dev
git push origin dev

# Set dev as the default branch for PRs
gh repo edit --default-branch dev
```

Verify on GitHub: you should now see both `main` and `dev` branches, with `dev` as default.

### Step 3 — Create branch protection rules

```bash
# Protect main — no direct pushes, require PR
gh api repos/$GITHUB_USER/london-postcode-finder/branches/main/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":0}' \
  --field enforce_admins=false \
  --field restrictions=null \
  --field required_status_checks=null
```

**Why this matters:** Even working alone, protecting `main` forces you to go through the PR process for every change. This builds the muscle memory of professional engineering.

### Step 4 — Create the GitHub Project board

```bash
# Create a new project board
gh project create --owner "@me" --title "London Postcode Finder"
```

Note the project number from the output (e.g., Project #1). You'll use it next.

### Step 5 — Create all 33 issues via CLI

This is the Claude Code step for US-002. Open Claude Code and paste:

```
I need to create 33 GitHub issues for my project using the GitHub CLI.
The repo is $GITHUB_USER/london-postcode-finder.
(Run: export GITHUB_USER=$(gh api user --jq '.login') before this script if not already set)

Write a bash script called create_issues.sh that creates all these issues
using `gh issue create` with appropriate --title, --body, and --label flags.

Create these labels first using `gh label create`:
- "milestone-0" (color: #0075ca)
- "milestone-1" (color: #e4e669)
- "milestone-2" (color: #d73a4a)
- "milestone-3" (color: #a2eeef)
- "milestone-4" (color: #7057ff)
- "milestone-5" (color: #008672)
- "milestone-6" (color: #e99695)
- "claude-code" (color: #cfd3d7)
- "manual" (color: #f9d0c4)

Each issue body should follow this format:
## User Story
As a [role], I want [goal], so that [reason].

## Acceptance Criteria
- [ ] [criterion 1]
- [ ] [criterion 2]
- [ ] [criterion 3]

Here are the 32 issues to create:
[paste the full backlog table from the project plan]

After the script is created, make it executable and run it.
```

### Step 6 — Add issues to your Project board

```bash
# List your issues to get their numbers
gh issue list

# Add them to the project board (repeat for each issue, or ask Claude Code
# to write a loop that adds all issues to project number 1)
gh project item-add 1 --owner "@me" --url [issue-url]
```

Ask Claude Code to write a small bash script that adds all open issues to your project board in one go.

### Step 7 — Your first PR

Day 1 is a one-time exception to the normal flow. Because we built the scaffold
directly on main before the branch strategy existed, we skip the feature branch
step and PR dev directly into main to establish the baseline.

From Day 2 onwards, you never do this — all PRs go feature → dev, and
only dev → main for production releases.

```bash
# Make sure you're on dev and all changes are committed
git checkout dev
git add .
git commit -m "chore: clean up scaffold, gitignore and env example"
git push origin dev

# PR dev into main — one-time exception to establish the baseline
gh pr create \
  --base main \
  --title "Milestone 0: Developer foundation (US-001, US-002)" \
  --body "Closes #1, Closes #2. Project scaffold, GitHub repo setup, branch strategy, and full issue backlog created." \
  --label "milestone-0"

# Review the PR on GitHub, then merge via CLI
gh pr merge --squash
```

### Step 8 — Confirm your Day 1 is done

```bash
# Should show 33 open issues
gh issue list --state open | wc -l

# Should show main and dev branches
git branch -a

# Should show your project board
gh project list --owner "@me"

# Should show the merged PR
gh pr list --state merged
```

---

## What You've Learned on Day 1

By the end of Day 1 you should be able to explain in your own words:

- Why `dev` and `main` are separate branches and what each protects
- What a user story acceptance criteria is for
- How `gh issue create`, `gh pr create`, and `gh pr merge` replace GitHub's web UI
- Why the project scaffold separates `/agents`, `/tools`, and `/prompts` into different folders
- What `config.py` does differently from `.env`

If any of those feel unclear, ask before Day 2. Day 2 (US-003: Supabase setup) builds directly on this foundation.

---

## Day 2 Preview

US-003 and US-004: get Supabase running locally with Docker, write your first two database migrations (searches table + learnings table, both RAG-ready schemas), and initialise Vercel with your project. By the end of Day 2 you'll have a local database that mirrors production exactly — and your first Vercel deployment (a blank page, but a deployed blank page).

> **Note on US-003:** Three migrations needed. The searches table includes `context_text TEXT CHECK (char_length(context_text) <= 500)`. The learnings table has all text columns written as full sentences (no shorthand). The agent_config table has a single row with `distilled_brain TEXT` (starts empty) and `query_count INTEGER DEFAULT 0`.

---

## Changelog

| Date | Change |
|---|---|
| Day 1 | Initial plan created — 32 user stories across 6 milestones |
| Day 2 | Added open-ended context text feature: Context Sub-Agent (US-033), updated orchestrator/synthesizer/state/DB/frontend stories. Total 33 user stories |
| Day 2 | Added knowledge base: learnings table, Knowledge Loader (US-034) + Writer (US-035), /knowledge/export (US-021). Removed history UI from V1 → V2 (US-036, US-037). Added Redo (US-025) + Start New (US-026). Total 38 user stories |
| Day 2 | Replaced RAG with layered memory + distillation. Knowledge base now: distilled_brain (compressed heuristics, rewritten every 50 queries) + last 10 raw learnings (recency). New agent_config table. Milestone 7 redesigned as distillation engine (US-039–041). Total 41 user stories across 7 milestones |
