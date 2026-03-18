from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "ID",
    "Title",
    "Description",
    "Severity",
    "Category",
    "Subcategory",
    "Steps to Reproduce",
    "Screenshot Path",
    "Reporter Name",
    "Reporter Email",
    "Status",
    "Created At",
    "Page URL",
    "Page Title",
]

SEVERITY_POINTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


class SheetClient:
    """Thin wrapper around gspread with in-memory read cache."""

    def __init__(self, sheet_id: str, credentials_file: str) -> None:
        creds = Credentials.from_service_account_file(
            credentials_file, scopes=SCOPES
        )
        self._gc = gspread.authorize(creds)
        self._spreadsheet = self._gc.open_by_key(sheet_id)
        self._ws = self._spreadsheet.sheet1

        self._cache: list[dict[str, str]] | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 12
        self._write_lock = asyncio.Lock()

        self._ensure_headers()

    def _ensure_headers(self) -> None:
        existing = self._ws.row_values(1)
        if existing != HEADERS:
            self._ws.update("A1", [HEADERS])

    def _next_id(self) -> int:
        return len(self._ws.get_all_values())

    def _row_to_dict(self, row: list[str]) -> dict[str, str]:
        return {HEADERS[i]: row[i] if i < len(row) else "" for i in range(len(HEADERS))}

    # -- reads (cached) -------------------------------------------------------

    def get_all_bugs(self, *, force: bool = False) -> list[dict[str, str]]:
        now = time.monotonic()
        if not force and self._cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        rows = self._ws.get_all_values()
        if len(rows) <= 1:
            self._cache = []
        else:
            self._cache = [self._row_to_dict(r) for r in rows[1:]]
        self._cache_time = now
        return self._cache

    async def get_all_bugs_async(self, *, force: bool = False) -> list[dict[str, str]]:
        return await asyncio.to_thread(self.get_all_bugs, force=force)

    # -- writes ----------------------------------------------------------------

    def append_bug(self, data: dict[str, Any]) -> dict[str, str]:
        bug_id = self._next_id()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        row = [
            str(bug_id),
            data.get("title", ""),
            data.get("description", ""),
            data.get("severity", "Medium"),
            data.get("category", "Other"),
            data.get("subcategory", ""),
            data.get("steps", ""),
            data.get("screenshot", ""),
            data.get("reporter_name", ""),
            data.get("reporter_email", ""),
            "Open",
            now,
            data.get("page_url", ""),
            data.get("page_title", ""),
        ]
        self._ws.append_row(row, value_input_option="USER_ENTERED")
        self._cache = None
        return self._row_to_dict(row)

    async def append_bug_async(self, data: dict[str, Any]) -> dict[str, str]:
        async with self._write_lock:
            return await asyncio.to_thread(self.append_bug, data)

    def update_status(self, bug_id: str, new_status: str) -> bool:
        cell = self._ws.find(bug_id, in_column=1)
        if cell is None:
            return False
        status_col = HEADERS.index("Status") + 1
        self._ws.update_cell(cell.row, status_col, new_status)
        self._cache = None
        return True

    async def update_status_async(self, bug_id: str, new_status: str) -> bool:
        async with self._write_lock:
            return await asyncio.to_thread(self.update_status, bug_id, new_status)

    def update_bug(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        cell = self._ws.find(bug_id, in_column=1)
        if cell is None:
            return None
        row_num = cell.row
        updated_row = [
            bug_id,
            data.get("title", ""),
            data.get("description", ""),
            data.get("severity", "Medium"),
            data.get("category", "Other"),
            data.get("subcategory", ""),
            data.get("steps", ""),
            data.get("screenshot", ""),
            data.get("reporter_name", ""),
            data.get("reporter_email", ""),
            data.get("status", "Open"),
            "",  # preserve original created_at
            data.get("page_url", ""),
            data.get("page_title", ""),
        ]
        existing = self._ws.row_values(row_num)
        created_at_idx = HEADERS.index("Created At")
        if created_at_idx < len(existing):
            updated_row[created_at_idx] = existing[created_at_idx]
        self._ws.update(f"A{row_num}", [updated_row])
        self._cache = None
        return self._row_to_dict(updated_row)

    async def update_bug_async(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        async with self._write_lock:
            return await asyncio.to_thread(self.update_bug, bug_id, data)

    def delete_bug(self, bug_id: str) -> bool:
        cell = self._ws.find(bug_id, in_column=1)
        if cell is None:
            return False
        self._ws.delete_rows(cell.row)
        self._cache = None
        return True

    async def delete_bug_async(self, bug_id: str) -> bool:
        async with self._write_lock:
            return await asyncio.to_thread(self.delete_bug, bug_id)

    # -- leaderboard -----------------------------------------------------------

    def compute_leaderboard(self, bugs: list[dict[str, str]]) -> list[dict[str, Any]]:
        scores: dict[str, dict[str, Any]] = {}
        for bug in bugs:
            name = bug.get("Reporter Name", "").strip()
            email = bug.get("Reporter Email", "").strip()
            if not name:
                continue
            key = f"{name}|{email}"
            if key not in scores:
                scores[key] = {
                    "name": name,
                    "email": email,
                    "total_bugs": 0,
                    "points": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                }
            entry = scores[key]
            severity = bug.get("Severity", "Low")
            entry["total_bugs"] += 1
            entry["points"] += SEVERITY_POINTS.get(severity, 1)
            entry[severity.lower()] = entry.get(severity.lower(), 0) + 1

        ranked = sorted(scores.values(), key=lambda e: (-e["points"], -e["total_bugs"]))
        for i, entry in enumerate(ranked, 1):
            entry["rank"] = i
        return ranked
