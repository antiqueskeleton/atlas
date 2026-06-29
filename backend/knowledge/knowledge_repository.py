import csv
import sqlite3
from pathlib import Path

from backend.services.paths import get_data_dir, get_db_path


class KnowledgeRepository:
    MARKET_ID = 1

    def __init__(self):
        self._db = get_db_path()
        self._data = get_data_dir()

    def _conn(self):
        return sqlite3.connect(str(self._db))

    # ─── Brands ───────────────────────────────────────────────────────────────

    def list_brands(self):
        with self._conn() as c:
            return c.execute(
                "SELECT brand_id, name, website, description, active "
                "FROM brands WHERE market_id=? ORDER BY name",
                (self.MARKET_ID,),
            ).fetchall()

    def get_brand(self, brand_id):
        with self._conn() as c:
            return c.execute(
                "SELECT brand_id, name, website, description, active FROM brands WHERE brand_id=?",
                (brand_id,),
            ).fetchone()

    def add_brand(self, name, website="", description=""):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO brands (market_id, name, website, description, active) VALUES (?,?,?,?,1)",
                (self.MARKET_ID, name.strip(), website.strip(), description.strip()),
            )
            row_id = cur.lastrowid
        self.export_brands_csv()
        return row_id

    def update_brand(self, brand_id, name, website="", description="", active=1):
        with self._conn() as c:
            c.execute(
                "UPDATE brands SET name=?, website=?, description=?, active=? WHERE brand_id=?",
                (name.strip(), website.strip(), description.strip(), int(active), brand_id),
            )
        self.export_brands_csv()

    def delete_brand(self, brand_id):
        with self._conn() as c:
            c.execute("DELETE FROM brands WHERE brand_id=?", (brand_id,))
        self.export_brands_csv()

    def export_brands_csv(self):
        rows = self.list_brands()
        csv_path = self._data / "brands.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "website", "description"])
            for _, name, website, description, _ in rows:
                writer.writerow([name, website or "", description or ""])

    # ─── Features ─────────────────────────────────────────────────────────────

    def list_features(self):
        with self._conn() as c:
            return c.execute(
                "SELECT feature_id, name, category FROM features WHERE market_id=? ORDER BY category, name",
                (self.MARKET_ID,),
            ).fetchall()

    def add_feature(self, name, category=""):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO features (market_id, name, category) VALUES (?,?,?)",
                (self.MARKET_ID, name.strip(), category.strip()),
            )
            row_id = cur.lastrowid
        self.export_features_csv()
        return row_id

    def update_feature(self, feature_id, name, category=""):
        with self._conn() as c:
            c.execute(
                "UPDATE features SET name=?, category=? WHERE feature_id=?",
                (name.strip(), category.strip(), feature_id),
            )
        self.export_features_csv()

    def delete_feature(self, feature_id):
        with self._conn() as c:
            c.execute("DELETE FROM features WHERE feature_id=?", (feature_id,))
        self.export_features_csv()

    def export_features_csv(self):
        rows = self.list_features()
        csv_path = self._data / "features.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "category"])
            for _, name, category in rows:
                writer.writerow([name, category or ""])

    # ─── Personas ─────────────────────────────────────────────────────────────

    def list_personas(self):
        with self._conn() as c:
            return c.execute(
                "SELECT persona_id, name, description, primary_goal, concerns, priority "
                "FROM personas WHERE market_id=? ORDER BY "
                "CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, name",
                (self.MARKET_ID,),
            ).fetchall()

    def get_persona(self, persona_id):
        with self._conn() as c:
            return c.execute(
                "SELECT persona_id, name, description, primary_goal, concerns, priority "
                "FROM personas WHERE persona_id=?",
                (persona_id,),
            ).fetchone()

    def add_persona(self, name, description="", primary_goal="", concerns="", priority="Medium"):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO personas (market_id, name, description, primary_goal, concerns, priority) "
                "VALUES (?,?,?,?,?,?)",
                (self.MARKET_ID, name.strip(), description.strip(),
                 primary_goal.strip(), concerns.strip(), priority),
            )
            return cur.lastrowid

    def update_persona(self, persona_id, name, description="", primary_goal="", concerns="", priority="Medium"):
        with self._conn() as c:
            c.execute(
                "UPDATE personas SET name=?, description=?, primary_goal=?, concerns=?, priority=? "
                "WHERE persona_id=?",
                (name.strip(), description.strip(), primary_goal.strip(),
                 concerns.strip(), priority, persona_id),
            )

    def delete_persona(self, persona_id):
        with self._conn() as c:
            c.execute("DELETE FROM personas WHERE persona_id=?", (persona_id,))

    # ─── Scenarios ────────────────────────────────────────────────────────────

    def list_scenarios(self):
        with self._conn() as c:
            return c.execute(
                "SELECT scenario_id, name, description FROM buying_scenarios "
                "WHERE market_id=? ORDER BY name",
                (self.MARKET_ID,),
            ).fetchall()

    def get_scenario(self, scenario_id):
        with self._conn() as c:
            return c.execute(
                "SELECT scenario_id, name, description FROM buying_scenarios WHERE scenario_id=?",
                (scenario_id,),
            ).fetchone()

    def add_scenario(self, name, description=""):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO buying_scenarios (market_id, name, description) VALUES (?,?,?)",
                (self.MARKET_ID, name.strip(), description.strip()),
            )
            return cur.lastrowid

    def update_scenario(self, scenario_id, name, description=""):
        with self._conn() as c:
            c.execute(
                "UPDATE buying_scenarios SET name=?, description=? WHERE scenario_id=?",
                (name.strip(), description.strip(), scenario_id),
            )

    def delete_scenario(self, scenario_id):
        with self._conn() as c:
            c.execute("DELETE FROM buying_scenarios WHERE scenario_id=?", (scenario_id,))

    # ─── Buying Stages ────────────────────────────────────────────────────────

    def list_buying_stages(self):
        with self._conn() as c:
            return c.execute(
                "SELECT stage_id, name, description, sort_order FROM buying_stages ORDER BY sort_order",
            ).fetchall()

    def get_buying_stage(self, stage_id):
        with self._conn() as c:
            return c.execute(
                "SELECT stage_id, name, description, sort_order FROM buying_stages WHERE stage_id=?",
                (stage_id,),
            ).fetchone()

    def add_buying_stage(self, name, description="", sort_order=99):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO buying_stages (name, description, sort_order) VALUES (?,?,?)",
                (name.strip(), description.strip(), int(sort_order)),
            )
            return cur.lastrowid

    def update_buying_stage(self, stage_id, name, description="", sort_order=99):
        with self._conn() as c:
            c.execute(
                "UPDATE buying_stages SET name=?, description=?, sort_order=? WHERE stage_id=?",
                (name.strip(), description.strip(), int(sort_order), stage_id),
            )

    def delete_buying_stage(self, stage_id):
        with self._conn() as c:
            c.execute("DELETE FROM buying_stages WHERE stage_id=?", (stage_id,))

    # ─── Prompt Families ──────────────────────────────────────────────────────

    def list_prompt_families(self):
        with self._conn() as c:
            return c.execute(
                "SELECT family_id, family_name, search_intent, business_value, priority "
                "FROM prompt_families WHERE market_id=? ORDER BY "
                "CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, family_name",
                (self.MARKET_ID,),
            ).fetchall()

    def add_prompt_family(self, family_name, search_intent="", business_value="", priority="Medium"):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO prompt_families (market_id, family_name, search_intent, business_value, priority) "
                "VALUES (?,?,?,?,?)",
                (self.MARKET_ID, family_name.strip(), search_intent.strip(),
                 business_value.strip(), priority),
            )
            return cur.lastrowid

    def get_prompt_counts(self):
        """Returns {family_name: count} from market_questions.csv."""
        csv_path = self._data / "market_questions.csv"
        counts: dict[str, int] = {}
        if not csv_path.exists():
            return counts
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fn = row.get("family_name", "").strip()
                if fn:
                    counts[fn] = counts.get(fn, 0) + 1
        return counts

    def list_prompts_in_family(self, family_name):
        """Returns [(prompt_style, prompt_text, prompt_influence_score)] for a family."""
        csv_path = self._data / "market_questions.csv"
        rows = []
        if not csv_path.exists():
            return rows
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("family_name", "").strip() == family_name:
                    rows.append((
                        row.get("prompt_style", ""),
                        row.get("prompt_text", ""),
                        row.get("prompt_influence_score", ""),
                    ))
        return rows

    def add_prompt(self, family_name, prompt_style, prompt_text, influence_score="5"):
        csv_path = self._data / "market_questions.csv"
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([family_name, prompt_style, prompt_text, influence_score])

    # ─── Web Intelligence ─────────────────────────────────────────────────────

    def _ensure_web_table(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS web_intelligence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand_id INTEGER REFERENCES brands(brand_id),
                    domain TEXT,
                    monthly_visits_est INTEGER DEFAULT 0,
                    domain_authority INTEGER DEFAULT 0,
                    organic_keywords_est INTEGER DEFAULT 0,
                    backlink_count INTEGER DEFAULT 0,
                    top_keywords TEXT,
                    notes TEXT,
                    data_source TEXT DEFAULT 'manual',
                    recorded_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def list_web_intelligence(self):
        self._ensure_web_table()
        with self._conn() as c:
            return c.execute("""
                SELECT w.id, COALESCE(b.name, '?') AS brand_name, w.domain,
                       w.monthly_visits_est, w.domain_authority, w.organic_keywords_est,
                       w.backlink_count, w.top_keywords, w.notes, w.data_source,
                       w.recorded_at
                FROM web_intelligence w
                LEFT JOIN brands b ON b.brand_id = w.brand_id
                ORDER BY brand_name
            """).fetchall()

    def get_web_entry(self, entry_id):
        self._ensure_web_table()
        with self._conn() as c:
            return c.execute("""
                SELECT w.id, w.brand_id, COALESCE(b.name,'?') AS brand_name, w.domain,
                       w.monthly_visits_est, w.domain_authority, w.organic_keywords_est,
                       w.backlink_count, w.top_keywords, w.notes, w.data_source
                FROM web_intelligence w
                LEFT JOIN brands b ON b.brand_id = w.brand_id
                WHERE w.id=?
            """, (entry_id,)).fetchone()

    def add_web_entry(self, brand_id, domain, monthly_visits=0, domain_authority=0,
                      organic_keywords=0, backlinks=0, top_keywords="", notes="", source="manual"):
        self._ensure_web_table()
        with self._conn() as c:
            cur = c.execute("""
                INSERT INTO web_intelligence
                    (brand_id, domain, monthly_visits_est, domain_authority,
                     organic_keywords_est, backlink_count, top_keywords, notes, data_source)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (brand_id, domain.strip(), monthly_visits, domain_authority,
                  organic_keywords, backlinks, top_keywords.strip(), notes.strip(), source))
            return cur.lastrowid

    def update_web_entry(self, entry_id, brand_id, domain, monthly_visits=0, domain_authority=0,
                          organic_keywords=0, backlinks=0, top_keywords="", notes="", source="manual"):
        self._ensure_web_table()
        with self._conn() as c:
            c.execute("""
                UPDATE web_intelligence
                SET brand_id=?, domain=?, monthly_visits_est=?, domain_authority=?,
                    organic_keywords_est=?, backlink_count=?, top_keywords=?, notes=?,
                    data_source=?, recorded_at=datetime('now')
                WHERE id=?
            """, (brand_id, domain.strip(), monthly_visits, domain_authority,
                  organic_keywords, backlinks, top_keywords.strip(), notes.strip(), source, entry_id))

    def delete_web_entry(self, entry_id):
        self._ensure_web_table()
        with self._conn() as c:
            c.execute("DELETE FROM web_intelligence WHERE id=?", (entry_id,))

    def delete_prompt(self, family_name, prompt_text):
        csv_path = self._data / "market_questions.csv"
        if not csv_path.exists():
            return
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["family_name", "prompt_style", "prompt_text", "prompt_influence_score"]
            rows = list(reader)
        keep = [
            r for r in rows
            if not (r.get("family_name") == family_name and r.get("prompt_text") == prompt_text)
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(keep)
