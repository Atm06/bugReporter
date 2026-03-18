# Bug Bash Reporting System

A lightweight bug reporting web app for one-day bug bash events. Built with FastAPI, deployable to Vercel with Supabase, or run locally with SQLite.

## Features

- Bug submission form with severity, category, page type, steps to reproduce, and screenshot upload
- Categories with sub-page selection (Detail / Search) for Software, Hardware, Solutions, Partners, Containers, Cloud
- Page URL field to link directly to where the issue was found
- Live dashboard with filters, search, and status management
- Admin mode (edit/delete all bugs, change status) protected by password
- Regular users can edit only the bugs they reported
- Leaderboard with point-based scoring
- Auto-refresh to keep all participants in sync
- Toast notifications for submissions, updates, and deletes

## Prerequisites

- Python 3.10+

## Installation

```bash
cd bugbash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

### Required variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_PASSWORD` | Password required for admin login | `changeme` |
| `ADMIN_EMAIL` | Email that triggers admin password prompt at sign-in | (none) |

### Supabase variables (for cloud deployment)

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL (e.g. `https://xxx.supabase.co`) |
| `SUPABASE_KEY` | Supabase anon / public API key |

### Optional variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UPLOAD_MAX_SIZE_MB` | Max screenshot upload size | `10` |
| `DB_PATH` | Directory for the SQLite database (local mode) | project root |
| `UPLOAD_PATH` | Directory for uploaded screenshots (local mode) | `uploads/` |

## Storage backends

The app automatically selects a backend based on which environment variables are set:

| Priority | Backend | When used |
|----------|---------|-----------|
| 1 | **Supabase** (PostgreSQL + Storage) | `SUPABASE_URL` and `SUPABASE_KEY` are set |
| 2 | **Google Sheets** | `GOOGLE_SHEET_ID` and credentials file exist |
| 3 | **Local SQLite** | Default fallback — no external services needed |

For local development, just leave the Supabase/Google variables unset and the app uses SQLite automatically.

## Running locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

To share with your team locally, use [ngrok](https://ngrok.com/):

```bash
brew install ngrok
ngrok http 8000
```

Share the generated `https://...ngrok-free.app` URL with participants.

## Deploying to Vercel (with Supabase)

### 1. Set up Supabase (free)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the contents of `supabase_setup.sql`
3. Copy your **Project URL** and **anon/public key** from **Settings → API**

### 2. Deploy to Vercel

```bash
# Install Vercel CLI if needed
npm i -g vercel

# Add environment variables
vercel env add SUPABASE_URL       # paste Project URL
vercel env add SUPABASE_KEY       # paste anon/public key
vercel env add ADMIN_PASSWORD     # your admin password
vercel env add ADMIN_EMAIL        # your admin email

# Deploy
vercel --prod
```

## Pages

| URL | Description |
|-----|-------------|
| `/` | Bug submission form |
| `/dashboard` | View all bugs, filter, update status |
| `/leaderboard` | See who's finding the most bugs |

## Roles

| Role | How to access | Permissions |
|------|---------------|-------------|
| Admin | Sign in with the admin email + password | Edit/delete all bugs, change status |
| Regular user | Sign in with any other email | Submit bugs, edit only their own bugs |

## Scoring

| Severity | Points |
|----------|--------|
| Critical | 4 |
| High | 3 |
| Medium | 2 |
| Low | 1 |

## Categories

**Pages** (prompted to select Detail or Search):
Software, Hardware, Solutions, Partners, Containers, Cloud

**Features** (no sub-selection):
Autosuggest, Global Search, API, Authentication, Favorites

**Other:**
Prompts for a manual page title and URL
