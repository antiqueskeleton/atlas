"""
Repository for Competitive Shopping data.
Stores price snapshots and confirmed specs in atlas.db.
"""
import sqlite3
from backend.services.paths import get_db_path


class PriceComparisonRepository:

    def connect(self):
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comp_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand       TEXT    NOT NULL,
                    model       TEXT    NOT NULL,
                    search_q    TEXT    NOT NULL,
                    retailer    TEXT    NOT NULL,
                    title       TEXT    NOT NULL,
                    price       REAL,
                    url         TEXT,
                    availability TEXT,
                    captured_at TEXT    DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comp_snap_bm
                ON comp_snapshots(brand, model, captured_at DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comp_specs (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand        TEXT NOT NULL,
                    model        TEXT NOT NULL,
                    spec_name    TEXT NOT NULL,
                    spec_value   TEXT NOT NULL,
                    source_url   TEXT,
                    confirmed_at TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(brand, model, spec_name) ON CONFLICT REPLACE
                )
            """)

    # ── Snapshots ──────────────────────────────────────────────────────────────

    def save_snapshots(self, brand: str, model: str, search_q: str,
                       results: list[dict]):
        with self.connect() as conn:
            for r in results:
                conn.execute("""
                    INSERT INTO comp_snapshots
                        (brand, model, search_q, retailer, title, price,
                         url, availability)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    brand, model, search_q,
                    r.get("retailer", ""),
                    r.get("title", ""),
                    r.get("price"),
                    r.get("url", ""),
                    r.get("availability", ""),
                ))

    def get_latest_snapshots(self, brand: str, model: str) -> list[dict]:
        """Return the most-recent snapshot per retailer for this brand/model."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT retailer, title, price, url, availability, captured_at
                FROM comp_snapshots
                WHERE brand=? AND model=?
                  AND captured_at = (
                      SELECT MAX(captured_at)
                      FROM comp_snapshots s2
                      WHERE s2.brand=comp_snapshots.brand
                        AND s2.model=comp_snapshots.model
                        AND s2.retailer=comp_snapshots.retailer
                  )
                ORDER BY price ASC
            """, (brand, model)).fetchall()
            return [dict(r) for r in rows]

    def get_previous_price(self, brand: str, model: str,
                           retailer: str) -> float | None:
        """Return the price from the snapshot immediately before the latest."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT price FROM comp_snapshots
                WHERE brand=? AND model=? AND retailer=?
                ORDER BY captured_at DESC LIMIT 2
            """, (brand, model, retailer)).fetchall()
            return rows[1]["price"] if len(rows) >= 2 else None

    def get_price_history(self, brand: str, model: str,
                          retailer: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT price, captured_at FROM comp_snapshots
                WHERE brand=? AND model=? AND retailer=?
                ORDER BY captured_at DESC LIMIT 30
            """, (brand, model, retailer)).fetchall()
            return [dict(r) for r in rows]

    # ── Specs ──────────────────────────────────────────────────────────────────

    def save_specs(self, brand: str, model: str,
                   specs: dict[str, str], source_url: str = ""):
        with self.connect() as conn:
            for name, value in specs.items():
                if value:
                    conn.execute("""
                        INSERT OR REPLACE INTO comp_specs
                            (brand, model, spec_name, spec_value, source_url)
                        VALUES (?,?,?,?,?)
                    """, (brand, model, name, value, source_url))

    def get_specs(self, brand: str, model: str) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT spec_name, spec_value FROM comp_specs
                WHERE brand=? AND model=?
            """, (brand, model)).fetchall()
            return {r["spec_name"]: r["spec_value"] for r in rows}

    def clear_specs(self, brand: str, model: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM comp_specs WHERE brand=? AND model=?",
                         (brand, model))
