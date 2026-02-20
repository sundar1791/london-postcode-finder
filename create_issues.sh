#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# create_issues.sh — Creates all 32 GitHub issues for london-postcode-finder
# Usage: export GITHUB_USER=$(gh api user --jq '.login') && bash create_issues.sh
# ---------------------------------------------------------------------------

if [[ -z "${GITHUB_USER:-}" ]]; then
  echo "ERROR: GITHUB_USER is not set."
  echo "Run: export GITHUB_USER=\$(gh api user --jq '.login')"
  exit 1
fi

REPO="$GITHUB_USER/london-postcode-finder"
echo "Creating issues in: $REPO"
echo ""

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
echo "--- Creating labels ---"

gh label create "milestone-0" --repo "$REPO" --color "0075ca" --description "M0: Developer Foundation"  --force
gh label create "milestone-1" --repo "$REPO" --color "e4e669" --description "M1: Data Foundation"       --force
gh label create "milestone-2" --repo "$REPO" --color "d73a4a" --description "M2: Agent Orchestration"   --force
gh label create "milestone-3" --repo "$REPO" --color "a2eeef" --description "M3: API Layer"             --force
gh label create "milestone-4" --repo "$REPO" --color "7057ff" --description "M4: Frontend"              --force
gh label create "milestone-5" --repo "$REPO" --color "008672" --description "M5: V1 Production Release" --force
gh label create "milestone-6" --repo "$REPO" --color "e99695" --description "M6: V2 Auth & Accounts"    --force
gh label create "claude-code" --repo "$REPO" --color "cfd3d7" --description "Built with Claude Code"    --force
gh label create "manual"      --repo "$REPO" --color "f9d0c4" --description "Manual / CLI step"         --force

echo "Labels created."
echo ""

# ---------------------------------------------------------------------------
# Helper — create one issue; args: title labels body
# ---------------------------------------------------------------------------
create_issue() {
  local title="$1"
  local labels="$2"
  local body="$3"
  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --label "$labels" \
    --body "$body"
}

# ---------------------------------------------------------------------------
# Milestone 0 — Developer Foundation
# ---------------------------------------------------------------------------
echo "--- Milestone 0: Developer Foundation ---"

create_issue \
  "US-001: Project scaffold — folder structure, requirements, config" \
  "milestone-0,claude-code" \
  "## User Story
As a developer, I want a clean project scaffold with the correct folder structure, dependencies, and config, so that I have a consistent starting point for building the application.

## Acceptance Criteria
- [ ] Folder structure created: /agents, /tools, /data, /prompts, /supabase, /frontend, /tests
- [ ] requirements.txt lists all required dependencies (langgraph, anthropic, httpx, fastapi, uvicorn, python-dotenv, supabase, pandas, pytest, pytest-asyncio)
- [ ] config.py loads env vars and defines 40 postcode districts and 5 scoring dimensions
- [ ] \`pytest tests/test_config.py\` passes"

create_issue \
  "US-002: GitHub repo, branch strategy, project board, all issues created" \
  "milestone-0,manual" \
  "## User Story
As a developer, I want a GitHub repo with branch protection, a project board, and all user stories tracked as issues, so that I can manage work and enforce good engineering practices from day one.

## Acceptance Criteria
- [ ] Public GitHub repo created at \$GITHUB_USER/london-postcode-finder
- [ ] main and dev branches exist; main is protected (PRs required)
- [ ] GitHub Project board created and linked to the repo
- [ ] All 32 issues created with correct labels"

create_issue \
  "US-003: Supabase local setup, initial schema migration" \
  "milestone-0,claude-code" \
  "## User Story
As a developer, I want a local Supabase instance with an initial schema migration, so that I can develop against a local database that mirrors production exactly.

## Acceptance Criteria
- [ ] \`supabase init\` run and /supabase folder scaffolded by the CLI
- [ ] \`supabase start\` launches successfully with Docker
- [ ] First migration file creates a \`searches\` table (search_id UUID, session_id, token_allocation JSONB, results JSONB, created_at)
- [ ] \`supabase db reset\` applies all migrations cleanly"

create_issue \
  "US-004: Vercel project init, environment variable structure" \
  "milestone-0,manual" \
  "## User Story
As a developer, I want a Vercel project linked to the repo with all environment variables configured, so that every push to main automatically deploys to production.

## Acceptance Criteria
- [ ] \`vercel link\` connects the local project to a Vercel project
- [ ] All required environment variables (ANTHROPIC_API_KEY, TFL_APP_KEY, SUPABASE_URL, SUPABASE_KEY) added to Vercel project settings via CLI
- [ ] \`vercel dev\` starts without errors
- [ ] Production deployment URL confirmed and accessible"

# ---------------------------------------------------------------------------
# Milestone 1 — Data Foundation
# ---------------------------------------------------------------------------
echo "--- Milestone 1: Data Foundation ---"

create_issue \
  "US-005: Postcode utility — postcodes.io, validate and get lat/lng" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a shared utility function that validates a UK postcode and returns its latitude and longitude, so that all scoring agents can geocode postcodes without duplicating API calls.

## Acceptance Criteria
- [ ] tools/postcode_utils.py created with \`validate_postcode()\` and \`get_lat_lng()\` functions
- [ ] Functions call postcodes.io API (no key required)
- [ ] Invalid postcodes raise a clear ValueError
- [ ] Unit test in tests/ confirms correct lat/lng for at least one known postcode (e.g. EC1A 1BB)"

create_issue \
  "US-006: ONS rent CSV — download, load into Supabase via migration" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want the ONS Private Rental Statistics CSV loaded into Supabase, so that the rent scorer can query rent data at runtime without reading a local CSV file.

## Acceptance Criteria
- [ ] ONS CSV downloaded and placed in /data (gitignored)
- [ ] Supabase migration creates a \`rent_data\` table with district and median_rent columns
- [ ] A load script populates \`rent_data\` from the CSV
- [ ] \`SELECT COUNT(*) FROM rent_data\` returns > 0 rows after migration"

create_issue \
  "US-007: Crime scorer — Police API, normalised score per postcode" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a crime scorer that returns a normalised 0–100 safety score per postcode, so that the orchestrator can include safety data in the final ranking.

## Acceptance Criteria
- [ ] agents/crime_agent.py created
- [ ] Calls data.police.uk API (no key required) using lat/lng from postcode utility
- [ ] Returns \`{\"postcode\": \"N1\", \"raw_value\": 234, \"normalised_score\": 72}\`
- [ ] Higher score = safer (inverse of crime count)
- [ ] Tested against 3 real postcodes and scores are between 0 and 100"

create_issue \
  "US-008: Green space scorer — Overpass API, parks within radius" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a green space scorer that returns a normalised 0–100 score per postcode, so that the orchestrator can weight green space in recommendations for users who value it.

## Acceptance Criteria
- [ ] agents/green_agent.py created
- [ ] Queries Overpass API (OpenStreetMap) for parks and green areas within 1km radius
- [ ] Returns \`{\"postcode\": \"SW4\", \"raw_value\": 3.2, \"normalised_score\": 68}\`
- [ ] raw_value is total green area in km² or feature count
- [ ] Tested against 3 real postcodes and scores are between 0 and 100"

create_issue \
  "US-009: Nightlife scorer — Overpass API, bars/restaurants within radius" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a nightlife scorer that returns a normalised 0–100 score per postcode, so that users who prioritise nightlife can filter for postcodes with high venue density.

## Acceptance Criteria
- [ ] agents/nightlife_agent.py created
- [ ] Queries Overpass API for bars, pubs, restaurants, and clubs within 500m radius
- [ ] Returns \`{\"postcode\": \"E1\", \"raw_value\": 47, \"normalised_score\": 85}\`
- [ ] raw_value is venue count
- [ ] Tested against 3 real postcodes and scores are between 0 and 100"

create_issue \
  "US-010: Transport scorer — TfL API, connectivity score per postcode" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a transport scorer that returns a normalised 0–100 connectivity score per postcode, so that users who commute to central London can prioritise well-connected areas.

## Acceptance Criteria
- [ ] agents/transport_agent.py created
- [ ] Calls TfL Unified API using TFL_APP_KEY from environment
- [ ] Returns \`{\"postcode\": \"NW3\", \"raw_value\": 4.2, \"normalised_score\": 78}\`
- [ ] raw_value is journey time to Zone 1 in minutes or TfL accessibility score
- [ ] Tested against 3 real postcodes and scores are between 0 and 100"

create_issue \
  "US-011: Rent scorer — ONS lookup, normalised score per postcode" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want a rent scorer that returns a normalised 0–100 affordability score per postcode, so that users with budget constraints can filter for more affordable areas.

## Acceptance Criteria
- [ ] agents/rent_agent.py created
- [ ] Queries rent_data table in Supabase by postcode district
- [ ] Returns \`{\"postcode\": \"HA1\", \"raw_value\": 1450, \"normalised_score\": 65}\`
- [ ] raw_value is median monthly rent in GBP; higher score = more affordable
- [ ] Tested against 3 real postcodes and scores are between 0 and 100"

create_issue \
  "US-012: Integration test — all 5 scorers against 5 real postcodes" \
  "milestone-1,claude-code" \
  "## User Story
As a developer, I want an integration test that runs all 5 scorers against 5 real postcodes, so that I can catch regressions before adding the agent orchestration layer.

## Acceptance Criteria
- [ ] tests/test_scorers.py created
- [ ] Runs all 5 scorer agents against E1, N1, SW4, W6, NW3
- [ ] Asserts each normalised_score is between 0 and 100
- [ ] Asserts expected keys (postcode, raw_value, normalised_score) present in each response
- [ ] \`pytest tests/test_scorers.py -v\` passes"

# ---------------------------------------------------------------------------
# Milestone 2 — Agent Orchestration
# ---------------------------------------------------------------------------
echo "--- Milestone 2: Agent Orchestration ---"

create_issue \
  "US-013: LangGraph state definition and graph scaffold" \
  "milestone-2,claude-code" \
  "## User Story
As a developer, I want a LangGraph graph scaffold with a typed state definition and node stubs, so that I can wire up real scoring agents into the graph in subsequent stories.

## Acceptance Criteria
- [ ] agents/graph.py created with a LangGraph StateGraph
- [ ] State schema defined: token_allocation, postcode_districts, scores, final_ranking
- [ ] Node stubs created for: orchestrator, crime, green, nightlife, transport, rent, synthesizer
- [ ] Graph compiles without errors (\`graph.compile()\` succeeds)
- [ ] Unit test confirms graph structure has the expected nodes and edges"

create_issue \
  "US-014: Parallel execution — all 5 scorers run simultaneously" \
  "milestone-2,claude-code" \
  "## User Story
As a developer, I want all 5 scoring agents to execute in parallel within the LangGraph graph, so that the pipeline completes faster since API calls don't block each other.

## Acceptance Criteria
- [ ] All 5 scorer nodes run in parallel using LangGraph fan-out pattern
- [ ] Results are collected and merged into shared state before the synthesizer node runs
- [ ] Total execution time is less than the sum of individual scorer times
- [ ] Timing verified with logs in a pytest integration test"

create_issue \
  "US-015: Orchestrator prompt design and Claude call" \
  "milestone-2,claude-code,manual" \
  "## User Story
As a developer, I want an orchestrator node that validates token allocations using Claude, so that invalid or malformed user input is caught before expensive scoring runs.

## Acceptance Criteria
- [ ] prompts/orchestrator.md system prompt written and reviewed manually
- [ ] Orchestrator node calls Claude API (claude-sonnet) with the raw token allocation input
- [ ] Claude returns structured JSON: \`{\"valid\": true, \"weights\": {\"safety\": 0.3, ...}}\`
- [ ] Total orchestrator token usage < 300 tokens per call"

create_issue \
  "US-016: Synthesizer prompt design and Claude call" \
  "milestone-2,claude-code,manual" \
  "## User Story
As a developer, I want a synthesizer node that ranks postcodes and writes human rationale using Claude, so that users receive personalised, readable recommendations rather than raw scores.

## Acceptance Criteria
- [ ] prompts/synthesizer.md system prompt written and reviewed manually
- [ ] Synthesizer node receives all 5 scorer outputs plus token weights as input
- [ ] Claude returns top 5 postcodes each with a one-paragraph rationale
- [ ] Output is valid JSON parseable by the FastAPI response model
- [ ] Total synthesizer token usage < 3,000 tokens per call"

create_issue \
  "US-017: End-to-end pipeline test — token input → top 5 in terminal" \
  "milestone-2,claude-code" \
  "## User Story
As a developer, I want a working end-to-end pipeline that takes a token allocation and prints the top 5 postcodes in the terminal, so that I can validate the full agent chain before building the HTTP layer.

## Acceptance Criteria
- [ ] scripts/run_pipeline.py accepts a token dict as a CLI argument
- [ ] Runs the full LangGraph pipeline against all 40 postcode districts
- [ ] Prints top 5 results with postcode name and rationale to stdout
- [ ] Completes successfully with real API keys present in .env"

# ---------------------------------------------------------------------------
# Milestone 3 — API Layer
# ---------------------------------------------------------------------------
echo "--- Milestone 3: API Layer ---"

create_issue \
  "US-018: FastAPI app scaffold, health check endpoint" \
  "milestone-3,claude-code" \
  "## User Story
As a developer, I want a FastAPI app with a /health endpoint, so that I have a working HTTP server to build the search endpoint on.

## Acceptance Criteria
- [ ] api.py created with a FastAPI app instance
- [ ] GET /health returns \`{\"status\": \"ok\"}\`
- [ ] \`uvicorn api:app --reload\` starts without errors
- [ ] CORS configured to allow requests from http://localhost:3000"

create_issue \
  "US-019: Search endpoint — accepts tokens, returns streaming response" \
  "milestone-3,claude-code" \
  "## User Story
As a developer, I want a POST /search endpoint that accepts a token allocation and streams results back, so that users see recommendations appear progressively rather than waiting for the full response.

## Acceptance Criteria
- [ ] POST /search accepts \`{\"safety\": 30, \"green_space\": 20, \"nightlife\": 10, \"transport\": 25, \"rent\": 15}\`
- [ ] Returns HTTP 422 if tokens do not sum to 100
- [ ] Runs the LangGraph pipeline and streams the synthesizer output via Server-Sent Events
- [ ] Streaming verified with \`curl -N http://localhost:8000/search\`"

create_issue \
  "US-020: Supabase save — every search persisted with session UUID" \
  "milestone-3,claude-code" \
  "## User Story
As a developer, I want every search automatically saved to Supabase with a session UUID, so that users can retrieve their search history in a later session.

## Acceptance Criteria
- [ ] searches table migration applied (search_id UUID PK, session_id TEXT, token_allocation JSONB, results JSONB, created_at TIMESTAMPTZ)
- [ ] POST /search writes the completed result to Supabase before the stream closes
- [ ] session_id is passed by the client in a request header (X-Session-ID)
- [ ] \`SELECT * FROM searches\` returns rows after a test search completes"

create_issue \
  "US-021: History endpoint — retrieve past searches by session UUID" \
  "milestone-3,claude-code" \
  "## User Story
As a developer, I want a GET /history/{session_id} endpoint that returns all past searches for a session, so that users can review and compare their previous postcode searches.

## Acceptance Criteria
- [ ] GET /history/{session_id} queries the searches table by session_id
- [ ] Returns a list of searches ordered by created_at DESC
- [ ] Returns an empty list (not 404) when the session has no history
- [ ] Tested with a session that has 2 or more saved searches"

# ---------------------------------------------------------------------------
# Milestone 4 — Frontend
# ---------------------------------------------------------------------------
echo "--- Milestone 4: Frontend ---"

create_issue \
  "US-022: Next.js scaffold with Vercel AI SDK, deploy shell to Vercel" \
  "milestone-4,claude-code" \
  "## User Story
As a developer, I want a Next.js app scaffold deployed as a live Vercel URL, so that I have a deployed foundation to build the UI on top of.

## Acceptance Criteria
- [ ] Next.js app created in /frontend using App Router
- [ ] Vercel AI SDK installed as a dependency
- [ ] \`vercel dev\` starts without errors from /frontend
- [ ] \`vercel deploy\` succeeds and returns a live URL
- [ ] Live URL returns HTTP 200 with a placeholder page"

create_issue \
  "US-023: Token allocation UI — sliders enforcing 100 token total" \
  "milestone-4,claude-code" \
  "## User Story
As a user, I want five sliders that always sum to exactly 100 tokens, so that I can specify exactly how much each lifestyle dimension matters to me without doing mental arithmetic.

## Acceptance Criteria
- [ ] Five sliders rendered with labels: Safety, Green Space, Nightlife, Transport, Rent
- [ ] Adjusting one slider redistributes remaining tokens proportionally across the others
- [ ] The total token count is always exactly 100 at all times
- [ ] Current token value is displayed as a number next to each slider
- [ ] Submit button is disabled until the allocation is valid"

create_issue \
  "US-024: Streaming results UI — postcodes appear as Claude writes" \
  "milestone-4,claude-code" \
  "## User Story
As a user, I want postcode recommendations to appear on screen as they are generated, so that I get immediate feedback and don't stare at a blank loading screen.

## Acceptance Criteria
- [ ] Submit button calls POST /search with the current token allocation
- [ ] A loading indicator appears while waiting for the first streamed token
- [ ] Postcode result cards appear one at a time as Claude streams the response
- [ ] Each card displays: postcode district name, overall score, and rationale paragraph"

create_issue \
  "US-025: History UI — past searches by session UUID" \
  "milestone-4,claude-code" \
  "## User Story
As a user, I want a history panel that shows my previous searches in the current browser session, so that I can compare different token allocations side by side.

## Acceptance Criteria
- [ ] session_id is generated on first page load and stored in localStorage
- [ ] History panel loads on page mount by calling GET /history/{session_id}
- [ ] Each past search entry is clickable and re-renders its saved results
- [ ] A friendly empty state is shown when no history exists yet"

create_issue \
  "US-026: Polish and mobile responsiveness" \
  "milestone-4,claude-code" \
  "## User Story
As a user, I want a UI that works well on both desktop and mobile screens, so that I can use the app on my phone while exploring London neighbourhoods in person.

## Acceptance Criteria
- [ ] Sliders are touch-friendly and usable on mobile without zooming
- [ ] Postcode result cards stack vertically on screens narrower than 768px
- [ ] Typography is legible at all screen sizes without horizontal scrolling
- [ ] Lighthouse mobile performance score is above 80"

# ---------------------------------------------------------------------------
# Milestone 5 — V1 Production Release
# ---------------------------------------------------------------------------
echo "--- Milestone 5: V1 Production Release ---"

create_issue \
  "US-027: Dev → main merge, production deployment" \
  "milestone-5,manual" \
  "## User Story
As a developer, I want the complete application merged to main and deployed to the production Vercel URL, so that the app is publicly accessible for the first time.

## Acceptance Criteria
- [ ] All Milestone 0–4 issues are closed and their PRs merged into dev
- [ ] Final PR from dev → main is created, reviewed, and merged
- [ ] Production Vercel deployment succeeds with all environment variables set
- [ ] Production URL responds with HTTP 200 and renders the full UI"

create_issue \
  "US-028: Error handling — invalid tokens, API failures, timeouts" \
  "milestone-5,claude-code" \
  "## User Story
As a user, I want clear error messages when the API fails or I submit invalid input, so that I know what went wrong and what action to take next.

## Acceptance Criteria
- [ ] Submitting a token total ≠ 100 shows an inline validation message before the API is called
- [ ] Scorer API timeouts (> 10s) return partial results with a visible warning banner
- [ ] TfL or Police API 5xx errors surface a human-readable message in the UI
- [ ] FastAPI always returns structured error responses — never raw Python tracebacks"

create_issue \
  "US-029: Public README and demo documentation" \
  "milestone-5,manual" \
  "## User Story
As a new visitor to the repository, I want a README that explains what the app does and how to run it, so that I can evaluate and run the project without contacting the author.

## Acceptance Criteria
- [ ] README includes: what the app does, architecture diagram, and the 5 scoring dimensions table
- [ ] Local setup steps are complete and verified to work from a fresh clone
- [ ] At least one screenshot or GIF showing the UI in action
- [ ] Production demo URL is included and accessible"

# ---------------------------------------------------------------------------
# Milestone 6 — V2: Auth and User Accounts
# ---------------------------------------------------------------------------
echo "--- Milestone 6: V2 Auth and User Accounts ---"

create_issue \
  "US-030: Supabase Auth — email + Google OAuth" \
  "milestone-6,claude-code,manual" \
  "## User Story
As a user, I want to log in with my email or Google account, so that my searches are tied to my identity and not just my current browser session.

## Acceptance Criteria
- [ ] Supabase Auth enabled and configured via CLI (not dashboard)
- [ ] Email and password sign-up and sign-in working end-to-end
- [ ] Google OAuth configured with client ID and secret, tested in browser
- [ ] Auth tokens are passed in the Authorization header on all authenticated API requests"

create_issue \
  "US-031: Schema migration — replace session UUID with user ID" \
  "milestone-6,claude-code" \
  "## User Story
As a developer, I want a database migration that links the searches table to authenticated user IDs, so that users own their search history regardless of which device they use.

## Acceptance Criteria
- [ ] Migration adds a nullable user_id UUID column to searches (FK → auth.users)
- [ ] Existing rows retain their session_id for backwards compatibility
- [ ] New searches from authenticated users write user_id instead of session_id
- [ ] Row-level security policy applied: users can only SELECT their own rows"

create_issue \
  "US-032: Frontend auth flow — login, logout, protected history" \
  "milestone-6,claude-code" \
  "## User Story
As a user, I want to log in, see my search history across all my devices, and log out securely, so that I can pick up where I left off from any device.

## Acceptance Criteria
- [ ] Login and signup page created with email/password form and Google OAuth button
- [ ] Supabase JS client handles token refresh automatically in the background
- [ ] History panel shows cross-device searches when the user is logged in
- [ ] Logging out clears all tokens from storage and redirects to the home page"

echo ""
echo "All 32 issues created successfully in $REPO."
