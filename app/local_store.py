from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY_POINTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

COLUMNS = [
    "id", "title", "description", "severity", "category", "subcategory",
    "steps", "screenshot", "reporter_name", "reporter_email",
    "status", "created_at", "page_url", "page_title",
]

HEADER_MAP = {
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


class LocalStoreClient:
    """Drop-in replacement for SheetClient backed by a local SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._write_lock = asyncio.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bugs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL,
                severity        TEXT NOT NULL DEFAULT 'Medium',
                category        TEXT NOT NULL DEFAULT 'Other',
                subcategory     TEXT NOT NULL DEFAULT '',
                steps           TEXT NOT NULL DEFAULT '',
                screenshot      TEXT NOT NULL DEFAULT '',
                reporter_name   TEXT NOT NULL DEFAULT '',
                reporter_email  TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'Open',
                created_at      TEXT NOT NULL,
                page_url        TEXT NOT NULL DEFAULT '',
                page_title      TEXT NOT NULL DEFAULT ''
            )
        """)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns that may not exist in older databases."""
        existing = {
            row[1] for row in self._conn.execute("PRAGMA table_info(bugs)").fetchall()
        }
        migrations = [
            ("subcategory", "TEXT NOT NULL DEFAULT ''"),
            ("page_url", "TEXT NOT NULL DEFAULT ''"),
            ("page_title", "TEXT NOT NULL DEFAULT ''"),
        ]
        for col, typedef in migrations:
            if col not in existing:
                self._conn.execute(f"ALTER TABLE bugs ADD COLUMN {col} {typedef}")

    def _row_to_dict(self, row: sqlite3.Row | tuple) -> dict[str, str]:
        return {HEADER_MAP[col]: str(row[i]) for i, col in enumerate(COLUMNS)}

    def get_all_bugs(self, *, force: bool = False) -> list[dict[str, str]]:
        cur = self._conn.execute(f"SELECT {', '.join(COLUMNS)} FROM bugs ORDER BY id")
        return [self._row_to_dict(r) for r in cur.fetchall()]

    async def get_all_bugs_async(self, *, force: bool = False) -> list[dict[str, str]]:
        return await asyncio.to_thread(self.get_all_bugs, force=force)

    def _next_id(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(id), 0) FROM bugs").fetchone()
        return row[0] + 1

    def _renumber(self) -> None:
        """Re-sequence IDs to 1, 2, 3 ... so there are no gaps."""
        rows = self._conn.execute("SELECT id FROM bugs ORDER BY id").fetchall()
        for new_id, (old_id,) in enumerate(rows, 1):
            if new_id != old_id:
                self._conn.execute(
                    "UPDATE bugs SET id = ? WHERE id = ?", (new_id, old_id)
                )
        seq_val = len(rows)
        self._conn.execute("DELETE FROM sqlite_sequence WHERE name = 'bugs'")
        if seq_val:
            self._conn.execute(
                "INSERT INTO sqlite_sequence (name, seq) VALUES ('bugs', ?)",
                (seq_val,),
            )
        self._conn.commit()

    def append_bug(self, data: dict[str, Any]) -> dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        next_id = self._next_id()
        self._conn.execute(
            """INSERT INTO bugs
               (id, title, description, severity, category, subcategory, steps,
                screenshot, reporter_name, reporter_email, status, created_at,
                page_url, page_title)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)""",
            (
                next_id,
                data.get("title", ""),
                data.get("description", ""),
                data.get("severity", "Medium"),
                data.get("category", "Other"),
                data.get("subcategory", ""),
                data.get("steps", ""),
                data.get("screenshot", ""),
                data.get("reporter_name", ""),
                data.get("reporter_email", ""),
                now,
                data.get("page_url", ""),
                data.get("page_title", ""),
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM bugs WHERE id = ?", (next_id,)
        ).fetchone()
        return self._row_to_dict(row)

    async def append_bug_async(self, data: dict[str, Any]) -> dict[str, str]:
        async with self._write_lock:
            return await asyncio.to_thread(self.append_bug, data)

    def update_status(self, bug_id: str, new_status: str) -> bool:
        cur = self._conn.execute(
            "UPDATE bugs SET status = ? WHERE id = ?", (new_status, bug_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    async def update_status_async(self, bug_id: str, new_status: str) -> bool:
        async with self._write_lock:
            return await asyncio.to_thread(self.update_status, bug_id, new_status)

    def update_bug(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        row = self._conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM bugs WHERE id = ?", (bug_id,)
        ).fetchone()
        if row is None:
            return None
        self._conn.execute(
            """UPDATE bugs SET title=?, description=?, severity=?, category=?,
               subcategory=?, steps=?, screenshot=?, reporter_name=?,
               reporter_email=?, status=?, page_url=?, page_title=?
               WHERE id=?""",
            (
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
                data.get("page_url", ""),
                data.get("page_title", ""),
                bug_id,
            ),
        )
        self._conn.commit()
        updated = self._conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM bugs WHERE id = ?", (bug_id,)
        ).fetchone()
        return self._row_to_dict(updated)

    async def update_bug_async(self, bug_id: str, data: dict[str, Any]) -> dict[str, str] | None:
        async with self._write_lock:
            return await asyncio.to_thread(self.update_bug, bug_id, data)

    def delete_bug(self, bug_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM bugs WHERE id = ?", (bug_id,))
        self._conn.commit()
        if cur.rowcount > 0:
            self._renumber()
            return True
        return False

    async def delete_bug_async(self, bug_id: str) -> bool:
        async with self._write_lock:
            return await asyncio.to_thread(self.delete_bug, bug_id)

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
