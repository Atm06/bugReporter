# Bug Bash Reporting System - Catalog

A lightweight bug reporting web app for one-day bug bash events. Built with FastAPI and backed by a local SQLite database.

## Features

- Bug submission form with severity, category, page type, steps to reproduce, and screenshot upload
- Categories with sub-page selection (Detail / Search) for Software, Hardware, Solutions, Partners, Containers, Cloud
- Page URL field to link directly to where the issue was found
- Live dashboard with filters, search, and status management
- Admin mode (edit/delete all bugs, change status) protected by password
- Regular users can edit only the bugs they reported
- Leaderboard with point-based scoring
- Auto-refresh to keep all participants in sync
- Data stored locally in SQLite -- no external services required

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

Edit `.env`:

```
ADMIN_PASSWORD=your-admin-password
ADMIN_EMAIL=admin@company.com
```

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_PASSWORD` | Password required for admin login | `changeme` |
| `ADMIN_EMAIL` | Email that triggers admin password prompt at sign-in | (none) |
| `UPLOAD_MAX_SIZE_MB` | Max screenshot upload size | `10` |
| `DB_PATH` | Directory for the SQLite database | project root |
| `UPLOAD_PATH` | Directory for uploaded screenshots | `uploads/` |

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

## Sharing with your team

To give your team access during the bug bash, use [ngrok](https://ngrok.com/) to create a public URL:

```bash
brew install ngrok
ngrok http 8000
```

Share the generated `https://...ngrok-free.app` URL with participants.

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
