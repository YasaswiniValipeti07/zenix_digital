# Digital Risk Protection Platform (Prototype)

Sentinel is a Django and SQLite prototype for trusted brand-asset management, explainable username/app candidate screening, reviewer investigations, and database-backed reports.

> **Scope:** This is not a live monitoring service and does not scrape social networks, messaging services, or app stores. The built-in detector is a local, deterministic heuristic using RapidFuzz and submitted evidence. No generative AI provider is connected. Results are leads for human review, never proof that an account is malicious.

## Requirements

- Python 3.10 or later
- pip
- Dependencies listed in `requirements.txt`

## Setup on Windows PowerShell

Open PowerShell in the project folder, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

If PowerShell blocks activation scripts, use the virtual-environment interpreter directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/>. The new migrations are additive and preserve existing brands/results. Back up `db.sqlite3` before applying pending schema changes. `migrate` writes to that SQLite file; only run it on a database you are authorized to change.

## Demo

1. Register a brand with official usernames and, optionally, official web URLs.
2. On **Social Media Monitoring**, enter usernames manually or import UTF-8 CSV with `username` and optional `display_name`, `description` columns.
3. On **App Risk Intelligence**, register official app references (app name/publisher/package/listing) and analyze a submitted app manually or with CSV (`app_name` plus optional metadata columns).
4. Local analysis excludes exact registered usernames, official URL hosts, package IDs and listing URLs before risk scoring. Review signals, score and evidence in **Investigation Center**.
5. Set review status to Pending, Under Review, or Reviewed. **Reports & Analytics** filters stored records by brand/date and exports CSV.

Brand registration uses Post/Redirect/Get and has case-insensitive duplicate protection. Submit each scan intentionally; scans are saved as separate result records.

## Features

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

- `config/` — Django project settings and root URL routing.
- `monitor/` — models, core and portal views, forms, explainable detection service, migrations, tests, templates, and static CSS.
- `db.sqlite3` — local development database.
- `manage.py` — Django management entry point.
- `name_detector.py`, `brand_checker.py`, `first_program.py`, root `index.html`, and root `style.css` — earlier project files retained; the dashboard served by Django uses `monitor/templates/index.html` and `monitor/static/monitor/style.css`.
- `requirements.txt` — Python dependencies.

## Checks and tests

Run Django's checks and tests (tests use a temporary test database):

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

The included Django development settings are for local prototyping only. Before deployment, use a secret key from an environment variable, disable `DEBUG`, configure `ALLOWED_HOSTS`, HTTPS/security settings, a production database, and authentication/authorization for reviewers. Do not commit credentials or API tokens. No third-party API integrations are configured in this project.

## Deploying to Vercel

Vercel detects Django from the root `manage.py` and the configured `WSGI_APPLICATION`. The `pyproject.toml` build hook runs the additive Django migrations before the deployment serves requests; this prevents a first-request 500 such as `no such table: monitor_brand` when the deployment has no local SQLite file. No custom `vercel.json` is needed for this Django runtime.

First provision a managed PostgreSQL database (for example, connect a Postgres/Neon storage integration to the Vercel project) and copy its pooled or serverless connection URL. Configure these values in Vercel **Project → Settings → Environment Variables** for Production (and Preview if needed):

- `SECRET_KEY`: one generated, stable, random Django secret. Keep it private and do not regenerate it for each deploy.
- `DEBUG`: `False`.
- `DATABASE_URL`: a persistent managed PostgreSQL connection string. Vercel's SQLite filesystem is not durable/writable across serverless invocations. The build migration will run against this database, so back up any existing remote data and use a database dedicated to this app.
- `ALLOWED_HOSTS`: optional comma-separated extra hosts; `*.vercel.app` and the current `VERCEL_URL` are included automatically.
- `CSRF_TRUSTED_ORIGINS`: optional comma-separated HTTPS origins when using a custom domain.

Redeploy after adding the environment variables. `STATIC_ROOT` allows Vercel to collect Django static assets. `requirements.txt` includes `dj-database-url` and `psycopg` to connect to PostgreSQL. On Vercel, `DATABASE_URL` is mandatory: without it Django now stops with a clear configuration error rather than trying to open SQLite under the read-only `/var/task` deployment bundle (the cause of `sqlite3.OperationalError: unable to open database file`). Locally, development continues to use `db.sqlite3`.

If a deployment still shows a 500 after setup, open **Vercel → Deployments → latest deployment → Functions/Runtime Logs** and use the first Python traceback. Common actionable messages are missing `SECRET_KEY`, failed PostgreSQL connection/credentials, or database migrations failing during the build.
