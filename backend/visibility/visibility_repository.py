import json
import sqlite3
from urllib.parse import urlparse
from pathlib import Path

from backend.services.paths import get_db_path
from backend.visibility import negation, recommendation
from backend.visibility.cue_zone_cache import compute_cue_zone_cache


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
                    review_status TEXT DEFAULT '',
                    review_note TEXT DEFAULT '',
                    negative_cue_cache TEXT,
                    recommended_cue_cache TEXT,
                    FOREIGN KEY(run_id) REFERENCES visibility_runs(run_id)
                )
            """)

            # Migrations for databases created before these columns existed
            for ddl in (
                "ALTER TABLE visibility_runs ADD COLUMN error_count INTEGER DEFAULT 0",
                "ALTER TABLE visibility_responses ADD COLUMN family_name TEXT DEFAULT ''",
                "ALTER TABLE visibility_responses ADD COLUMN review_status TEXT DEFAULT ''",
                "ALTER TABLE visibility_responses ADD COLUMN review_note TEXT DEFAULT ''",
                # NULL (not '') by default — distinguishes "not computed yet"
                # from "computed, response has zero cue zones" ('{}').
                "ALTER TABLE visibility_responses ADD COLUMN negative_cue_cache TEXT",
                "ALTER TABLE visibility_responses ADD COLUMN recommended_cue_cache TEXT",
                # #96: provider-reported source URLs (JSON list) — currently
                # only Perplexity returns these; NULL for other providers.
                "ALTER TABLE visibility_responses ADD COLUMN citations TEXT",
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
        # Cue-zone cache computed once here, at collection time — the
        # response text is immutable from this point on, so this is the
        # only time this ever needs computing (see cue_zone_cache.py).
        # Cheap per-response (~0.5-1ms); doing it here means analytics never
        # pays this cost again for these rows, instead of paying it fresh on
        # every future summarize_responses() call.
        with self.connect() as conn:
            conn.executemany("""
                INSERT INTO visibility_responses (
                    run_id, provider, model, prompt, response, collected_at, family_name,
                    negative_cue_cache, recommended_cue_cache, citations
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    r.run_id,
                    r.provider,
                    r.model,
                    r.prompt,
                    r.response,
                    r.collected_at.isoformat(),
                    getattr(r, "family_name", ""),
                    compute_cue_zone_cache(r.response, negation._cue_zones),
                    compute_cue_zone_cache(r.response, recommendation._cue_zones),
                    json.dumps(r.citations) if getattr(r, "citations", None) else None,
                )
                for r in responses
            ])

    def find_recent_matching_runs(self, providers: list[str], prompt_set: str,
                                   within_minutes: int = 60) -> list:
        """
        Returns visibility_runs rows for any of `providers` whose prompt_set
        exactly matches `prompt_set` and started within the last
        `within_minutes` minutes (#76) — used to warn before starting a
        likely-redundant rerun of the same collection (e.g. after an
        apparent crash/stall that actually finished, or simple double-click
        impatience).

        Returns (run_id, provider, prompt_set, started_at, status,
        response_count) tuples, most recent first.
        """
        if not providers:
            return []
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(minutes=within_minutes)).isoformat()
        placeholders = ",".join("?" for _ in providers)
        with self.connect() as conn:
            return conn.execute(f"""
                SELECT run_id, provider, prompt_set, started_at, status, response_count
                FROM visibility_runs
                WHERE provider IN ({placeholders})
                  AND prompt_set = ?
                  AND started_at >= ?
                ORDER BY started_at DESC
            """, (*providers, prompt_set, cutoff)).fetchall()

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
                       search: str = "", provider: str = "", review_status: str = ""):
        """Fetch responses with optional DB-side filtering and pagination.
        Pass limit=0 (default) to fetch all rows — used by analytics.
        Pass limit>0 for the Raw Data tab display.
        review_status: "" (no filter), "unreviewed", "flagged", or "reviewed".
        review_status/review_note/cue caches are appended at the END of the
        SELECT (not inserted earlier) so existing positional indexing
        elsewhere (excel_report.py, intelligence_service.py) keeps working
        unchanged.
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
        if review_status == "unreviewed":
            clauses.append("COALESCE(vresp.review_status, '') = ''")
        elif review_status:
            clauses.append("vresp.review_status = ?")
            params.append(review_status)
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
                    COALESCE(NULLIF(vresp.family_name, ''), vrun.prompt_set) AS family_display,
                    COALESCE(vresp.review_status, '') AS review_status,
                    COALESCE(vresp.review_note, '') AS review_note,
                    vresp.negative_cue_cache,
                    vresp.recommended_cue_cache
                FROM visibility_responses vresp
                LEFT JOIN visibility_runs vrun ON vresp.run_id = vrun.run_id
                {where}
                ORDER BY vresp.collected_at DESC
                {pagination}
            """, params)
            return cursor.fetchall()

    def count_responses_filtered(self, search: str = "", provider: str = "",
                                  review_status: str = "") -> int:
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
        if review_status == "unreviewed":
            clauses.append("COALESCE(review_status, '') = ''")
        elif review_status:
            clauses.append("review_status = ?")
            params.append(review_status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.connect() as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM visibility_responses {where}", params
            ).fetchone()[0]

    def set_review_status(self, response_id: int, status: str, note: str = "") -> None:
        """
        status must be one of '' (clear/unreviewed), 'flagged' (extraction
        looks wrong, needs attention), or 'reviewed' (a human confirmed it's
        correct). note is an optional free-text explanation, most useful
        when flagging.
        """
        if status not in ("", "flagged", "reviewed"):
            raise ValueError(f"Invalid review status: {status!r}")
        with self.connect() as conn:
            conn.execute(
                "UPDATE visibility_responses SET review_status=?, review_note=? WHERE id=?",
                (status, note.strip(), response_id),
            )

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

    def count_uncached_cue_zones(self) -> int:
        """Responses collected before the cue-zone cache existed (#81) —
        NULL, not '{}' (a response with genuinely zero zones is still
        cached, just as an empty object; see cue_zone_cache.py)."""
        with self.connect() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM visibility_responses "
                "WHERE negative_cue_cache IS NULL OR recommended_cue_cache IS NULL"
            )
            return cursor.fetchone()[0]

    def backfill_cue_zone_cache(self, batch_size: int = 500) -> int:
        """
        One-time backfill for responses collected before the cue-zone cache
        existed. Safe to call repeatedly/on every startup — only touches
        rows that are actually still uncached, and does nothing (zero
        query cost beyond the initial SELECT) once none remain. Processes
        in batches so a very large backfill (100k+ rows) doesn't hold one
        giant transaction or load the whole table into memory at once.

        Returns the number of rows updated (0 once fully backfilled).
        """
        updated = 0
        while True:
            with self.connect() as conn:
                rows = conn.execute(
                    "SELECT id, response FROM visibility_responses "
                    "WHERE negative_cue_cache IS NULL OR recommended_cue_cache IS NULL "
                    "LIMIT ?",
                    (batch_size,),
                ).fetchall()
                if not rows:
                    break
                conn.executemany(
                    "UPDATE visibility_responses "
                    "SET negative_cue_cache = ?, recommended_cue_cache = ? "
                    "WHERE id = ?",
                    [
                        (
                            compute_cue_zone_cache(text, negation._cue_zones),
                            compute_cue_zone_cache(text, recommendation._cue_zones),
                            row_id,
                        )
                        for row_id, text in rows
                    ],
                )
            updated += len(rows)
            if len(rows) < batch_size:
                break
        return updated

    def count_stats(self) -> dict:
        """Pure counts for the Raw Data tab KPI row — no derived metrics."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                                                          AS total,
                    COUNT(DISTINCT vr.provider)                                       AS providers,
                    COUNT(DISTINCT vr.run_id)                                         AS runs,
                    COUNT(DISTINCT COALESCE(NULLIF(vr.family_name, ''), vs.prompt_set, '?')) AS families,
                    COUNT(CASE WHEN vr.review_status = 'flagged' THEN 1 END)          AS flagged
                FROM visibility_responses vr
                LEFT JOIN visibility_runs vs ON vr.run_id = vs.run_id
            """).fetchone()
        return {
            "total":     row[0] or 0,
            "providers": row[1] or 0,
            "runs":      row[2] or 0,
            "families":  row[3] or 0,
            "flagged":   row[4] or 0,
        }

    def citation_domain_counts(self, limit: int = 25) -> dict:
        """
        Which web domains AI providers actually cite as sources (#96) —
        aggregated from the per-response citation URLs Perplexity returns.
        Returns {"domains": [(domain, citation_count, responses_citing)],
        "responses_with_citations": n}, domains ordered by citation count.
        Direct measurement of the sources feeding AI answers — the target
        list for earned-media work, with zero scraping.
        """
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT citations FROM visibility_responses "
                "WHERE citations IS NOT NULL AND citations != ''"
            ).fetchall()

        citation_totals: dict[str, int] = {}
        response_counts: dict[str, int] = {}
        for (raw,) in rows:
            try:
                urls = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            domains_in_response = set()
            for url in urls or []:
                domain = urlparse(url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                if not domain:
                    continue
                citation_totals[domain] = citation_totals.get(domain, 0) + 1
                domains_in_response.add(domain)
            for domain in domains_in_response:
                response_counts[domain] = response_counts.get(domain, 0) + 1

        ranked = sorted(citation_totals.items(), key=lambda kv: -kv[1])[:limit]
        return {
            "domains": [(d, c, response_counts.get(d, 0)) for d, c in ranked],
            "responses_with_citations": len(rows),
        }
