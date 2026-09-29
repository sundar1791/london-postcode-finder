# MANUAL_STEPS — going live

Everything here needs your accounts or a dashboard. Do the steps in order; each one says what "done" looks like. Commands assume you're in the repo root with `.venv` activated.

Hosted Supabase project: **london-postcode** (ref `vpqwqoasougowxbnminu`, Frankfurt).

---

## 0. Generate the two secrets once

```bash
python -c "import secrets; print('ADMIN_TOKEN=' + secrets.token_urlsafe(32)); print('CRON_SECRET=' + secrets.token_urlsafe(32))"
```

Keep both in your password manager. `ADMIN_TOKEN` goes on Railway only. `CRON_SECRET` goes on both Railway and Vercel, with the same value.

---

## 1. Anthropic Console: cap spend

1. **Top up credit first.** The build used up the balance: the last e2e run failed with "Your credit balance is too low to access the Anthropic API". Go to **Billing → Buy credits**; $20–30 covers the warm-up plus a few days of demo traffic.
2. Go to https://console.anthropic.com → **Settings → Limits** (or **Billing → Spend limits**).
3. Set a **monthly spend limit of £30–50**, or the USD equivalent (about $40–60).
4. Optionally add an email alert at 50%.

Done when: the limit shows on the Limits page and `RUN_E2E_TESTS=1 python -m pytest tests/test_pipeline_e2e.py` passes locally. Each search costs about $0.15–0.20, so the default `DAILY_SEARCH_CAP=100` means about $20/day at worst.

---

## 2. Supabase: hosted database

### 2a. Restore the project if it's paused
Go to https://supabase.com/dashboard/project/vpqwqoasougowxbnminu. If it shows **Paused**, click **Restore project** and wait for it to go green (1–2 minutes).

### 2b. Push the three new migrations
New in this branch: `distillation_history`, `spawn_cache`, and extra `searches` columns (`adjusted_allocation`, `top_5`, `duration_ms`, `status`).

```bash
supabase link --project-ref vpqwqoasougowxbnminu     # only if not already linked
export $(grep SUPABASE_DB_PASSWORD .env | xargs) && supabase db push --password $SUPABASE_DB_PASSWORD
```

Done when: `supabase migration list` shows every migration in both the Local and Remote columns.

### 2c. Confirm `cached_scores` has 200 rows
Put the hosted values in your shell. Get them from Dashboard → **Project Settings → API**: the Project URL and the `anon` `public` key.

```bash
export HOSTED_URL=https://vpqwqoasougowxbnminu.supabase.co
export HOSTED_KEY=<anon public key>

curl -s -o /dev/null -D - "$HOSTED_URL/rest/v1/cached_scores?select=district" \
  -H "apikey: $HOSTED_KEY" -H "Authorization: Bearer $HOSTED_KEY" -H "Prefer: count=exact" -H "Range: 0-0" \
  | grep -i content-range
```

Done when: it prints `content-range: 0-0/200`.

**If the count isn't 200**, reimport from the snapshot committed at `data/cached_scores_snapshot.json`, taken from the working local cache:

```bash
curl -s -X POST "$HOSTED_URL/rest/v1/cached_scores?on_conflict=district,dimension" \
  -H "apikey: $HOSTED_KEY" -H "Authorization: Bearer $HOSTED_KEY" \
  -H "Content-Type: application/json" -H "Prefer: resolution=merge-duplicates,return=minimal" \
  --data @data/cached_scores_snapshot.json && echo "reimported"
```

Then re-run the count check.

### 2d. (Optional) `rent_data` on hosted
Only the monthly score refresh reads `rent_data`; searches read `cached_scores`. To load it, temporarily point `.env` at hosted (`SUPABASE_URL` and `SUPABASE_KEY`). Every module calls `load_dotenv(override=True)`, so shell exports are ignored. Then run:

```bash
python tools/load_rent_data.py      # expect "Upserted 40 row(s) into rent_data."
```

Switch `.env` back to local (`http://127.0.0.1:54321`) afterwards.

---

## 3. Railway: backend

1. https://railway.com → **New Project → Deploy from GitHub repo** → pick `london-postcode-finder`.
2. Service → **Settings**:
   - **Source → Branch**: `main` once merged. Use `feature/v1-live-prototype` if you want to try it first.
   - **Root Directory**: leave empty (repo root). Railway picks up `Dockerfile` and `railway.json`, including the health check on `/api/health`.
   - **Networking → Generate Domain**. Copy the URL, e.g. `https://london-postcode-finder-production.up.railway.app`.
3. Service → **Variables**. Add these; `PORT` is set by Railway:

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your key |
   | `SUPABASE_URL` | `https://vpqwqoasougowxbnminu.supabase.co` |
   | `SUPABASE_KEY` | hosted anon public key |
   | `TFL_APP_KEY` | your TfL key |
   | `ADMIN_TOKEN` | from step 0 |
   | `CRON_SECRET` | from step 0 |
   | `FRONTEND_ORIGIN` | `http://localhost:3000` for now (replaced in step 5) |
   | `DISTILL_EVERY_N` | `10` |
   | `RATE_LIMIT_PER_HOUR` | `5` |
   | `DAILY_SEARCH_CAP` | `100` |

4. Deploy, then check:
   ```bash
   export API=https://<your-railway-domain>
   curl -s $API/api/health        # {"status":"ok","db":"ok",...}
   curl -s $API/api/knowledge | head -c 200
   ```

Done when: health returns `"db":"ok"`.

> Keep the service at **1 replica**. The rate limiter and distillation lock live in process memory.

---

## 4. Vercel: frontend

1. https://vercel.com/new → import `london-postcode-finder`.
2. **Root Directory**: `frontend`. Framework preset: Next.js (auto-detected).
3. **Environment Variables** (Production and Preview):

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the Railway URL, e.g. `https://london-postcode-finder-production.up.railway.app` |
   | `BACKEND_URL` | the same Railway URL |
   | `CRON_SECRET` | from step 0, the same as Railway |

4. **Deploy**. Copy the production URL, e.g. `https://london-postcode-finder.vercel.app`.
5. **Settings → Cron Jobs** should list `/api/cron/refresh-scores` at `0 0 1 * *`, picked up from `frontend/vercel.json`.

The existing Vercel project was originally created with the FastAPI preset at the repo root. Its framework must be **Next.js** and its root directory **`frontend`**, or builds fail. Or with the CLI from the repo root: `vercel env add NEXT_PUBLIC_API_URL production` (repeat for each variable), then `vercel deploy --prod`.

---

## 5. Point CORS at the Vercel URL

Railway → Variables → set:

```
FRONTEND_ORIGIN=https://london-postcode-finder.vercel.app,https://postcodes.sundarsubramanian.xyz
```

Include the custom domain if you'll add it in step 6. If you want Vercel preview deployments to work too, also set:

```
FRONTEND_ORIGIN_REGEX=^https://london-postcode-finder-[a-z0-9-]+-sundar1791s-projects\.vercel\.app$
```

Redeploy the Railway service, which happens automatically when variables change.

Done when: the Vercel site loads `/learning` without a "can't be reached" message.

---

## 6. (Optional) Custom domain `postcodes.sundarsubramanian.xyz`

1. Vercel → Project → **Settings → Domains → Add** `postcodes.sundarsubramanian.xyz`.
2. Cloudflare → `sundarsubramanian.xyz` → **DNS → Add record**:

   | Type | Name | Target | Proxy status | TTL |
   |---|---|---|---|---|
   | `CNAME` | `postcodes` | `cname.vercel-dns.com` | **DNS only** (grey cloud) | Auto |

   If Vercel's Domains page shows a project-specific target (e.g. `xxxx.vercel-dns-017.com`), use that instead.
3. Wait for Vercel to show **Valid Configuration** and issue the certificate.
4. Make sure the domain is in Railway's `FRONTEND_ORIGIN` (step 5).

---

## 7. Warm up hosted

Run these through the deployed API, so they hit hosted Supabase without touching your `.env`:

```bash
export API=https://<your-railway-domain>
export ADMIN_TOKEN=<from step 0>      # bypasses the rate limit for these runs

python tools/seed_demo.py --yes --api $API       # 12 searches, ~12–15 min, ~$2–3; distillation fires at search 10
python tools/record_demo_run.py --api $API       # re-records the fallback against hosted (optional; a local recording is already committed)
```

If you re-record, commit the updated `api/demo/recorded_run.json` and `frontend/public/recorded_run.json`, then redeploy both.

To force a distillation at any time:

```bash
curl -s -X POST $API/api/admin/distill -H "X-Admin-Token: $ADMIN_TOKEN"
```

Done when: `https://<vercel-url>/learning` shows **Current rules**, plus at least one entry under **How the rules changed**.

---

## 8. Smoke test on the live site

1. **Adjust:** Balanced preset, context "I'm terrified of crime". The timeline shows "Adjusted your weights" with Safety raised.
2. **Spawn:** Family preset, "I need a nursery nearby for my daughter". The context agent step reads "(from a recent cached run)" after the seed. "Why these results" lists any districts removed by the filter.
3. **Ignore:** Young professional, "I like pizza". It reads "Context noted, weights unchanged".
4. **Rate limit:** run 6 searches from one browser within an hour. The sixth shows "You've reached the hourly limit", with **See a recorded example run**. The replay is labelled "Recorded example run".
5. **Recorded fallback:** on the home page, click "Watch a recorded example".
6. **Cron:** `curl -s -H "Authorization: Bearer $CRON_SECRET" https://<vercel-url>/api/cron/refresh-scores` returns 202 `accepted`. This triggers a real refresh that takes about 30–60 minutes, so run it once only.

---

## 9. Merge

```bash
gh pr view --web          # the PR from feature/v1-live-prototype → dev
gh pr merge <N> --squash  # once happy
gh pr create --base main --head dev --title "Release: v1 live prototype" --body "Promotes the v1 live prototype to main."
gh pr merge <M> --merge
```

After merging to `main`, set Railway's source branch to `main` if you pointed it at the feature branch earlier. Vercel deploys `main` to production automatically.
