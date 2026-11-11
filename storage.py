
import csv
import os
import sqlite3
from pathlib import Path
from datetime import datetime


DATA_DIR = (
    Path(os.environ["LOCALAPPDATA"])
    / "DouyinAssistant"
)

DB_PATH = DATA_DIR / "assistant.db"


class StorageManager:

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            str(DB_PATH),
            timeout=10
        )
        self.conn.row_factory = sqlite3.Row

        self.init_database()

    def init_database(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS room_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_at TEXT NOT NULL,
                    room_url TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    anchor TEXT,
                    title TEXT,
                    live_status TEXT,
                    login_status TEXT
                )
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_records_time
                ON room_records(id DESC)
            """)

    def add_favorite(self, name, url):
        name = name.strip()
        url = url.strip()

        if not name or not url:
            raise ValueError("名称和地址不能为空")

        with self.conn:
            self.conn.execute("""
                INSERT INTO favorites (
                    name, url, created_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    name=excluded.name
            """, (
                name,
                url,
                datetime.now().isoformat(
                    timespec="seconds"
                )
            ))

    def get_favorites(self):
        rows = self.conn.execute("""
            SELECT id, name, url
            FROM favorites
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]

    def remove_favorite(self, favorite_id):
        with self.conn:
            self.conn.execute("""
                DELETE FROM favorites WHERE id=?
            """, (favorite_id,))

    def save_record(self, room_url, info):
        with self.conn:
            self.conn.execute("""
                INSERT INTO room_records (
                    collected_at,
                    room_url,
                    page_url,
                    anchor,
                    title,
                    live_status,
                    login_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(
                    timespec="seconds"
                ),
                room_url,
                info.get("url", ""),
                info.get("anchor", ""),
                info.get("title", ""),
                info.get("live_status", ""),
                info.get("login_status", "")
            ))

    def get_records(self, limit=100):
        rows = self.conn.execute("""
            SELECT
                collected_at,
                anchor,
                title,
                live_status,
                login_status,
                room_url
            FROM room_records
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    def count_records(self):
        row = self.conn.execute("""
            SELECT COUNT(*) AS total
            FROM room_records
        """).fetchone()

        return row["total"]

    def export_csv(self, file_path):
        columns = [
            "collected_at",
            "room_url",
            "page_url",
            "anchor",
            "title",
            "live_status",
            "login_status"
        ]

        cursor = self.conn.execute("""
            SELECT
                collected_at,
                room_url,
                page_url,
                anchor,
                title,
                live_status,
                login_status
            FROM room_records
            ORDER BY id DESC
        """)

        count = 0

        # utf-8-sig 便于 Windows Excel 打开中文
        with open(
            file_path,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as file:
            writer = csv.writer(file)
            writer.writerow(columns)

            for row in cursor:
                writer.writerow([
                    row[col] for col in columns
                ])
                count += 1

        return count

    def close(self):
        self.conn.close()