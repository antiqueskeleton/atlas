import json
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.services.paths import get_db_path


class TargetedReviewRepository:
    """
    Persistence for Targeted Review (#25): platform-presence snapshots and
    the user's curated retailer product URLs.

    Findings are stored as one JSON snapshot per (platform, brand,
    collection time) rather than normalized metric columns — each platform's
    metric shape is different and will keep evolving as platforms are added,
    and every read path wants the whole snapshot anyway (latest per brand
    for gap analysis, full history later for trend charts). Same
    schema-flexibility tradeoff visibility_responses made with its cue-zone
    cache columns.
    """

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS targeted_review_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tr_findings_lookup
                ON targeted_review_findings (platform, brand, collected_at)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS targeted_review_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS brand_social_links (
                    brand TEXT PRIMARY KEY,
                    links_json TEXT NOT NULL,
                    discovered_at TEXT NOT NULL
                )
            """)
            # Influencer tracking — flat, NOT brand-nested (a creator can
            # cover several brands; forcing one brand per creator would be
            # awkward). Snapshots of their performance reuse
            # targeted_review_findings itself (platform="YouTube Creators"/
            # "Reddit Creators", brand column holds the creator's display
            # name) — only the curated list of who to track needs its own
            # table.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS targeted_review_creators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    added_at TEXT NOT NULL,
                    UNIQUE(platform, handle)
                )
            """)

    # ── Findings ──────────────────────────────────────────────────────────────

    def save_findings(self, platform: str, findings: list[dict],
                      collected_at: str | None = None):
        stamp = collected_at or datetime.now().isoformat()
        with self.connect() as conn:
            conn.executemany("""
                INSERT INTO targeted_review_findings
                    (platform, brand, metrics_json, collected_at)
                VALUES (?, ?, ?, ?)
            """, [
                (platform, f.get("brand", ""), json.dumps(f), stamp)
                for f in findings
            ])

    def latest_findings(self, platform: str) -> dict[str, dict]:
        """
        Most recent snapshot per brand for a platform, as {brand: metrics}
        with the snapshot's collected_at injected into each metrics dict.
        Brands collected in different runs are each represented by their own
        latest row, so a partial re-run (one brand) doesn't hide the others.
        """
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT brand, metrics_json, collected_at
                FROM targeted_review_findings
                WHERE platform = ?
                ORDER BY collected_at ASC, id ASC
            """, (platform,)).fetchall()

        latest: dict[str, dict] = {}
        for brand, metrics_json, collected_at in rows:  # ASC → last write wins
            try:
                metrics = json.loads(metrics_json)
            except json.JSONDecodeError:
                continue
            metrics["collected_at"] = collected_at
            latest[brand] = metrics
        return latest

    def brand_history(self, platform: str, brand: str) -> list[dict]:
        """All snapshots for one brand on one platform, oldest first —
        the raw material for future trend charting."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT metrics_json, collected_at
                FROM targeted_review_findings
                WHERE platform = ? AND brand = ?
                ORDER BY collected_at ASC, id ASC
            """, (platform, brand)).fetchall()
        history = []
        for metrics_json, collected_at in rows:
            try:
                metrics = json.loads(metrics_json)
            except json.JSONDecodeError:
                continue
            metrics["collected_at"] = collected_at
            history.append(metrics)
        return history

    # ── Retailer product URLs ─────────────────────────────────────────────────

    def add_product_url(self, brand: str, url: str) -> bool:
        """Returns False when the URL is already saved (UNIQUE constraint) —
        a duplicate paste is a no-op, not an error dialog."""
        try:
            with self.connect() as conn:
                conn.execute("""
                    INSERT INTO targeted_review_urls (brand, url, added_at)
                    VALUES (?, ?, ?)
                """, (brand, url.strip(), datetime.now().isoformat()))
            return True
        except sqlite3.IntegrityError:
            return False

    def list_product_urls(self) -> list[tuple]:
        """[(id, brand, url, added_at)] ordered by brand then insertion."""
        with self.connect() as conn:
            return conn.execute("""
                SELECT id, brand, url, added_at
                FROM targeted_review_urls
                ORDER BY brand COLLATE NOCASE ASC, id ASC
            """).fetchall()

    def delete_product_url(self, url_id: int):
        with self.connect() as conn:
            conn.execute("DELETE FROM targeted_review_urls WHERE id = ?", (url_id,))

    # ── Brand social links ────────────────────────────────────────────────────

    def save_social_links(self, brand: str, links: dict):
        """Discovered social profiles per brand (youtube/facebook/… → URL).
        Last discovery wins — sites change their footers."""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO brand_social_links (brand, links_json, discovered_at)
                VALUES (?, ?, ?)
                ON CONFLICT(brand) DO UPDATE SET
                    links_json = excluded.links_json,
                    discovered_at = excluded.discovered_at
            """, (brand, json.dumps(links), datetime.now().isoformat()))

    def get_social_links(self, brand: str) -> dict:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT links_json FROM brand_social_links WHERE brand = ?",
                (brand,)).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return {}

    def all_social_links(self) -> dict[str, dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT brand, links_json FROM brand_social_links").fetchall()
        result = {}
        for brand, links_json in rows:
            try:
                result[brand] = json.loads(links_json)
            except (json.JSONDecodeError, TypeError):
                continue
        return result

    # ── Tracked creators (influencers) ────────────────────────────────────────

    def add_creator(self, platform: str, handle: str, display_name: str,
                    notes: str = "") -> bool:
        """Returns False when this (platform, handle) is already tracked
        (UNIQUE constraint) — a duplicate add is a no-op, not an error."""
        try:
            with self.connect() as conn:
                conn.execute("""
                    INSERT INTO targeted_review_creators
                        (platform, handle, display_name, notes, added_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (platform, handle.strip(), display_name.strip(),
                      notes.strip(), datetime.now().isoformat()))
            return True
        except sqlite3.IntegrityError:
            return False

    def list_creators(self) -> list[tuple]:
        """[(id, platform, handle, display_name, notes, added_at)] ordered
        by display name."""
        with self.connect() as conn:
            return conn.execute("""
                SELECT id, platform, handle, display_name, notes, added_at
                FROM targeted_review_creators
                ORDER BY display_name COLLATE NOCASE ASC, id ASC
            """).fetchall()

    def remove_creator(self, creator_id: int):
        with self.connect() as conn:
            conn.execute("DELETE FROM targeted_review_creators WHERE id = ?", (creator_id,))
