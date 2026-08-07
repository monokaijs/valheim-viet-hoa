from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .schema import CatalogEntry, SegmentState, Tier


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS segments (
  segment_id TEXT PRIMARY KEY,
  key TEXT NOT NULL,
  english TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  family TEXT NOT NULL,
  domain TEXT NOT NULL,
  tier TEXT NOT NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  translation TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  model TEXT,
  reasoning_effort TEXT,
  notes TEXT NOT NULL DEFAULT '',
  validation_errors_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_segments_key ON segments(key);
CREATE INDEX IF NOT EXISTS idx_segments_family ON segments(family);
CREATE INDEX IF NOT EXISTS idx_segments_status_tier ON segments(status, tier);
CREATE TABLE IF NOT EXISTS source_history (
  source_hash TEXT PRIMARY KEY,
  key TEXT NOT NULL,
  english TEXT NOT NULL,
  translation TEXT,
  context_json TEXT NOT NULL,
  archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS glossary (
  source TEXT PRIMARY KEY COLLATE NOCASE,
  target TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  locked INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class TranslationMemory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "TranslationMemory":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def sync_catalog(self, entries: Iterable[CatalogEntry]) -> None:
        current_keys: set[str] = set()
        for entry in entries:
            current_keys.add(entry.key)
            old = self.db.execute(
                "SELECT * FROM segments WHERE key=? ORDER BY updated_at DESC LIMIT 1", (entry.key,)
            ).fetchone()
            if old and old["source_hash"] != entry.source_hash:
                self.db.execute(
                    "INSERT OR IGNORE INTO source_history(source_hash,key,english,translation,context_json) "
                    "VALUES(?,?,?,?,?)",
                    (old["source_hash"], old["key"], old["english"], old["translation"], old["context_json"]),
                )
                self.db.execute("DELETE FROM segments WHERE segment_id=?", (old["segment_id"],))
            self.db.execute(
                """INSERT INTO segments(segment_id,key,english,source_hash,family,domain,tier)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(segment_id) DO UPDATE SET
                     family=excluded.family, domain=excluded.domain,
                     tier=CASE WHEN segments.status IN ('pending','classified')
                               THEN excluded.tier ELSE segments.tier END,
                     updated_at=CURRENT_TIMESTAMP""",
                (entry.segment_id, entry.key, entry.english, entry.source_hash,
                 entry.family, entry.domain, entry.baseline_tier.value),
            )
        self.db.commit()

    def get(self, segment_id: str) -> SegmentState | None:
        row = self.db.execute("SELECT * FROM segments WHERE segment_id=?", (segment_id,)).fetchone()
        return self._state(row) if row else None

    def get_by_key(self, key: str) -> SegmentState | None:
        row = self.db.execute(
            "SELECT * FROM segments WHERE key=? ORDER BY updated_at DESC LIMIT 1", (key,)
        ).fetchone()
        return self._state(row) if row else None

    def select(self, statuses: tuple[str, ...], tiers: tuple[Tier, ...] | None = None,
               limit: int | None = None) -> list[SegmentState]:
        marks = ",".join("?" for _ in statuses)
        sql = f"SELECT * FROM segments WHERE status IN ({marks})"
        args: list[str | int] = list(statuses)
        if tiers:
            tier_marks = ",".join("?" for _ in tiers)
            sql += f" AND tier IN ({tier_marks})"
            args.extend(t.value for t in tiers)
        sql += " ORDER BY tier, family, key"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        return [self._state(r) for r in self.db.execute(sql, args)]

    def related(self, family: str, exclude: str, limit: int = 8) -> list[dict[str, str]]:
        rows = self.db.execute(
            "SELECT key,english,translation FROM segments WHERE family=? AND segment_id<>? "
            "ORDER BY CASE WHEN translation IS NULL THEN 1 ELSE 0 END, key LIMIT ?",
            (family, exclude, limit),
        )
        return [dict(r) for r in rows]

    def update_classification(self, segment_id: str, tier: Tier, domain: str,
                              context: dict[str, object]) -> None:
        self.db.execute(
            "UPDATE segments SET tier=?,domain=?,context_json=?,status='classified',updated_at=CURRENT_TIMESTAMP "
            "WHERE segment_id=? AND status IN ('pending','classified')",
            (tier.value, domain, json.dumps(context, ensure_ascii=False), segment_id),
        )
        self.db.commit()

    def save_translation(self, segment_id: str, translation: str, status: str, model: str,
                         effort: str, notes: str, errors: list[str]) -> None:
        self.db.execute(
            "UPDATE segments SET translation=?,status=?,model=?,reasoning_effort=?,notes=?,"
            "validation_errors_json=?,updated_at=CURRENT_TIMESTAMP WHERE segment_id=?",
            (translation, status, model, effort, notes,
             json.dumps(errors, ensure_ascii=False), segment_id),
        )
        self.db.commit()

    def translations(self, approved_only: bool = True) -> dict[str, str]:
        statuses = ("approved",) if approved_only else ("approved", "translated", "needs_review")
        marks = ",".join("?" for _ in statuses)
        rows = self.db.execute(
            f"SELECT key,translation FROM segments WHERE status IN ({marks}) AND translation IS NOT NULL",
            statuses,
        )
        return {r["key"]: r["translation"] for r in rows}

    def glossary(self) -> list[dict[str, object]]:
        return [dict(r) for r in self.db.execute("SELECT source,target,notes,locked FROM glossary ORDER BY source")]

    def import_glossary(self, rows: Iterable[tuple[str, str, str, bool]]) -> None:
        self.db.executemany(
            "INSERT INTO glossary(source,target,notes,locked) VALUES(?,?,?,?) "
            "ON CONFLICT(source) DO UPDATE SET target=excluded.target,notes=excluded.notes,locked=excluded.locked",
            ((s, t, n, int(l)) for s, t, n, l in rows),
        )
        self.db.commit()

    def stats(self) -> dict[str, int]:
        return {r["status"]: r["n"] for r in self.db.execute(
            "SELECT status,COUNT(*) n FROM segments GROUP BY status ORDER BY status"
        )}

    @staticmethod
    def _state(row: sqlite3.Row) -> SegmentState:
        return SegmentState(
            segment_id=row["segment_id"], key=row["key"], english=row["english"],
            source_hash=row["source_hash"], family=row["family"], domain=row["domain"],
            tier=Tier(row["tier"]), context=json.loads(row["context_json"]),
            translation=row["translation"], status=row["status"], model=row["model"],
            reasoning_effort=row["reasoning_effort"], notes=row["notes"],
            validation_errors=json.loads(row["validation_errors_json"]),
        )
