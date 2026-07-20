import sqlite3
from datetime import datetime
from pathlib import Path

from backend.services.paths import get_db_path


class UsageRepository:
    """
    Per-call API usage log (R9) so Atlas can show its OWN month-to-date usage
    and an estimated cost in one place — the user was checking each provider's
    dashboard separately.

    One row per successful API call: provider, model, token counts (0 when the
    API doesn't return them), and an estimated USD cost (NULL when the model
    has no known rate — an honest blank, never a fabricated number). This
    tracks ONLY calls made through Atlas, and the cost is an estimate from
    published rates; it is not the user's real billed spend (no provider
    exposes that via API).
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
                CREATE TABLE IF NOT EXISTS api_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model TEXT,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    est_cost_usd REAL,
                    ts TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_usage_ts
                ON api_usage_events (ts)
            """)

    def record(self, provider, model, input_tokens, output_tokens,
               est_cost_usd, ts=None):
        stamp = ts or datetime.now().isoformat()
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO api_usage_events
                    (provider, model, input_tokens, output_tokens, est_cost_usd, ts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (provider, model or "", int(input_tokens or 0),
                  int(output_tokens or 0), est_cost_usd, stamp))

    def month_to_date(self, now=None) -> list[dict]:
        """
        Per-provider rollup for the current calendar month, each:
            {provider, calls, input_tokens, output_tokens,
             est_cost (None if NO call had a known rate),
             cost_partial (True if some calls had no rate but others did)}
        sorted by estimated cost desc, then call count desc.
        """
        now = now or datetime.now()
        start = now.replace(day=1, hour=0, minute=0, second=0,
                            microsecond=0).isoformat()
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT provider,
                       COUNT(*),
                       COALESCE(SUM(input_tokens), 0),
                       COALESCE(SUM(output_tokens), 0),
                       SUM(est_cost_usd),
                       SUM(CASE WHEN est_cost_usd IS NULL THEN 1 ELSE 0 END)
                FROM api_usage_events
                WHERE ts >= ?
                GROUP BY provider
            """, (start,)).fetchall()

        result = []
        for provider, calls, in_tok, out_tok, cost_sum, missing in rows:
            result.append({
                "provider": provider,
                "calls": calls,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "est_cost": cost_sum,                    # None only if all NULL
                "cost_partial": bool(missing) and cost_sum is not None,
            })
        result.sort(key=lambda r: (-(r["est_cost"] or 0.0), -r["calls"]))
        return result
