"""Lightweight SQLite storage for automation idempotency and logs."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutomationDB:
    def __init__(self, path: str = "automation.sqlite") -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True) if Path(path).parent != Path(".") else None
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                url TEXT,
                channel_id TEXT,
                title TEXT,
                score INTEGER,
                compliance_status TEXT,
                processed_at TEXT,
                decision_json TEXT
            );
            CREATE TABLE IF NOT EXISTS generated_shorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_video_id INTEGER,
                file_path TEXT UNIQUE,
                title TEXT,
                score INTEGER,
                transformation_applied INTEGER,
                compliance_risk TEXT,
                created_at TEXT,
                metadata_json TEXT,
                FOREIGN KEY(source_video_id) REFERENCES source_videos(id)
            );
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_short_id INTEGER,
                youtube_video_id TEXT,
                file_path TEXT UNIQUE,
                privacy_status TEXT,
                status TEXT,
                uploaded_at TEXT,
                error TEXT,
                FOREIGN KEY(generated_short_id) REFERENCES generated_shorts(id)
            );
            CREATE TABLE IF NOT EXISTS run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                level TEXT,
                message TEXT,
                created_at TEXT
            );
            """
        )
        self.conn.commit()

    def source_processed(self, video_id: str) -> bool:
        row = self.conn.execute("SELECT id FROM source_videos WHERE video_id = ?", (video_id,)).fetchone()
        return row is not None

    def record_source(self, video: Dict, score: int, compliance_status: str, decision: Dict) -> int:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO source_videos
            (video_id, url, channel_id, title, score, compliance_status, processed_at, decision_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video.get("video_id"),
                video.get("url"),
                video.get("channel_id"),
                video.get("title"),
                score,
                compliance_status,
                utc_now(),
                json.dumps(decision),
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM source_videos WHERE video_id = ?", (video.get("video_id"),)).fetchone()
        return int(row["id"])

    def record_short(
        self,
        source_video_id: int,
        file_path: str,
        title: str,
        score: int,
        transformation_applied: bool,
        compliance_risk: str,
        metadata: Dict,
    ) -> int:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO generated_shorts
            (source_video_id, file_path, title, score, transformation_applied, compliance_risk, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_video_id,
                file_path,
                title,
                score,
                1 if transformation_applied else 0,
                compliance_risk,
                utc_now(),
                json.dumps(metadata),
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM generated_shorts WHERE file_path = ?", (file_path,)).fetchone()
        return int(row["id"])

    def upload_exists(self, file_path: str) -> bool:
        row = self.conn.execute("SELECT id FROM uploads WHERE file_path = ? AND status = 'uploaded'", (file_path,)).fetchone()
        return row is not None

    def record_upload(self, generated_short_id: int, file_path: str, result: Dict, status: str = "uploaded", error: str = "") -> int:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO uploads
            (generated_short_id, youtube_video_id, file_path, privacy_status, status, uploaded_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generated_short_id,
                result.get("youtube_video_id"),
                file_path,
                result.get("privacy_status"),
                status,
                result.get("uploaded_at") or utc_now(),
                error,
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM uploads WHERE file_path = ?", (file_path,)).fetchone()
        return int(row["id"])

    def log(self, run_id: str, level: str, message: str) -> None:
        self.conn.execute(
            "INSERT INTO run_logs (run_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (run_id, level, message, utc_now()),
        )
        self.conn.commit()

    def recent_logs(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT run_id, level, message, created_at FROM run_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def recent_uploads(self, limit: int = 10) -> List[Dict]:
        rows = self.conn.execute(
            """
            SELECT youtube_video_id, file_path, privacy_status, status, uploaded_at, error
            FROM uploads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.conn.close()
