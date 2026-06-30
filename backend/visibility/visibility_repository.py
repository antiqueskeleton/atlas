import sqlite3
from pathlib import Path

from backend.services.paths import get_db_path


class VisibilityRepository:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else get_db_path()
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
                    duration_seconds REAL,
                    error_count INTEGER DEFAULT 0
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
                    family_name TEXT DEFAULT '',
                    FOREIGN KEY(run_id) REFERENCES visibility_runs(run_id)
                )
            """)

            # Migrations for databases created before these columns existed
            for ddl in (
                "ALTER TABLE visibility_runs ADD COLUMN error_count INTEGER DEFAULT 0",
                "ALTER TABLE visibility_responses ADD COLUMN family_name TEXT DEFAULT ''",
            ):
                try:
                    conn.execute(ddl)
                except Exception:
                    pass  # column already exists

            # Indexes — additive, safe, reversible with DROP INDEX
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vresp_run_id      ON visibility_responses(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vresp_provider     ON visibility_responses(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vresp_collected_at ON visibility_responses(collected_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vresp_family       ON visibility_responses(family_name)")

    def save_run(self, run):
        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO visibility_runs (
                    run_id, provider, model, prompt_set,
                    started_at, completed_at, status,
                    response_count, duration_seconds, error_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                getattr(run, "error_count", 0),
            ))

    def save_responses(self, responses):
        with self.connect() as conn:
            conn.executemany("""
                INSERT INTO visibility_responses (
                    run_id, provider, model, prompt, response, collected_at, family_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    r.run_id,
                    r.provider,
                    r.model,
                    r.prompt,
                    r.response,
                    r.collected_at.isoformat(),
                    getattr(r, "family_name", ""),
                )
                for r in responses
            ])

    def list_runs(self):
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT
                    run_id, provider, model, prompt_set,
                    started_at, completed_at, status,
                    response_count, duration_seconds,
                    COALESCE(error_count, 0) AS error_count
                FROM visibility_runs
                ORDER BY started_at DESC
            """)
            return cursor.fetchall()

    def list_responses(self, limit: int = 0, offset: int = 0,
                       search: str = "", provider: str = ""):
        """Fetch responses with optional DB-side filtering and pagination.
        Pass limit=0 (default) to fetch all rows — used by analytics.
        Pass limit>0 for the Raw Data tab display.
        """
        clauses, params = [], []
        if provider:
            clauses.append("vresp.provider = ?")
            params.append(provider)
        if search:
            clauses.append(
                "(INSTR(LOWER(COALESCE(vresp.family_name,'')), LOWER(?)) > 0"
                " OR INSTR(LOWER(vresp.prompt), LOWER(?)) > 0"
                " OR INSTR(LOWER(vresp.response), LOWER(?)) > 0)"
            )
            params.extend([search, search, search])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        pagination = f"LIMIT {int(limit)} OFFSET {int(offset)}" if limit > 0 else ""
        with self.connect() as conn:
            cursor = conn.execute(f"""
                SELECT
                    vresp.id,
                    vresp.run_id,
                    vresp.provider,
                    vresp.model,
                    vresp.prompt,
                    vresp.response,
                    vresp.collected_at,
                    COALESCE(NULLIF(vresp.family_name, ''), vrun.prompt_set) AS family_display
                FROM visibility_responses vresp
                LEFT JOIN visibility_runs vrun ON vresp.run_id = vrun.run_id
                {where}
                ORDER BY vresp.collected_at DESC
                {pagination}
            """, params)
            return cursor.fetchall()

    def count_responses_filtered(self, search: str = "", provider: str = "") -> int:
        clauses, params = [], []
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if search:
            clauses.append(
                "(INSTR(LOWER(COALESCE(family_name,'')), LOWER(?)) > 0"
                " OR INSTR(LOWER(prompt), LOWER(?)) > 0"
                " OR INSTR(LOWER(response), LOWER(?)) > 0)"
            )
            params.extend([search, search, search])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.connect() as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM visibility_responses {where}", params
            ).fetchone()[0]

    def get_responses_for_run(self, run_id):
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT
                    id, run_id, provider, model, prompt, response, collected_at,
                    COALESCE(NULLIF(family_name, ''), '') AS family_name
                FROM visibility_responses
                WHERE run_id = ?
                ORDER BY collected_at ASC
            """, (run_id,))
            return cursor.fetchall()

    def count_responses(self) -> int:
        with self.connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM visibility_responses")
            return cursor.fetchone()[0]

    def count_stats(self) -> dict:
        """Pure counts for the Raw Data tab KPI row — no derived metrics."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                                                          AS total,
                    COUNT(DISTINCT vr.provider)                                       AS providers,
                    COUNT(DISTINCT vr.run_id)                                         AS runs,
                    COUNT(DISTINCT COALESCE(NULLIF(vr.family_name, ''), vs.prompt_set, '?')) AS families
                FROM visibility_responses vr
                LEFT JOIN visibility_runs vs ON vr.run_id = vs.run_id
            """).fetchone()
        return {
            "total":     row[0] or 0,
            "providers": row[1] or 0,
            "runs":      row[2] or 0,
            "families":  row[3] or 0,
        }
