from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

SEVERITY_POINTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

COLUMN_MAP = {
    "id": "ID",
    "title": "Title",
    "description": "Description",
    "severity": "Severity",
    "category": "Category",
    "subcategory": "Subcategory",
    "steps": "Steps to Reproduce",
    "screenshot": "Screenshot Path",
    "reporter_name": "Reporter Name",
    "reporter_email": "Reporter Email",
    "status": "Status",
    "created_at": "Created At",
    "page_url": "Page URL",
    "page_title": "Page Title",
}

DB_FIELDS = list(COLUMN_MAP.keys())


class SupabaseStoreClient:
    """Drop-in replacement for LocalStoreClient backed by Supabase (PostgREST + Storage)."""

    def __init__(self, url: str, key: str) -> None:
        self.base_url = url.rstrip("/")
        self.rest_url = f"{self.base_url}/rest/v1"
        self.storage_url = f"{self.base_url}/storage/v1"
        self.key = key
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._client = httpx.Client(headers=self._headers, timeout=30)
        self._lock = asyncio.Lock()

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: dict) -> dict[str, str]:
        return {COLUMN_MAP[k]: str(v) for k, v in row.items() if k in COLUMN_MAP}

    def _next_id(self) -> int:
        resp = self._client.get(
            f"{self.rest_url}/bugs",
            params={"select": "id", "order": "id.desc", "limit": "1"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0]["id"] + 1 if data else 1

    def _renumber(self) -> None:
        resp = self._client.get(
            f"{self.rest_url}/bugs",
            params={"select": "id", "order": "id"},
        )
        resp.raise_for_status()
        rows = resp.json()
        for new_id, row in enumerate(rows, 1):
            if new_id != row["id"]:
                self._client.patch(
                    f"{self.rest_url}/bugs",
                    params={"id": f"eq.{row['id']}"},
                    json={"id": new_id},
                )

    # ── read ─────────────────────────────────────────────────────────────

    def get_all_bugs(self, *, force: bool = False) -> list[dict[str, str]]:
        resp = self._client.get(
            f"{self.rest_url}/bugs",
            params={"select": ",".join(DB_FIELDS), "order": "id"},
        )
        if resp.status_code == 401:
            raise RuntimeError(
                f"Supabase auth failed (401). Check SUPABASE_KEY is the anon/public key. "
                f"Response: {resp.text}"
            )
        resp.raise_for_status()
        return [self._row_to_dict(r) for r in resp.json()]

    async def get_all_bugs_async(self, *, force: bool = False) -> list[dict[str, str]]:
        return await asyncio.to_thread(self.get_all_bugs, force=force)

    # ── create ───────────────────────────────────────────────────────────

    def append_bug(self, data: dict[str, Any]) -> dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        next_id = self._next_id()
        row = {
            "id": next_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "severity": data.get("severity", "Medium"),
            "category": data.get("category", "Other"),
            "subcategory": data.get("subcategory", ""),
            "steps": data.get("steps", ""),
            "screenshot": data.get("screenshot", ""),
            "reporter_name": data.get("reporter_name", ""),
            "reporter_email": data.get("reporter_email", ""),
            "status": "Open",
            "created_at": now,
            "page_url": data.get("page_url", ""),
            "page_title": data.get("page_title", ""),
        }
        resp = self._client.post(f"{self.rest_url}/bugs", json=row)
        resp.raise_for_status()
        return self._row_to_dict(resp.json()[0])

    async def append_bug_async(self, data: dict[str, Any]) -> dict[str, str]:
        async with self._lock:
            return await asyncio.to_thread(self.append_bug, data)

    # ── update status ────────────────────────────────────────────────────

    def update_status(self, bug_id: str, new_status: str) -> bool:
        resp = self._client.patch(
            f"{self.rest_url}/bugs",
            params={"id": f"eq.{bug_id}"},
            json={"status": new_status},
        )
        resp.raise_for_status()
        return len(resp.json()) > 0

    async def update_status_async(self, bug_id: str, new_status: str) -> bool:
        async with self._lock:
            return await asyncio.to_thread(self.update_status, bug_id, new_status)

    # ── update full bug ──────────────────────────────────────────────────

    def update_bug(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        payload = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "severity": data.get("severity", "Medium"),
            "category": data.get("category", "Other"),
            "subcategory": data.get("subcategory", ""),
            "steps": data.get("steps", ""),
            "screenshot": data.get("screenshot", ""),
            "reporter_name": data.get("reporter_name", ""),
            "reporter_email": data.get("reporter_email", ""),
            "status": data.get("status", "Open"),
            "page_url": data.get("page_url", ""),
            "page_title": data.get("page_title", ""),
        }
        resp = self._client.patch(
            f"{self.rest_url}/bugs",
            params={"id": f"eq.{bug_id}"},
            json=payload,
        )
        resp.raise_for_status()
        rows = resp.json()
        return self._row_to_dict(rows[0]) if rows else None

    async def update_bug_async(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        async with self._lock:
            return await asyncio.to_thread(self.update_bug, bug_id, data)

    # ── delete ───────────────────────────────────────────────────────────

    def delete_bug(self, bug_id: str) -> bool:
        resp = self._client.delete(
            f"{self.rest_url}/bugs",
            params={"id": f"eq.{bug_id}"},
        )
        resp.raise_for_status()
        deleted = len(resp.json()) > 0
        if deleted:
            self._renumber()
        return deleted

    async def delete_bug_async(self, bug_id: str) -> bool:
        async with self._lock:
            return await asyncio.to_thread(self.delete_bug, bug_id)

    # ── file storage ─────────────────────────────────────────────────────

    def upload_file(self, filename: str, content: bytes, content_type: str) -> str:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        resp = self._client.post(
            f"{self.storage_url}/object/screenshots/{filename}",
            content=content,
            headers=headers,
        )
        resp.raise_for_status()
        return f"{self.base_url}/storage/v1/object/public/screenshots/{filename}"

    # ── leaderboard ──────────────────────────────────────────────────────

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
