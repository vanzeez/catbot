"""SQLite store: tasks, events, decisions, corrections."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, ts TEXT, utterance TEXT, lang TEXT,
  ok INTEGER, stopped_by TEXT, spoken TEXT, latency_ms INTEGER);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT,
  stage TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT,
  step INTEGER, question_id TEXT, state TEXT, choice TEXT, confidence REAL, source TEXT);
CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
  task_id TEXT, step INTEGER, question_id TEXT, correct_choice TEXT);
"""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _exec(self, sql: str, args: tuple[Any, ...]) -> None:
        with self._lock:
            self._db.execute(sql, args)
            self._db.commit()

    def add_event(self, task_id: str, stage: str, payload_json: str) -> None:
        self._exec(
            "INSERT INTO events (ts, task_id, stage, json) VALUES (?,?,?,?)",
            (now(), task_id, stage, payload_json),
        )

    def add_task(self, task_id: str, utterance: str, lang: str) -> None:
        self._exec(
            "INSERT OR REPLACE INTO tasks (task_id, ts, utterance, lang) VALUES (?,?,?,?)",
            (task_id, now(), utterance, lang),
        )

    def finish_task(
        self, task_id: str, ok: bool, stopped_by: str | None, spoken: str, latency_ms: int
    ) -> None:
        self._exec(
            "UPDATE tasks SET ok=?, stopped_by=?, spoken=?, latency_ms=? WHERE task_id=?",
            (int(ok), stopped_by, spoken, latency_ms, task_id),
        )

    def add_decision(
        self,
        task_id: str,
        step: int,
        question_id: str,
        state: str,
        choice: str,
        confidence: float,
        source: str,
    ) -> None:
        self._exec(
            "INSERT INTO decisions (ts, task_id, step, question_id, state, choice, confidence,"
            " source) VALUES (?,?,?,?,?,?,?,?)",
            (now(), task_id, step, question_id, state, choice, confidence, source),
        )

    def add_correction(self, task_id: str, step: int, question_id: str, correct: str) -> None:
        self._exec(
            "INSERT INTO corrections (ts, task_id, step, question_id, correct_choice)"
            " VALUES (?,?,?,?,?)",
            (now(), task_id, step, question_id, correct),
        )

    def count(self, table: str) -> int:
        assert table in {"tasks", "events", "decisions", "corrections"}
        with self._lock:
            return int(self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def rows(self, sql: str, args: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self._lock:
            return list(self._db.execute(sql, args).fetchall())


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
