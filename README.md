
# Digital Risk Protection Platform (Prototype)

Sentinel is a Vite frontend with an Express API and Supabase database for trusted brand-asset management and explainable candidate screening. A Django prototype remains in the repository for local reference; the Render/Vercel deployment uses the Node API.

> **Scope:** This is not a live monitoring service and does not scrape social networks, messaging services, or app stores. The built-in detector is a local, deterministic heuristic using RapidFuzz and submitted evidence. No generative AI provider is connected. Results are leads for human review, never proof that an account is malicious.

## Requirements

- Node.js 22.12 or later and npm for the Vite/Express deployment stack.
- A Supabase project for database-backed API behavior.
- Python 3.10 or later only if running the retained Django prototype.

## Run the Vite frontend and API locally on Windows PowerShell

Install dependencies and create a local environment file:

```powershell
npm ci
Copy-Item .env.example .env
```

Edit `.env` with the Supabase project URL and API key. Keep `.env` private. Then run the backend:

```powershell
npm start
```

In another terminal, start Vite and open <http://localhost:5173/>:

```powershell
npm run dev
```

Vite proxies `/api` requests to the local API on port 3000. Without Supabase settings, the API health route remains available and data routes report a clear configuration error.

## Run the retained Django prototype locally

The earlier Django application is retained in `monitor/` but is not used by the Vercel/Render deployment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Back up `db.sqlite3` before applying schema migrations.

## Demo

1. Register a brand with official usernames and, optionally, official web URLs.
2. On **Social Media Monitoring**, enter usernames manually or import UTF-8 CSV with `username` and optional `display_name`, `description` columns.
3. On **App Risk Intelligence**, register official app references (app name/publisher/package/listing) and analyze a submitted app manually or with CSV (`app_name` plus optional metadata columns).
4. Local analysis excludes exact registered usernames, official URL hosts, package IDs and listing URLs before risk scoring. Review signals, score and evidence in **Investigation Center**.
5. Set review status to Pending, Under Review, or Reviewed. **Reports & Analytics** filters stored records by brand/date and exports CSV.

Brand registration uses Post/Redirect/Get and has case-insensitive duplicate protection. Submit each scan intentionally; scans are saved as separate result records.

## Features

The Vite workspace supports brand registration, candidate analysis, recent findings, inventory, and review-status updates through the Express API. The following fuller workflow details describe the retained Django prototype:

- Clean White + Royal Blue enterprise dashboard with eight connected pages: Security Overview, Brand Inventory, AI-assisted Threat Detection, Social Media Monitoring, App Risk Intelligence, Investigation Center, Reports & Analytics, and Settings & Integrations.
- Database-backed KPI cards, inventory, queue and reports; no fabricated totals.
- Explainable local heuristic analysis: RapidFuzz name similarity, support/security/verification terms, optional profile text, app package/publisher/host differences, evidence and input-dependent confidence limitations.
- Exact official usernames, explicitly registered official website hosts and registered app identifiers are excluded before risk triage.
- Bounded UTF-8 CSV imports (1 MB, maximum 100 rows) and manual input.
- Brand registration with server-side validation and case-insensitive duplicate prevention.
- Official usernames stored alongside each brand; usernames are comma/newline separated, with optional `@` prefixes.
- Manual batch username comparison (maximum 100 candidates per submission).
- Cautious classification: Official asset, High similarity — review, Possible match — review, and Low similarity. Scores are triage signals, not conclusions.
- Case-insensitive matching; spaces are ignored, and underscores are ignored for similarity comparison but retained when checking exact official-account identity.
- Official assets receive Official status, no similarity score, and are excluded from suspicious-match triage.
- Persisted investigation records with Pending, Under Review, and Reviewed states.
- Django CSRF protection, ORM queries, escaped template values, and mobile-friendly dashboard tables/forms.

Invalid submissions are server-validated. Table search filters visible rows only. No scheduled jobs, external source APIs, image/logo analysis, or generative-AI analysis are implemented or simulated.

## Project structure

- `src/` and root `index.html` — Vite frontend.
- `index.js`, `detection.js`, and `risk.js` — Express API and explainable local analysis.
- `supabase_schema.sql` — Supabase tables and views required by the API.
- `render.yaml` — Render web-service blueprint for the API.
- `vercel.json` and `vite.config.mjs` — Vercel static build and local API proxy.
- `config/`, `monitor/`, and `manage.py` — retained Django prototype, not used by the split deployment.

## Checks and tests

Run the Node API tests and build the Vite frontend:

```powershell
npm test
npm run build
```

For the retained Django prototype only, run its checks and tests (tests use a temporary test database):

```powershell
python manage.py check
python manage.py test monitor
```

Tests cover registration persistence/validation, username parsing and similarity, official username/URL/app exclusions, explainable risk fields, scan and CSV persistence, page rendering, actual database metrics, safe CSV output, CSRF, and review-state updates.

## Pages and integrations

- **Security Overview** — actual database counts and navigation to the workflows.
- **Brand Inventory** — brands, official usernames/URLs and registered official apps.
- **AI-assisted Threat Detection** — a local, explainable heuristic engine; it is not a generative-AI integration.
- **Social Media Monitoring** and **App Risk Intelligence** — manual input and reviewer-supplied CSV only.
- **Investigation Center** — saved evidence, explanations and human-managed statuses.
- **Reports & Analytics** — actual saved records, brand/date filters and formula-neutralized CSV export.
- **Settings & Integrations** — honest connection status. No authorized live platform or app-store source is configured.

No scheduler runs because no source integrations are configured. A future authorized provider can be added behind a source adapter with credentials loaded from environment configuration.

## Production limitations and security

This is a prototype, not a production-hardened service. The Express API currently has no user authentication or per-user authorization; CORS origin restrictions are not authentication. Add an appropriate authentication layer and Supabase Row Level Security policies before exposing sensitive data or using it with untrusted users. Keep database credentials server-side and never commit them. No third-party monitoring integrations are configured.

## Deploying the frontend to Vercel and API to Render

The deployable stack is **Vite static frontend → Express API → Supabase**. Vercel serves the built `dist/` files; Render runs `node index.js`. The frontend never receives the Supabase key.

### 1. Prepare Supabase

Create or open the Supabase project, then run `supabase_schema.sql` in its SQL Editor. Copy the project URL and the API key used by the backend. Do not commit either value. The schema must be installed before using the API.

### 2. Deploy the API on Render

Create a Render **Blueprint** from this repository and use `render.yaml`, or create a Node web service with:

- Build command: `npm ci`
- Start command: `npm start`
- Health check path: `/health`

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the Render service environment. The service listens on Render's `PORT`. Render's free service may sleep between requests.

### 3. Deploy the frontend on Vercel

Import the same repository into Vercel. Use the repository root; `vercel.json` configures the Vite build (`npm ci`, `npm run build`, output `dist`). Add this Vercel environment variable before deploying:

- `VITE_API_BASE_URL`: the Render service origin, for example `https://sentinel-api.onrender.com` (no trailing slash).

After Vercel assigns the frontend URL, set `FRONTEND_URL` on Render to that exact origin, such as `https://your-project.vercel.app`. For additional preview/custom-domain origins, set `ALLOWED_ORIGINS` to a comma-separated list. Redeploy/restart the Render service after changing its environment.

For local development, run `npm start` in one terminal and `npm run dev` in another. Vite proxies `/api` calls to `http://localhost:3000`; set `API_PROXY_TARGET` if your local API uses another address. Run `npm test` and `npm run build` to verify the project.
