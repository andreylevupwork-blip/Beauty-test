from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.sqlite3"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                username TEXT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                service_id TEXT NOT NULL,
                service_title TEXT NOT NULL,
                master_name TEXT NOT NULL,
                appt_start TEXT NOT NULL,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL
            );
            """
        )
        # Prevent double-booking for the same master+time.
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_master_time
            ON appointments (master_name, appt_start);
            """
        )
        await db.commit()


async def is_slot_taken(master_name: str, appt_start_iso: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT 1
            FROM appointments
            WHERE master_name = ? AND appt_start = ?
            LIMIT 1
            """,
            (master_name, appt_start_iso),
        ) as cur:
            row = await cur.fetchone()
            return row is not None


async def create_appointment(
    *,
    user_id: str,
    username: str | None,
    name: str,
    phone: str,
    service_id: str,
    service_title: str,
    master_name: str,
    appt_start_iso: str,
    note: str | None,
) -> int:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO appointments (
                user_id, username, name, phone,
                service_id, service_title,
                master_name, appt_start,
                note, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)
            """,
            (
                user_id,
                username,
                name,
                phone,
                service_id,
                service_title,
                master_name,
                appt_start_iso,
                note,
                created_at,
            ),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_user_appointments(user_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, service_title, master_name, appt_start, status, name, phone
            FROM appointments
            WHERE user_id = ? AND status = 'confirmed'
            ORDER BY appt_start ASC
            """,
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_all_appointments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, user_id, username, name, phone, service_id, service_title, master_name, appt_start, note, status, created_at
            FROM appointments
            WHERE status = 'confirmed'
            ORDER BY appt_start ASC
            """
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def cancel_appointment(appt_id: int, user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM appointments
            WHERE id = ? AND user_id = ?
            """,
            (appt_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def admin_delete_appointment(appt_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM appointments
            WHERE id = ?
            """,
            (appt_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

