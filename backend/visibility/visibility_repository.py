import sqlite3
from pathlib import Path


class VisibilityRepository:
    def __init__(self, db_path="database/atlas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visibility_runs (
                    run_id TEXT PRIMARY KEY,
                    provider TEXT,
                    model TEXT,
                    prompt_set TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT,
                    response_count INTEGER,
                    duration_seconds REAL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS visibility_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    provider TEXT,
                    model TEXT,
                    prompt TEXT,
                    response TEXT,
                    collected_at TEXT,
                    FOREIGN KEY(run_id) REFERENCES visibility_runs(run_id)
                )
            """)

    def save_run(self, run):
        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO visibility_runs (
                    run_id,
                    provider,
                    model,
                    prompt_set,
                    started_at,
                    completed_at,
                    status,
                    response_count,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.provider,
                run.model,
                run.prompt_set,
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                run.status,
                run.response_count,
                run.duration_seconds,
            ))

    def save_responses(self, responses):
        with self.connect() as conn:
            conn.executemany("""
                INSERT INTO visibility_responses (
                    run_id,
                    provider,
                    model,
                    prompt,
                    response,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (
                    response.run_id,
                    response.provider,
                    response.model,
                    response.prompt,
                    response.response,
                    response.collected_at.isoformat(),
                )
                for response in responses
            ])

    def list_runs(self):
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT
                    run_id,
                    provider,
                    model,
                    prompt_set,
                    started_at,
                    completed_at,
                    status,
                    response_count,
                    duration_seconds
                FROM visibility_runs
                ORDER BY started_at DESC
            """)

            return cursor.fetchall()
        
    def list_responses(self, limit=100):
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT
                    id,
                    run_id,
                    provider,
                    model,
                    prompt,
                    response,
                    collected_at
                FROM visibility_responses
                ORDER BY collected_at DESC
                LIMIT ?
            """, (limit,))

            return cursor.fetchall()
        
    def get_responses_for_run(self, run_id):
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT
                    id,
                    run_id,
                    provider,
                    model,
                    prompt,
                    response,
                    collected_at
                FROM visibility_responses
                WHERE run_id = ?
                ORDER BY collected_at ASC
            """, (run_id,))

            return cursor.fetchall()