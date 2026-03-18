# Bug Bash Reporting System - Catalog

A lightweight bug reporting web app for one-day bug bash events. Built with FastAPI and backed by Google Sheets.

## Features

- Bug submission form with severity, category, steps to reproduce, and screenshot upload
- Live dashboard with filters, search, and status management
- Leaderboard with point-based scoring (Critical=4, High=3, Medium=2, Low=1)
- Auto-refresh to keep all participants in sync
- Google Sheets backend for easy sharing and post-event analysis

## Prerequisites

- Python 3.10+
- A Google Cloud project with Sheets API and Drive API enabled
- A service account with a downloaded JSON key

## Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **Credentials** > **Create Credentials** > **Service Account**
5. Download the JSON key and save it as `credentials.json` in the `bugbash/` directory
6. Create a new Google Sheet
7. Share the sheet with the service account email (found in `credentials.json` under `client_email`) as an **Editor**
8. Copy the sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

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
GOOGLE_SHEET_ID=<your-sheet-id>
GOOGLE_CREDENTIALS_FILE=credentials.json
CATEGORIES=Search,Browse,Product Detail,Cart,Checkout,Filters,Navigation,API,Other
```

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Participants can access the app at `http://<your-ip>:8000` on the local network.

## Pages

| URL | Description |
|-----|-------------|
| `/` | Bug submission form |
| `/dashboard` | View all bugs, filter, update status |
| `/leaderboard` | See who's finding the most bugs |

## Scoring

| Severity | Points |
|----------|--------|
| Critical | 4 |
| High | 3 |
| Medium | 2 |
| Low | 1 |
