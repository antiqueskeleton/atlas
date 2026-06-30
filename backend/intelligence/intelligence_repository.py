import sqlite3
from pathlib import Path

from backend.services.paths import get_db_path


class IntelligenceRepository:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def _initialize(self):
        with self.connect() as conn:
            # Migrate: add run_id to opportunities if the column doesn't exist yet
            try:
                conn.execute("ALTER TABLE opportunities ADD COLUMN run_id TEXT")
            except Exception:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_runs (
                    run_id     TEXT PRIMARY KEY,
                    provider   TEXT,
                    model      TEXT,
                    target_brand TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    status     TEXT,
                    duration_seconds REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_results (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id       TEXT,
                    analyst_name TEXT,
                    prompt       TEXT,
                    response     TEXT,
                    collected_at TEXT,
                    FOREIGN KEY(run_id) REFERENCES intelligence_runs(run_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_briefings (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id             TEXT UNIQUE,
                    product_summary    TEXT,
                    persona_summary    TEXT,
                    journey_summary    TEXT,
                    opportunities      TEXT,
                    executive_briefing TEXT,
                    created_at         TEXT,
                    FOREIGN KEY(run_id) REFERENCES intelligence_runs(run_id)
                )
            """)

    # ── Writes ────────────────────────────────────────────────────────────────

    def save_run(self, run_id, provider, model, target_brand, started_at):
        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO intelligence_runs
                (run_id, provider, model, target_brand, started_at, status)
                VALUES (?, ?, ?, ?, ?, 'running')
            """, (run_id, provider, model, target_brand, started_at))

    def complete_run(self, run_id, completed_at, duration_seconds, status="completed"):
        with self.connect() as conn:
            conn.execute("""
                UPDATE intelligence_runs
                SET completed_at=?, status=?, duration_seconds=?
                WHERE run_id=?
            """, (completed_at, status, duration_seconds, run_id))

    def save_result(self, run_id, analyst_name, prompt, response, collected_at):
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO intelligence_results
                (run_id, analyst_name, prompt, response, collected_at)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, analyst_name, prompt, response, collected_at))

    def save_briefing(
        self, run_id, product_summary, persona_summary,
        journey_summary, opportunities, executive_briefing, created_at
    ):
        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO intelligence_briefings
                (run_id, product_summary, persona_summary,
                 journey_summary, opportunities, executive_briefing, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, product_summary, persona_summary,
                journey_summary, opportunities, executive_briefing, created_at
            ))

    # ── Reads ─────────────────────────────────────────────────────────────────

    def list_runs(self):
        with self.connect() as conn:
            return conn.execute("""
                SELECT run_id, provider, model, target_brand,
                       started_at, completed_at, status, duration_seconds
                FROM intelligence_runs ORDER BY started_at DESC
            """).fetchall()

    def get_latest_run(self):
        with self.connect() as conn:
            return conn.execute("""
                SELECT run_id, provider, model, target_brand,
                       started_at, completed_at, status, duration_seconds
                FROM intelligence_runs ORDER BY started_at DESC LIMIT 1
            """).fetchone()

    def get_results_for_run(self, run_id):
        with self.connect() as conn:
            return conn.execute("""
                SELECT analyst_name, prompt, response, collected_at
                FROM intelligence_results WHERE run_id=? ORDER BY id ASC
            """, (run_id,)).fetchall()

    def get_briefing_for_run(self, run_id):
        with self.connect() as conn:
            return conn.execute("""
                SELECT product_summary, persona_summary, journey_summary,
                       opportunities, executive_briefing, created_at
                FROM intelligence_briefings WHERE run_id=?
            """, (run_id,)).fetchone()

    def save_opportunities(self, run_id: str, opp_list: list):
        from datetime import datetime
        now = datetime.now().isoformat()
        with self.connect() as conn:
            conn.executemany("""
                INSERT INTO opportunities (market_id, run_id, created_date, title, description, evidence, status)
                VALUES (1, ?, ?, ?, ?, ?, 'new')
            """, [
                (run_id, now, o["title"], o["description"], o["evidence"])
                for o in opp_list
            ])

    def get_opportunities_for_run(self, run_id: str):
        with self.connect() as conn:
            return conn.execute("""
                SELECT opportunity_id, title, evidence, description, status
                FROM opportunities WHERE run_id=? ORDER BY opportunity_id ASC
            """, (run_id,)).fetchall()

    def get_stuck_runs(self, older_than_minutes: int = 30) -> list:
        """Return intelligence runs stuck in 'running' status beyond the threshold."""
        with self.connect() as conn:
            return conn.execute("""
                SELECT run_id, provider, started_at
                FROM intelligence_runs
                WHERE status = 'running'
                  AND started_at < datetime('now', ?, 'utc')
            """, (f"-{older_than_minutes} minutes",)).fetchall()

    def mark_run_failed(self, run_id: str):
        with self.connect() as conn:
            conn.execute(
                "UPDATE intelligence_runs SET status='failed', completed_at=datetime('now') WHERE run_id=?",
                (run_id,),
            )

    def get_unparsed_briefing_runs(self) -> list:
        """Return (run_id, opportunities_text) for briefings with no parsed opportunity rows."""
        with self.connect() as conn:
            return conn.execute("""
                SELECT ib.run_id, ib.opportunities
                FROM intelligence_briefings ib
                WHERE ib.opportunities IS NOT NULL
                  AND ib.opportunities != ''
                  AND ib.run_id NOT IN (SELECT DISTINCT run_id FROM opportunities WHERE run_id IS NOT NULL)
            """).fetchall()

    def update_opportunity_status(self, opp_id: int, status: str):
        with self.connect() as conn:
            conn.execute(
                "UPDATE opportunities SET status=? WHERE opportunity_id=?",
                (status, opp_id),
            )
