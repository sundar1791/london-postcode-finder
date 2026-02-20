# London Postcode Finder

## What This Project Does

London Postcode Finder scores 40 London postcode districts across five dimensions — Safety, Green Space, Nightlife, Transport, and Rent — by orchestrating a set of specialised AI sub-agents with LangGraph. Each agent calls a different data source (Metropolitan Police API, TfL Unified API, ONS rent data, etc.), normalises its results to a 0–100 scale, and hands off to a final Claude-powered ranking agent that combines the scores and returns a ranked list of postcodes tailored to the user's stated priorities.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User / Frontend                       │
│                    (Next.js — /frontend)                     │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI  (api.py)                          │
│             POST /score  ·  GET /districts                   │
└────────┬──────────────────────────────────────┬─────────────┘
         │ LangGraph orchestration               │ Supabase client
         ▼                                       ▼
┌────────────────────┐                ┌──────────────────────┐
│   Scoring Agents   │                │  Supabase (Postgres) │
│  /agents           │                │  cached scores table │
│                    │                └──────────────────────┘
│  safety_agent.py   │◄──── Met Police Open Data API
│  green_agent.py    │◄──── TfL Unified API (green space)
│  nightlife_agent.py│◄──── TfL / Google Places API
│  transport_agent.py│◄──── TfL Unified API (journey times)
│  rent_agent.py     │◄──── ONS Private Rental Market CSV
│                    │
│  ranking_agent.py  │◄──── Claude (Anthropic API) — final rank
└────────────────────┘
         │
         ▼
┌────────────────────┐
│   Shared Tools     │
│   /tools           │
│  tfl_client.py     │
│  postcode_utils.py │
└────────────────────┘
```

---

## Scoring Dimensions

| Dimension   | API / Data Source                              |
|-------------|------------------------------------------------|
| Safety      | Metropolitan Police Open Data API              |
| Green Space | TfL Unified API (parks & open spaces layer)   |
| Nightlife   | TfL / Google Places API (licensed venues)      |
| Transport   | TfL Unified API (journey time to Zone 1)       |
| Rent        | ONS Private Rental Market Statistics CSV       |

---

## Local Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd london-postcode-finder

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in all keys

# 5. Download the ONS rent CSV and place it in /data
#    (see data/README or project wiki for the exact URL)

# 6. Start the API server
python api.py
# Server runs at http://localhost:8000
```

---

## CLI Tools Required

| Tool        | Purpose                          | Install                        |
|-------------|----------------------------------|--------------------------------|
| `gh`        | GitHub CLI (PRs, issues)         | `brew install gh`              |
| `supabase`  | Supabase local dev & migrations  | `brew install supabase/tap/supabase` |
| `vercel`    | Deploy the Next.js frontend      | `npm i -g vercel`              |

---

## Contributing

**Branch naming**

```
feat/<short-description>     # new feature
fix/<short-description>      # bug fix
chore/<short-description>    # maintenance / tooling
```

**Commit format** (Conventional Commits)

```
feat(transport): add TfL journey-time normalisation
fix(rent): handle missing ONS rows for outer districts
chore(deps): bump anthropic to 0.25.0
```

**PR process**

1. Branch off `main`, make your changes, push.
2. Open a PR with `gh pr create` — fill in the summary and test plan.
3. All checks (pytest, lint) must pass before review.
4. Squash-merge into `main` after approval.
