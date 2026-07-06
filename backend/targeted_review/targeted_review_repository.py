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
