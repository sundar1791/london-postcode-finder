# London Postcode Finder — Project Plan

## What We're Building

A web app that helps people new to London figure out where to live. Users are given 100 tokens to distribute across 5 lifestyle dimensions. A multi-agent system scores every London postcode district against those dimensions using free public APIs, then Claude synthesises the results into 5 personalised recommendations with rationale.

Users can try different token allocations and compare results over time. No login required in V1.

---

## The Agent Architecture

```
User submits token allocation (100 tokens across 5 dimensions)
              ↓
    [Orchestrator Agent — Claude Sonnet]
    Validates tokens, normalises weights, dispatches sub-agents
              ↓
    ┌─────────────────────────────────────────┐
    │  5 Sub-Agents run in PARALLEL           │
    │                                         │
    │  Crime Agent      → UK Police API       │
    │  Green Agent      → Overpass (OSM)      │
    │  Nightlife Agent  → Overpass (OSM)      │
    │  Transport Agent  → TfL API             │
    │  Rent Agent       → ONS CSV lookup      │
    └─────────────────────────────────────────┘
              ↓
    Each agent returns: {postcode, raw_value, normalised_score}
              ↓
    [Synthesizer Agent — Claude Sonnet]
    Weights scores by token allocation, ranks all postcodes,
    picks top 5, writes human rationale for each
              ↓
    Results saved to Supabase (Postgres)
    Response streamed to Next.js frontend
```

**Claude API is used exactly twice per search:**
- Orchestrator call: ~200 tokens in, ~100 out (tiny, cheap)
- Synthesizer call: ~2,000 tokens in, ~800 out (~$0.04 per search)

Everything between those two calls is pure Python — zero LLM cost.

---

## The 5 Scoring Dimensions

| Dimension | API | Cost |
| --- | --- | --- |
| Safety | UK Police API (data.police.uk) | Free, no key |
| Green Space | Overpass API (OpenStreetMap) | Free, no key |
| Nightlife | Overpass API (OpenStreetMap) | Free, no key |
| Transport | TfL Unified API | Free, key required |
| Rent | ONS Private Rental Statistics CSV | Free, no key |
| Postcode backbone | postcodes.io | Free, no key |

---

## Tech Stack

| Layer | Tool | Why |
| --- | --- | --- |
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

# Create feature branch from dev
git checkout dev && git pull origin dev
git checkout -b feature/US-007-crime-scorer

# Build using Claude Code
claude

# Commit with closing reference
git add .
git commit -m "feat: crime scorer with Police API normalised output (closes #7)"

# Push and open PR via CLI
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
| --- | --- | --- |
| US-001 | Project scaffold — folder structure, requirements, config | Claude Code |
| US-002 | GitHub repo, branch strategy, project board, all issues created | Manual + CLI |
| US-003 | Supabase local setup, initial schema migration | CLI + Claude Code |
| US-004 | Vercel project init, environment variable structure | CLI |

### Milestone 1 — Data Foundation
*Goal: All 5 scorers work independently. No agents, no Claude. Just verified data pipelines.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-005 | Postcode utility — postcodes.io, validate and get lat/lng | Claude Code |
| US-006 | ONS rent CSV — download, load into Supabase via migration | Claude Code |
| US-007 | Crime scorer — Police API, normalised score per postcode | Claude Code |
| US-008 | Green space scorer — Overpass API, parks within radius | Claude Code |
| US-009 | Nightlife scorer — Overpass API, bars/restaurants within radius | Claude Code |
| US-010 | Transport scorer — TfL API, connectivity score per postcode | Claude Code |
| US-011 | Rent scorer — ONS lookup, normalised score per postcode | Claude Code |
| US-012 | Integration test — all 5 scorers against 5 real postcodes | Claude Code |

### Milestone 2 — Agent Orchestration
*Goal: LangGraph pipeline works end-to-end in terminal. Claude is in the loop.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-013 | LangGraph state definition and graph scaffold | Claude Code |
| US-014 | Parallel execution — all 5 scorers run simultaneously | Claude Code |
| US-015 | Orchestrator prompt design and Claude call | Manual + Claude Code |
| US-016 | Synthesizer prompt design and Claude call | Manual + Claude Code |
| US-017 | End-to-end pipeline test — token input → top 5 in terminal | Claude Code |

### Milestone 3 — API Layer
*Goal: Pipeline accessible via HTTP with streaming.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-018 | FastAPI app scaffold, health check endpoint | Claude Code |
| US-019 | Search endpoint — accepts tokens, returns streaming response | Claude Code |
| US-020 | Supabase save — every search persisted with session UUID | Claude Code |
| US-021 | History endpoint — retrieve past searches by session UUID | Claude Code |

### Milestone 4 — Frontend
*Goal: A real browser UI. No terminal required.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-022 | Next.js scaffold with Vercel AI SDK, deploy shell to Vercel | Claude Code |
| US-023 | Token allocation UI — sliders enforcing 100 token total | Claude Code |
| US-024 | Streaming results UI — postcodes appear as Claude writes | Claude Code |
| US-025 | History UI — past searches by session UUID | Claude Code |
| US-026 | Polish and mobile responsiveness | Claude Code |

### Milestone 5 — V1 Production Release
*Goal: Live, shareable, stable.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-027 | Dev → main merge, production deployment | CLI |
| US-028 | Error handling — invalid tokens, API failures, timeouts | Claude Code |
| US-029 | Public README and demo documentation | Manual |

### Milestone 6 — V2: Auth and User Accounts
*Goal: Users log in, own their searches, compare across sessions.*

| Issue | User Story | Notes |
| --- | --- | --- |
| US-030 | Supabase Auth — email + Google OAuth via CLI | CLI + Claude Code |
| US-031 | Schema migration — replace session UUID with user ID | Claude Code |
| US-032 | Frontend auth flow — login, logout, protected history | Claude Code |

---

## Infrastructure Flexibility Principles

1. **Supabase is the single source of truth for data.** Adding new features means adding migrations, not rearchitecting.
2. **Each sub-agent is one file.** Adding a new scoring dimension = one new file + one graph node change.
3. **Prompts live in \****\`/prompts/*.md`**\*\*.** Improving Claude's behaviour doesn't touch production code.
4. **Environment variables are the only difference between local and production.** `supabase start` + `vercel dev` mirrors prod exactly.
5. **Every infrastructure change goes through CLI.** No dashboard clicks = reproducible, version-controlled infra.

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
| --- | --- | --- |
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

### Step 5 — Create all 32 issues via CLI

This is the Claude Code step for US-002. Open Claude Code and paste:

```
I need to create 32 GitHub issues for my project using the GitHub CLI.
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

Now we do the PR ritual properly for the first time — so you know the pattern for every day from here.

```bash
# You're currently on dev branch with the scaffold committed
# Create a feature branch for US-001 retroactively
git checkout main
git checkout -b feature/US-001-US-002-foundation

# Cherry-pick or the scaffold is already here since we built on main initially
# Simpler: just ensure dev has the scaffold, then PR dev into main

git checkout dev
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
# Should show 32 open issues
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

US-003 and US-004: get Supabase running locally with Docker, write your first database migration (the `searches` table schema), and initialise Vercel with your project. By the end of Day 2 you'll have a local database that mirrors production exactly — and your first Vercel deployment (a blank page, but a deployed blank page).
