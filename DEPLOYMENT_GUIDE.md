# Digital Risk Protection - Node.js + Supabase Deployment Guide

## Prerequisites
- Node.js installed (v18+ recommended)
- Supabase account at https://supabase.com
- Git (optional, for version control)

## Step 1: Create Supabase Project
1. Go to [supabase.com](https://supabase.com) and sign up/in
2. Click "New project"
3. Enter project name (e.g., "digital-risk-protection")
4. Choose a region close to your users
5. Click "Create project"

## Step 2: Get API Credentials
1. Go to **Settings → API**
2. Copy **Project URL** (looks like: `https://abc123.supabase.co`)
3. Copy **anon public** key (a long string starting with `eyJ...`)
4. These are required for the `.env` file

## Step 3: Set Up Database Schema
1. In your Supabase project, go to **SQL Editor**
2. Click "New query"
3. Copy and paste the contents of `supabase_schema.sql`
4. Click "Run"
5. You should see tables created: `brands`, `official_apps`, `monitoring_results`

## Step 4: Configure Environment Variables
Create a `.env` file in the project root:

```bash
# Copy the example first
copy .env.example .env

# Then edit .env with your values:
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR-PUBLIC-ANON-KEY
SECRET_KEY=change-this-to-a-secure-random-value
PORT=3000
```

**Important**: Add `.env` to `.gitignore` (already done)

## Step 5: Install Dependencies
```bash
npm install
```

## Step 6: Start the Server
```bash
npm start
```

The server will run at `http://localhost:3000`

## Step 7: Test the API
Health check: `curl http://localhost:3000/`

Expected response:
```json
{
  "name": "Digital Risk Protection API",
  "status": "running",
  "version": "2.0.0",
  "database": "Supabase"
}
```

## Step 8: Deploy to Vercel
```bash
# Install Vercel CLI (if not installed)
npm install -g vercel

# Login
vercel login

# Deploy
vercel
```

Or connect your GitHub repository to Vercel directly for automatic deployments.

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/brands` | GET | List all brands with result counts |
| `/brands/register` | POST | Register a new brand |
| `/brands/apps/register` | POST | Register an official app |
| `/results` | GET | List monitoring results with filters |
| `/results/scan` | POST | Scan usernames for a brand |
| `/analyze` | POST | Analyze candidate username/app |
| `/import/csv` | POST | Import candidates from CSV |

## Test Flows

### Register a Brand
```bash
curl -X POST http://localhost:3000/brands/register \
  -H "Content-Type: application/json" \
  -d '{"brand_name": "NovaPay", "official_accounts": "novapay, novapay_support", "official_urls": "https://nova.example.com"}'
```

### Scan Usernames
```bash
curl -X POST http://localhost:3000/results/scan \
  -H "Content-Type: application/json" \
  -d '{"brand_id": 1, "usernames": ["novapaay", "unrelated_name"], "asset_type": "social"}'
```

### Analyze a Candidate
```bash
curl -X POST http://localhost:3000/analyze \
  -H "Content-Type: application/json" \
  -d '{"brand_id": 1, "asset_type": "social", "username": "novapaay"}'
```

### Import CSV
```bash
curl -X POST http://localhost:3000/import/csv \
  -H "Content-Type: application/json" \
  -d '{"brand_id": 1, "asset_type": "social", "csvContent": "username,display_name,description\\nnovapaay,Novapay Support,Test description"}'
```

## Folder Structure (after migration)
```
digital-risk-protection/
├── .env              # Your secrets (NOT committed)
├── .env.example      # Template safe to commit
├── .gitignore        # Ignores node_modules, .env
├── index.js          # Main Express server
├── package.json      # Dependencies and scripts
├── package-lock.json # Lock file
├── vercel.json       # Vercel deployment config
├── supabase_schema.sql # Database schema
├── risk.js           # Risk assessment utilities
├── detection.js      # Heuristic analysis engine
├── node_modules/     # Dependencies (gitignored)
├── config/           # Original Django config (kept for reference)
│   └── settings.py
├── manage.py         # Original Django manage.py
├── monitor/          # Original Django monitor app
│   ├── models.py
│   ├── views.py
│   └── ...
├── requirements.txt  # Original Python deps
├── pyproject.toml    # Vercel build hook (Django)
├── README.md         # Original documentation
└── style.css         # CSS assets
```

## Need Help?
- If you encounter issues with the Supabase schema, check the Supabase logs
- If API routes aren't working, verify your `.env` values are correct
- If detection results seem off, test the `analyze_candidate` function directly

## Original Django Files (Kept for Reference)
The original Django files remain in the repository:
- `config/settings.py`
- `monitor/models.py`
- `monitor/views.py`
- `monitor/urls.py`
- `monitor/templates/`

These can be removed or kept depending on whether you want to fully migrate the frontend as well.