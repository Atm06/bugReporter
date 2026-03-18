from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .local_store import LocalStoreClient
from .sheets import SheetClient
from .supabase_store import SupabaseStoreClient

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_PATH", str(PROJECT_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_UPLOAD_BYTES = int(os.getenv("UPLOAD_MAX_SIZE_MB", "10")) * 1024 * 1024

CATEGORIES_WITH_PAGES = ["Software", "Hardware", "Solutions", "Partners", "Containers", "Cloud"]
SIMPLE_CATEGORIES = ["Autosuggest", "Global Search", "API", "Authentication", "Favorites"]
ALL_CATEGORIES = CATEGORIES_WITH_PAGES + SIMPLE_CATEGORIES + ["Other"]
PAGE_TYPES = ["Detail", "Search"]

SEVERITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["Open", "In Progress", "Fixed", "Won't Fix", "Duplicate"]

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()[:40]

app = FastAPI(title="Bug Bash Reporter")


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

sheet: SheetClient | LocalStoreClient | SupabaseStoreClient | None = None


@app.on_event("startup")
def startup() -> None:
    global sheet
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if supabase_url and supabase_key:
        sheet = SupabaseStoreClient(supabase_url, supabase_key)
        print(f"✔ Using Supabase backend ({supabase_url})")
    else:
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        creds_path = PROJECT_DIR / creds_file

        if sheet_id and creds_path.exists():
            sheet = SheetClient(sheet_id, str(creds_path))
            print("✔ Using Google Sheets backend")
        else:
            db_dir = Path(os.getenv("DB_PATH", str(PROJECT_DIR)))
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "bugs.db"
            sheet = LocalStoreClient(db_path)
            print(f"✔ Using local SQLite backend ({db_path})")


def _sheet() -> SheetClient | LocalStoreClient:
    if sheet is None:
        raise HTTPException(status_code=503, detail="Storage client not initialised")
    return sheet


def _is_admin(request: Request) -> bool:
    return request.headers.get("X-Admin-Token", "") == ADMIN_TOKEN


def _user_email(request: Request) -> str:
    return request.headers.get("X-User-Email", "").strip().lower()


# ── Page routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def submit_page(request: Request):
    return templates.TemplateResponse(
        "submit.html",
        {
            "request": request,
            "categories_with_pages": CATEGORIES_WITH_PAGES,
            "simple_categories": SIMPLE_CATEGORIES,
            "all_categories": ALL_CATEGORIES,
            "page_types": PAGE_TYPES,
            "severities": SEVERITIES,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "categories_with_pages": CATEGORIES_WITH_PAGES,
            "simple_categories": SIMPLE_CATEGORIES,
            "all_categories": ALL_CATEGORIES,
            "page_types": PAGE_TYPES,
            "severities": SEVERITIES,
            "statuses": STATUSES,
        },
    )


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    return templates.TemplateResponse("leaderboard.html", {"request": request})


# ── Auth routes ──────────────────────────────────────────────────────────────

class EmailCheck(BaseModel):
    email: str


class AdminLogin(BaseModel):
    password: str


@app.post("/api/auth/check-email")
async def check_email(body: EmailCheck):
    return {"requires_password": body.email.strip().lower() == ADMIN_EMAIL}


@app.post("/api/auth/admin")
async def admin_login(body: AdminLogin):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(403, "Invalid admin password")
    return {"ok": True, "token": ADMIN_TOKEN}


@app.get("/api/auth/verify-admin")
async def verify_admin(request: Request):
    return {"ok": _is_admin(request)}


# ── API routes ───────────────────────────────────────────────────────────────

class BugCreate(BaseModel):
    title: str
    description: str
    severity: str = "Medium"
    category: str = "Other"
    subcategory: str = ""
    steps: str = ""
    screenshot: str = ""
    reporter_name: str = ""
    reporter_email: str = ""
    page_url: str = ""
    page_title: str = ""


class BugUpdate(BaseModel):
    title: str
    description: str
    severity: str = "Medium"
    category: str = "Other"
    subcategory: str = ""
    steps: str = ""
    screenshot: str = ""
    reporter_name: str = ""
    reporter_email: str = ""
    status: str = "Open"
    page_url: str = ""
    page_title: str = ""


class StatusUpdate(BaseModel):
    status: str


@app.post("/api/bugs")
async def create_bug(bug: BugCreate):
    if bug.severity not in SEVERITIES:
        raise HTTPException(400, f"Invalid severity: {bug.severity}")
    result = await _sheet().append_bug_async(bug.model_dump())
    return JSONResponse(result, status_code=201)


@app.get("/api/bugs")
async def list_bugs():
    bugs = await _sheet().get_all_bugs_async()
    return bugs


@app.put("/api/bugs/{bug_id}")
async def update_bug(bug_id: str, bug: BugUpdate, request: Request):
    if bug.severity not in SEVERITIES:
        raise HTTPException(400, f"Invalid severity: {bug.severity}")
    if bug.status not in STATUSES:
        raise HTTPException(400, f"Invalid status: {bug.status}")

    admin = _is_admin(request)
    email = _user_email(request)

    if not admin:
        bugs = await _sheet().get_all_bugs_async()
        target = next((b for b in bugs if b["ID"] == bug_id), None)
        if not target:
            raise HTTPException(404, f"Bug {bug_id} not found")
        if target["Reporter Email"].strip().lower() != email:
            raise HTTPException(403, "You can only edit bugs you reported")

    result = await _sheet().update_bug_async(bug_id, bug.model_dump())
    if result is None:
        raise HTTPException(404, f"Bug {bug_id} not found")
    return result


@app.patch("/api/bugs/{bug_id}/status")
async def update_bug_status(bug_id: str, body: StatusUpdate, request: Request):
    if body.status not in STATUSES:
        raise HTTPException(400, f"Invalid status: {body.status}")

    admin = _is_admin(request)
    if not admin:
        raise HTTPException(403, "Only admins can change bug status")

    ok = await _sheet().update_status_async(bug_id, body.status)
    if not ok:
        raise HTTPException(404, f"Bug {bug_id} not found")
    return {"ok": True, "bug_id": bug_id, "status": body.status}


@app.delete("/api/bugs/{bug_id}")
async def delete_bug(bug_id: str, request: Request):
    if not _is_admin(request):
        raise HTTPException(403, "Only admins can delete bugs")
    ok = await _sheet().delete_bug_async(bug_id)
    if not ok:
        raise HTTPException(404, f"Bug {bug_id} not found")
    return {"ok": True, "bug_id": bug_id}


@app.get("/api/leaderboard")
async def leaderboard_data():
    bugs = await _sheet().get_all_bugs_async()
    return _sheet().compute_leaderboard(bugs)


@app.post("/api/upload")
async def upload_screenshot(file: UploadFile = File(...)):
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "Only image files are allowed")

    ext = Path(file.filename or "img.png").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File extension {ext} not allowed")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)}MB)")

    filename = f"{uuid.uuid4().hex}{ext}"

    if isinstance(_sheet(), SupabaseStoreClient):
        url = _sheet().upload_file(
            filename, contents, file.content_type or "image/png"
        )
        return {"filename": filename, "url": url}

    dest = UPLOAD_DIR / filename
    dest.write_bytes(contents)
    return {"filename": filename, "url": f"/uploads/{filename}"}
