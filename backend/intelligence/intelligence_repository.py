import sqlite3
from pathlib import Path


class IntelligenceRepository:
    def __init__(self, db_path="database/atlas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def _initialize(self):
        with self.connect() as conn:
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
