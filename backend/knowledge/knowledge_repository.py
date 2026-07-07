import csv
import sqlite3
from pathlib import Path

from backend.services.paths import get_data_dir, get_db_path


_FULL_BRAND_LIST = [
    # Tier 1 — Major Consumer Brands
    # (name, website, description, aliases, tier, product_types, country, parent_company)
    ("Firman",             "https://firmanpowerequipment.com", "Portable generators and power equipment",          "Firman Power Equipment,FIRMAN",         1, "Portable,Inverter",          "US",     ""),
    ("Generac",            "https://www.generac.com",          "Home standby and portable power equipment",        "Generac Power Systems",                 1, "Portable,Inverter,Standby",  "US",     ""),
    ("Champion",           "https://www.championpowerequipment.com", "Portable generators and power equipment",   "",                                      1, "Portable,Inverter,Standby",  "US",     ""),
    ("Honda",              "https://powerequipment.honda.com", "Premium portable generators and power equipment",  "Honda Power Equipment",                 1, "Portable,Inverter",          "Global", "Honda Motor Co."),
    ("Westinghouse",       "https://westinghouseoutdoorpower.com", "Portable generators and outdoor power equipment", "",                                 1, "Portable,Inverter,Standby",  "US",     ""),
    ("Briggs & Stratton",  "https://www.briggsandstratton.com","Engines and portable generators",                  "Briggs,B&S,Briggs and Stratton",        1, "Portable,Inverter,Standby",  "US",     ""),
    ("Cummins",            "https://www.cummins.com",          "Standby and portable power equipment",             "Cummins Onan,Onan",                     1, "Portable,Inverter,Standby",  "Global", ""),
    ("Kohler",             "https://www.kohlerpower.com",      "Premium home standby generators",                  "Kohler Power",                          1, "Standby",                    "US",     "Kohler Co."),
    ("DuroMax",            "https://www.duromaxpower.com",     "Portable generators and engines",                  "Duro Max",                              1, "Portable,Inverter",          "US",     ""),
    ("DuroStar",           "https://www.durostarpower.com",    "Value portable generators",                        "Duro Star",                             1, "Portable",                   "US",     ""),
    ("WEN",                "https://wenproducts.com",          "Value tools and portable generators",              "",                                      1, "Portable,Inverter",          "US",     ""),
    ("Pulsar",             "https://pulsar-products.com",      "Portable generators and outdoor power equipment",  "",                                      1, "Portable,Inverter",          "US",     ""),
    ("Genmax",             "https://www.genmax.com",           "Portable and inverter generators",                 "",                                      1, "Portable,Inverter",          "US",     ""),
    ("A-iPower",           "https://www.aipowerusa.com",       "Portable and inverter generators",                 "Aipower,AI Power,AiPower",              1, "Portable,Inverter",          "US",     ""),
    ("Yamaha",             "https://www.yamahagenerators.com", "Premium inverter generators",                      "Yamaha Power",                          1, "Portable,Inverter",          "Global", "Yamaha Motor Co."),
    ("Powermate",          "https://www.powermate.com",        "Portable generators",                              "Coleman Powermate",                     1, "Portable,Inverter",          "US",     ""),
    ("Ryobi",              "https://www.ryobitools.com",       "Portable generators and power tools",              "",                                      1, "Portable,Inverter",          "Global", "Techtronic Industries"),
    ("CAT",                "https://www.cat.com",              "Portable and commercial generators",               "Caterpillar",                           1, "Portable,Inverter",          "Global", "Caterpillar Inc."),
    ("Predator",           "https://www.harborfreight.com",    "Value generator brand sold by Harbor Freight",     "",                                      1, "Portable,Inverter",          "US",     "Harbor Freight"),
    ("Craftsman",          "https://www.craftsman.com",        "Portable generators and tools",                    "",                                      1, "Portable,Inverter",          "US",     "Stanley Black & Decker"),
    ("DeWalt",             "https://www.dewalt.com",           "Portable generators and power tools",              "",                                      1, "Portable",                   "Global", "Stanley Black & Decker"),
    ("Sportsman",          "https://www.sportsmangenerators.com", "Portable and inverter generators",              "",                                      1, "Portable,Inverter",          "US",     ""),
    ("Powerhorse",         "https://www.northerntool.com",     "Portable generators sold by Northern Tool",        "",                                      1, "Portable,Inverter",          "US",     "Northern Tool"),
    ("NorthStar",          "https://www.northerntool.com",     "Portable generators sold by Northern Tool",        "North Star",                            1, "Portable",                   "US",     "Northern Tool"),
    # Tier 2 — Mid-size Brands
    ("All Power America",  "https://www.apgroupusa.com",       "Portable generators",                              "APG,All Power",                         2, "Portable,Inverter",          "US",     ""),
    ("Buffalo Tools",      "https://www.buffalotools.com",     "Value portable generators",                        "",                                      2, "Portable",                   "US",     ""),
    ("Black Max",          "",                                 "Portable generators sold at Walmart",              "",                                      2, "Portable,Inverter",          "US",     ""),
    ("BILT HARD",          "",                                 "Portable generators sold at Sam's Club",           "",                                      2, "Portable",                   "US",     ""),
    ("Coleman",            "https://www.coleman.com",          "Portable generators and outdoor products",         "Coleman Generators",                    2, "Portable,Inverter",          "US",     ""),
    ("ETQ",                "",                                 "Portable generators",                              "",                                      2, "Portable,Inverter",          "US",     ""),
    ("Energizer",          "https://energizerpower.com",       "Portable power stations and generators",           "",                                      2, "Portable",                   "US",     ""),
    ("Green-Power America","",                                 "Portable generators",                              "GreenPower",                            2, "Portable",                   "US",     ""),
    ("Hyundai",            "https://www.hyundaipowerproducts.com", "Portable generators",                          "Hyundai Power",                         2, "Portable,Inverter",          "Global", "Hyundai"),
    ("Lifan",              "",                                 "Portable generators and engines",                  "",                                      2, "Portable",                   "Global", ""),
    ("Loncin",             "",                                 "Portable generators and engines",                  "",                                      2, "Portable",                   "Global", ""),
    ("PowerSmart",         "https://powersmartusa.com",        "Portable generators",                              "Power Smart",                           2, "Portable,Inverter",          "US",     ""),
    ("Rainier",            "https://rainierpowerequipment.com","Portable generators",                              "",                                      2, "Portable,Inverter",          "US",     ""),
    ("Smarter Tools",      "",                                 "Portable generators",                              "",                                      2, "Portable",                   "US",     ""),
    ("Tomahawk",           "https://www.tomahawk-power.com",   "Portable generators and construction equipment",   "Tomahawk Power",                        2, "Portable",                   "US",     ""),
    ("United Power",       "",                                 "Portable generators",                              "",                                      2, "Portable",                   "US",     ""),
    ("Wacker Neuson",      "https://www.wackerneuson.com",     "Construction and portable generators",             "Wacker",                                2, "Portable",                   "Global", ""),
    ("Warrior",            "",                                 "Portable generators",                              "",                                      2, "Portable",                   "US",     ""),
    ("Yardmax",            "https://www.yardmax.com",          "Outdoor power equipment and generators",           "Yard Max",                              2, "Portable",                   "US",     ""),
    ("Powerland",          "",                                 "Portable generators",                              "Power Land",                            2, "Portable,Inverter",          "US",     ""),
    ("Dirty Hand Tools",   "https://www.dirtyhandtools.com",   "Outdoor power equipment and generators",           "",                                      2, "Portable",                   "US",     ""),
    ("Ducar",              "",                                 "Portable generators and engines",                  "",                                      2, "Portable",                   "Global", ""),
    ("SENCI",              "https://senci.com",                "Portable generators",                              "",                                      2, "Portable",                   "Global", ""),
    ("Kipor",              "",                                 "Portable and inverter generators",                 "",                                      2, "Portable,Inverter",          "Global", ""),
    ("PowerPro",           "",                                 "Portable generators",                              "Power Pro",                             2, "Portable",                   "US",     ""),
    ("PowerStroke",        "",                                 "Portable generators sold at Walmart",              "Power Stroke",                          2, "Portable,Inverter",          "US",     ""),
    ("Wagan",              "https://www.wagan.com",            "Portable power products and generators",           "",                                      2, "Portable",                   "US",     ""),
    # Tier 3 — Canadian Market Brands
    ("BE Power Equipment", "https://www.bepowerequipment.com", "Portable generators (Canadian market)",            "BE Power",                              3, "Portable",                   "Canada", ""),
    ("Mi-T-M",             "https://www.mitm.com",             "Portable generators and pressure washers",         "Mi T M",                                3, "Portable",                   "US",     ""),
    ("Boss Industrial",    "",                                 "Portable generators (Canadian market)",            "",                                      3, "Portable",                   "Canada", ""),
    ("Powerfist",          "",                                 "Portable generators (Princess Auto Canada)",       "",                                      3, "Portable",                   "Canada", "Princess Auto"),
    ("Mastercraft",        "",                                 "Portable generators sold at Canadian Tire",        "",                                      3, "Portable",                   "Canada", "Canadian Tire"),
    ("Motomaster",         "",                                 "Portable generators sold at Canadian Tire",        "Moto Master",                           3, "Portable",                   "Canada", "Canadian Tire"),
    ("Yardworks",          "",                                 "Outdoor power equipment (Canadian Tire)",          "Yard Works",                            3, "Portable",                   "Canada", "Canadian Tire"),
    # Tier 4 — Retailer Exclusive / House Brands
    ("Masterforce",        "",                                 "Portable generators sold at Menards",              "Master Force",                          4, "Portable",                   "US",     "Menards"),
    ("Earthquake",         "https://www.earthquakeoutdoor.com","Outdoor power equipment and generators",           "",                                      4, "Portable",                   "US",     ""),
    ("Homelite",           "https://www.homelite.com",         "Portable generators sold at Home Depot",           "Home Lite",                             4, "Portable",                   "US",     ""),
    ("JobSmart",           "",                                 "Portable generators sold at Tractor Supply",       "Job Smart",                             4, "Portable",                   "US",     "Tractor Supply"),
    ("Husky",              "",                                 "Tools and generators sold at Home Depot",          "",                                      4, "Portable",                   "US",     "Home Depot"),
    ("Ridgid",             "https://www.ridgid.com",           "Tools and generators sold at Home Depot",          "",                                      4, "Portable",                   "US",     "Techtronic Industries"),
    ("Kobalt",             "",                                 "Tools sold at Lowe's (historical generators)",     "",                                      4, "Portable",                   "US",     "Lowe's"),
    # Tier 5 — Premium Standby Specialists
    ("Honeywell",          "https://www.honeywellgenerators.com", "Licensed standby generators (Generac OEM)",    "Honeywell Generators",                  5, "Standby",                    "US",     "Generac (licensed)"),
    ("Eaton",              "https://www.eaton.com",            "Standby power systems (historical generators)",    "",                                      5, "Standby",                    "Global", ""),
    ("Siemens",            "https://www.siemens.com",          "Standby power systems (historical generators)",    "",                                      5, "Standby",                    "Global", ""),
    # Tier 6 — Commercial Brands
    ("Atlas Copco",        "https://www.atlascopco.com",       "Commercial and industrial generators",             "",                                      6, "Portable",                   "Global", ""),
    ("Multiquip",          "https://www.multiquip.com",        "Commercial portable generators",                   "MQ Power",                              6, "Portable",                   "Global", ""),
    ("Gillette",           "https://www.gillettegenerators.com","Commercial generators",                           "",                                      6, "Portable,Standby",           "US",     ""),
    ("MTU",                "https://www.mtu-solutions.com",    "Industrial generator sets",                        "MTU Onsite Energy",                     6, "Standby",                    "Global", "Rolls-Royce"),
    ("Doosan",             "https://www.doosan.com",           "Industrial generator sets",                        "",                                      6, "Portable,Standby",           "Global", ""),
    ("Winco",              "https://www.wincogen.com",         "Commercial and industrial generators",             "",                                      6, "Portable,Standby",           "US",     ""),
    ("WhisperWatt",        "https://www.whisperwatt.com",       "Commercial portable generators",                   "Whisper Watt",                          6, "Portable",                   "US",     ""),
    ("Pramac",             "https://www.pramac.com",           "Commercial and industrial generators",             "",                                      6, "Portable,Standby",           "Global", ""),
    ("SDMO",               "https://www.sdmo.com",             "Commercial generators",                            "",                                      6, "Portable,Standby",           "Global", ""),
    # Tier 7 — Solar / Battery Brands
    ("Jackery",            "https://www.jackery.com",          "Portable battery and solar generators",            "",                                      7, "Portable",                   "Global", ""),
    ("EcoFlow",            "https://www.ecoflow.com",          "Portable battery and solar power systems",         "Eco Flow",                              7, "Portable",                   "Global", ""),
    ("Bluetti",            "https://www.bluettipower.com",     "Portable power stations and solar generators",     "Bluetti Power",                         7, "Portable",                   "Global", ""),
    ("Goal Zero",          "https://www.goalzero.com",         "Portable solar and battery power systems",         "GoalZero",                              7, "Portable",                   "US",     ""),
    ("Anker",              "https://www.anker.com",            "Portable battery and home backup systems",         "Anker SOLIX,SOLIX",                     7, "Portable",                   "Global", ""),
    ("Renogy",             "https://www.renogy.com",           "Portable solar and battery power systems",         "",                                      7, "Portable",                   "US",     ""),
    ("Geneverse",          "https://geneverse.com",            "Portable power stations",                          "",                                      7, "Portable",                   "US",     ""),
    ("Zendure",            "https://www.zendure.com",          "Portable power stations",                          "",                                      7, "Portable",                   "Global", ""),
    ("Nature's Generator", "https://www.naturesgenerator.com", "Solar and battery generator systems",              "Natures Generator",                     7, "Portable",                   "US",     ""),
    ("Lion Energy",        "https://lionenergy.com",           "Portable power stations",                          "Lion Power",                            7, "Portable",                   "US",     ""),
    ("VTOMAN",             "https://vtoman.com",               "Portable power stations",                          "",                                      7, "Portable",                   "Global", ""),
    ("OUPES",              "https://oupes.com",                "Portable power stations",                          "",                                      7, "Portable",                   "Global", ""),
    ("Mango Power",        "https://www.mangopower.com",       "Portable power stations",                          "MangoPower",                            7, "Portable",                   "Global", ""),
]


class KnowledgeRepository:
    MARKET_ID = 1
    _migrated_dbs: set = set()  # tracks DBs already migrated this session

    def __init__(self):
        self._db = get_db_path()
        self._data = get_data_dir()
        self._ensure_core_tables()

    def _conn(self):
        return sqlite3.connect(str(self._db))

    # ─── Core schema bootstrap ────────────────────────────────────────────────

    def _ensure_core_tables(self):
        """Create all core tables on a fresh DB; idempotent via IF NOT EXISTS."""
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    market_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL UNIQUE,
                    description TEXT,
                    status      TEXT DEFAULT 'active'
                )
            """)
            c.execute(
                "INSERT OR IGNORE INTO markets (market_id, name, description) VALUES (1, 'Portable Generators', 'US portable generator market')"
            )
            c.execute("""
                CREATE TABLE IF NOT EXISTS brands (
                    brand_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id      INTEGER NOT NULL DEFAULT 1,
                    name           TEXT NOT NULL,
                    website        TEXT DEFAULT '',
                    description    TEXT DEFAULT '',
                    active         INTEGER DEFAULT 1,
                    aliases        TEXT DEFAULT '',
                    tier           INTEGER DEFAULT 0,
                    product_types  TEXT DEFAULT '',
                    country        TEXT DEFAULT 'US',
                    parent_company TEXT DEFAULT '',
                    UNIQUE(market_id, name)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS features (
                    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id  INTEGER NOT NULL DEFAULT 1,
                    name       TEXT NOT NULL,
                    category   TEXT DEFAULT '',
                    UNIQUE(market_id, name)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS personas (
                    persona_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id    INTEGER NOT NULL DEFAULT 1,
                    name         TEXT NOT NULL,
                    description  TEXT DEFAULT '',
                    primary_goal TEXT DEFAULT '',
                    concerns     TEXT DEFAULT '',
                    priority     TEXT DEFAULT 'Medium',
                    UNIQUE(market_id, name)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS buying_scenarios (
                    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id   INTEGER NOT NULL DEFAULT 1,
                    name        TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    UNIQUE(market_id, name)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS buying_stages (
                    stage_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id       INTEGER NOT NULL DEFAULT 1,
                    run_id          TEXT,
                    created_date    TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    description     TEXT DEFAULT '',
                    evidence        TEXT DEFAULT '',
                    confidence      REAL DEFAULT 0,
                    priority        TEXT DEFAULT 'Medium',
                    estimated_impact TEXT DEFAULT '',
                    status          TEXT DEFAULT 'open'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS prompt_families (
                    family_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id      INTEGER NOT NULL DEFAULT 1,
                    topic_id       INTEGER,
                    scenario_id    INTEGER,
                    persona_id     INTEGER,
                    stage_id       INTEGER,
                    family_name    TEXT NOT NULL,
                    search_intent  TEXT DEFAULT '',
                    business_value INTEGER DEFAULT 50,
                    seasonality    TEXT DEFAULT '',
                    priority       INTEGER DEFAULT 3,
                    UNIQUE(market_id, family_name, persona_id, scenario_id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS market_questions (
                    question_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    family_id            INTEGER NOT NULL,
                    prompt_style         TEXT NOT NULL,
                    prompt_text          TEXT NOT NULL,
                    prompt_influence_score INTEGER DEFAULT 50,
                    active               INTEGER DEFAULT 1,
                    UNIQUE(family_id, prompt_style)
                )
            """)

    # ─── Brands ───────────────────────────────────────────────────────────────

    def _migrate_brands_table(self):
        db_key = str(self._db)
        if db_key in KnowledgeRepository._migrated_dbs:
            return
        if getattr(self, "_in_migration", False):
            return
        self._in_migration = True
        try:
            self._ensure_core_tables()
            with self._conn() as c:
                for col, defn in [
                    ("aliases",        "TEXT    DEFAULT ''"),
                    ("tier",           "INTEGER DEFAULT 0"),
                    ("product_types",  "TEXT    DEFAULT ''"),
                    ("country",        "TEXT    DEFAULT 'US'"),
                    ("parent_company", "TEXT    DEFAULT ''"),
                ]:
                    try:
                        c.execute(f"ALTER TABLE brands ADD COLUMN {col} {defn}")
                    except Exception:
                        pass  # column already exists
            # Seed full list if this is a fresh install
            with self._conn() as c:
                count = c.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
            if count < 20:
                self._seed_full_brand_list()
            # Fill in empty metadata for any brand that matches the seed list
            self._update_existing_from_seed()
            KnowledgeRepository._migrated_dbs.add(db_key)
        finally:
            self._in_migration = False

    def _update_existing_from_seed(self):
        """For brands already in the DB, fill in metadata (aliases, types, country, etc.) from seed."""
        seed_map = {entry[0].lower(): entry for entry in _FULL_BRAND_LIST}
        with self._conn() as c:
            rows = c.execute(
                "SELECT brand_id, name FROM brands WHERE market_id=?", (self.MARKET_ID,)
            ).fetchall()
            for brand_id, name in rows:
                seed = seed_map.get(name.lower())
                if seed:
                    # seed: (name, website, description, aliases, tier, product_types, country, parent_company)
                    c.execute(
                        "UPDATE brands SET aliases=?, tier=?, product_types=?, country=?, parent_company=? "
                        "WHERE brand_id=?",
                        (seed[3], seed[4], seed[5], seed[6], seed[7], brand_id),
                    )

    def _seed_full_brand_list(self):
        with self._conn() as c:
            existing_names = {row[0].lower() for row in c.execute(
                "SELECT name FROM brands WHERE market_id=?", (self.MARKET_ID,)
            ).fetchall()}
        for entry in _FULL_BRAND_LIST:
            if entry[0].lower() not in existing_names:
                self.add_brand(*entry, _log_event=False)

    def list_brands(self):
        self._migrate_brands_table()
        with self._conn() as c:
            return c.execute(
                "SELECT brand_id, name, website, description, active, "
                "aliases, tier, product_types, country, parent_company "
                "FROM brands WHERE market_id=? ORDER BY tier, name",
                (self.MARKET_ID,),
            ).fetchall()

    def get_brand(self, brand_id):
        self._migrate_brands_table()
        with self._conn() as c:
            return c.execute(
                "SELECT brand_id, name, website, description, active, "
                "aliases, tier, product_types, country, parent_company "
                "FROM brands WHERE brand_id=?",
                (brand_id,),
            ).fetchone()

    # ─── Trend event log ──────────────────────────────────────────────────────
    # A lightweight record of changes that can shift a Trends chart's numbers
    # without any real change in AI behavior (a brand added/removed, an alias
    # list edited, a prompt family added). Trends annotates its time-series
    # charts with these so a viewer can tell "the AI's actual behavior moved"
    # apart from "we changed what we're measuring" (#67) — right now those two
    # look identical on a chart, which risks a real, silently wrong conclusion.

    def _ensure_events_table(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS atlas_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    occurred_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def log_event(self, event_type: str, description: str,
                  occurred_at: str = None):
        """occurred_at (ISO string) lets backfilled events land on the date
        the change actually happened (#90) — omitted, the DB stamps now."""
        self._ensure_events_table()
        with self._conn() as c:
            if occurred_at:
                c.execute(
                    "INSERT INTO atlas_events (event_type, description, occurred_at) "
                    "VALUES (?, ?, ?)",
                    (event_type, description, occurred_at),
                )
            else:
                c.execute(
                    "INSERT INTO atlas_events (event_type, description) VALUES (?, ?)",
                    (event_type, description),
                )

    def list_events(self, since: str = None) -> list:
        """Returns [(event_type, description, occurred_at)] ordered oldest
        first. since, if given, is an ISO date/datetime string — only events
        at or after it are returned."""
        self._ensure_events_table()
        with self._conn() as c:
            if since:
                return c.execute(
                    "SELECT event_type, description, occurred_at FROM atlas_events "
                    "WHERE occurred_at >= ? ORDER BY occurred_at",
                    (since,),
                ).fetchall()
            return c.execute(
                "SELECT event_type, description, occurred_at FROM atlas_events "
                "ORDER BY occurred_at"
            ).fetchall()

    def add_brand(self, name, website="", description="", aliases="", tier=0,
                  product_types="", country="US", parent_company="", active=1,
                  _log_event=True):
        # _log_event=False is used by _seed_full_brand_list() when populating
        # the ~90-brand default list on a fresh DB (or one with <20 brands) —
        # that's initial setup, not a real, trend-relevant user action, so it
        # must not flood the event log with 90 "brand added" markers (#67).
        self._migrate_brands_table()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO brands "
                "(market_id, name, website, description, active, aliases, tier, product_types, country, parent_company) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.MARKET_ID, name.strip(), website.strip(), description.strip(),
                 int(active), aliases.strip() if aliases else "",
                 int(tier) if tier else 0,
                 product_types.strip() if product_types else "",
                 country.strip() if country else "US",
                 parent_company.strip() if parent_company else ""),
            )
            row_id = cur.lastrowid
        self.export_brands_csv()
        if _log_event:
            self.log_event("brand_added", f"Brand added: {name.strip()}")
        return row_id

    def update_brand(self, brand_id, name, website="", description="", active=1,
                     aliases="", tier=0, product_types="", country="US", parent_company=""):
        self._migrate_brands_table()
        prev = self.get_brand(brand_id)
        prev_aliases = (prev[5] or "") if prev else ""
        new_aliases = aliases.strip() if aliases else ""
        with self._conn() as c:
            c.execute(
                "UPDATE brands SET name=?, website=?, description=?, active=?, "
                "aliases=?, tier=?, product_types=?, country=?, parent_company=? "
                "WHERE brand_id=?",
                (name.strip(), website.strip(), description.strip(), int(active),
                 new_aliases,
                 int(tier) if tier else 0,
                 product_types.strip() if product_types else "",
                 country.strip() if country else "US",
                 parent_company.strip() if parent_company else "",
                 brand_id),
            )
        self.export_brands_csv()
        if prev_aliases != new_aliases:
            self.log_event("brand_aliases_changed", f"Alias list changed for brand: {name.strip()}")

    def delete_brand(self, brand_id):
        self._migrate_brands_table()
        prev = self.get_brand(brand_id)
        brand_name = prev[1] if prev else f"id {brand_id}"
        with self._conn() as c:
            c.execute("DELETE FROM brands WHERE brand_id=?", (brand_id,))
        self.export_brands_csv()
        self.log_event("brand_removed", f"Brand removed: {brand_name}")

    def export_brands_csv(self):
        self._migrate_brands_table()
        rows = self.list_brands()
        csv_path = self._data / "brands.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "website", "description"])
            for row in rows:
                writer.writerow([row[1], row[2] or "", row[3] or ""])

    def get_brand_detection_terms(self) -> dict[str, list[str]]:
        """Returns {canonical_name: [lowercase_search_terms]} for all active brands."""
        self._migrate_brands_table()
        rows = self.list_brands()
        result = {}
        for row in rows:
            brand_id, name, website, description, active, aliases, tier, product_types, country, parent_company = row
            if not active:
                continue
            terms = [name.lower()]
            if aliases:
                for alias in aliases.split(","):
                    a = alias.strip().lower()
                    if a and a not in terms:
                        terms.append(a)
            result[name] = terms
        return result

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
        """Returns families from market_questions.csv, sorted by max influence score desc."""
        csv_path = self._data / "market_questions.csv"
        if not csv_path.exists():
            return []
        scores: dict[str, int] = {}
        seen: list[str] = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fn = row.get("family_name", "").strip()
                if not fn:
                    continue
                try:
                    score = int(row.get("prompt_influence_score", 0))
                except (ValueError, TypeError):
                    score = 0
                if fn not in scores:
                    seen.append(fn)
                    scores[fn] = score
                elif score > scores[fn]:
                    scores[fn] = score
        seen.sort(key=lambda n: (-scores[n], n))
        return [(None, fn, "", "", scores[fn]) for fn in seen]

    def add_prompt_family(self, family_name):
        """Creates a new family in market_questions.csv with a blank placeholder row."""
        csv_path = self._data / "market_questions.csv"
        name = family_name.strip()
        if not name:
            return
        needs_header = not csv_path.exists()
        # Check if already exists
        if not needs_header:
            with open(csv_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("family_name", "").strip() == name:
                        return
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if needs_header:
                # A file created fresh (rather than the checked-in, already-
                # populated market_questions.csv every real install ships
                # with) had no header row at all, so the NEXT call's
                # DictReader-based duplicate check above would silently
                # misread the first data row as column names and never
                # detect a real duplicate. Only matters for a from-scratch
                # CSV — the shipped one already has a header — but cheap
                # to guard against unconditionally.
                writer.writerow(["family_name", "prompt_style", "prompt_text", "prompt_influence_score"])
            writer.writerow([name, "", "", "0"])
        self.log_event("family_added", f"Prompt family added: {name}")

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
                    text = row.get("prompt_text", "").strip()
                    if text:
                        rows.append((
                            row.get("prompt_style", ""),
                            text,
                            row.get("prompt_influence_score", ""),
                        ))
        return rows

    def add_prompt(self, family_name, prompt_style, prompt_text, influence_score="5"):
        csv_path = self._data / "market_questions.csv"
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([family_name, prompt_style, prompt_text, influence_score])

    # ─── Prompt Categories ────────────────────────────────────────────────────
    # A purely additive tier ABOVE prompt families, for grouping related
    # families (e.g. "Best Generator Power Outage" + "Best Hurricane
    # Generator" + "Emergency Preparedness Generator") so the Visibility page
    # can select a whole cluster with one checkbox instead of many. Families
    # themselves are untouched — this is a separate DB-backed mapping, not a
    # change to market_questions.csv, so nothing about existing prompts,
    # families, or historical Visibility run data is affected. A family with
    # no row in prompt_family_categories is simply uncategorized.

    def _ensure_category_tables(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS prompt_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS prompt_family_categories (
                    family_name TEXT PRIMARY KEY,
                    category_id INTEGER NOT NULL REFERENCES prompt_categories(id)
                )
            """)

    def list_prompt_categories(self):
        """Returns [(id, name, family_count)] sorted by name."""
        self._ensure_category_tables()
        with self._conn() as c:
            return c.execute("""
                SELECT pc.id, pc.name, COUNT(pfc.family_name) AS family_count
                FROM prompt_categories pc
                LEFT JOIN prompt_family_categories pfc ON pfc.category_id = pc.id
                GROUP BY pc.id, pc.name
                ORDER BY pc.name
            """).fetchall()

    def add_prompt_category(self, name: str) -> int:
        """Creates a category if it doesn't already exist; returns its id either way."""
        self._ensure_category_tables()
        name = name.strip()
        with self._conn() as c:
            row = c.execute("SELECT id FROM prompt_categories WHERE name=?", (name,)).fetchone()
            if row:
                return row[0]
            cur = c.execute("INSERT INTO prompt_categories (name) VALUES (?)", (name,))
            return cur.lastrowid

    def delete_prompt_category(self, category_id: int):
        """Deletes a category; member families become uncategorized (not deleted)."""
        self._ensure_category_tables()
        with self._conn() as c:
            c.execute("DELETE FROM prompt_family_categories WHERE category_id=?", (category_id,))
            c.execute("DELETE FROM prompt_categories WHERE id=?", (category_id,))

    def get_family_category_map(self) -> dict:
        """Returns {family_name: category_name} for every assigned family."""
        self._ensure_category_tables()
        with self._conn() as c:
            rows = c.execute("""
                SELECT pfc.family_name, pc.name
                FROM prompt_family_categories pfc
                JOIN prompt_categories pc ON pc.id = pfc.category_id
            """).fetchall()
            return {family_name: category_name for family_name, category_name in rows}

    def get_families_in_category(self, category_id: int) -> list:
        self._ensure_category_tables()
        with self._conn() as c:
            return [r[0] for r in c.execute(
                "SELECT family_name FROM prompt_family_categories WHERE category_id=?",
                (category_id,),
            ).fetchall()]

    def set_family_category(self, family_name: str, category_id: int | None):
        """Assigns family_name to category_id, or un-assigns it if category_id is None."""
        self._ensure_category_tables()
        with self._conn() as c:
            c.execute("DELETE FROM prompt_family_categories WHERE family_name=?", (family_name,))
            if category_id is not None:
                c.execute(
                    "INSERT INTO prompt_family_categories (family_name, category_id) VALUES (?,?)",
                    (family_name, category_id),
                )

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
                    recorded_at TEXT DEFAULT (datetime('now')),
                    page_title TEXT,
                    meta_description TEXT,
                    h1_tags TEXT,
                    h2_tags TEXT,
                    has_schema INTEGER DEFAULT 0,
                    has_sitemap INTEGER DEFAULT 0,
                    is_https INTEGER DEFAULT 0,
                    load_ms INTEGER DEFAULT 0,
                    scraped_at TEXT,
                    is_own_site INTEGER DEFAULT 0,
                    has_robots_txt INTEGER DEFAULT 0,
                    blocks_ai_crawlers INTEGER DEFAULT 0,
                    blocked_crawler_names TEXT DEFAULT ''
                )
            """)
            for col in (
                "page_title TEXT", "meta_description TEXT", "h1_tags TEXT",
                "h2_tags TEXT", "has_schema INTEGER DEFAULT 0",
                "has_sitemap INTEGER DEFAULT 0", "is_https INTEGER DEFAULT 0",
                "load_ms INTEGER DEFAULT 0", "scraped_at TEXT",
                "is_own_site INTEGER DEFAULT 0",
                "has_robots_txt INTEGER DEFAULT 0",
                "blocks_ai_crawlers INTEGER DEFAULT 0",
                "blocked_crawler_names TEXT DEFAULT ''",
            ):
                try:
                    c.execute(f"ALTER TABLE web_intelligence ADD COLUMN {col}")
                except Exception:
                    pass

    def list_web_intelligence(self):
        """
        Returns on-page signals actually obtainable by scrape_domain() —
        title, meta description, keywords, HTTPS/schema/sitemap, load time,
        AI-crawler robots.txt status, plus whether the entry is flagged as
        the user's own site (own-site entries sort first, so a self-audit
        row is naturally prominent above the competitor comparison rows).
        Deliberately does NOT return monthly_visits_est/domain_authority/
        organic_keywords_est/backlink_count: those columns still exist for
        potential future use, but no code path scrapes them (they're
        proprietary metrics from paid tools like Moz/SEMrush/Ahrefs/
        SimilarWeb) and the Knowledge page no longer displays or edits them.
        """
        self._ensure_web_table()
        with self._conn() as c:
            return c.execute("""
                SELECT w.id, COALESCE(b.name, '?') AS brand_name, w.domain,
                       w.page_title, w.meta_description, w.top_keywords,
                       w.is_https, w.has_schema, w.has_sitemap, w.load_ms,
                       w.notes, w.data_source, w.recorded_at, w.scraped_at,
                       w.is_own_site, w.has_robots_txt, w.blocks_ai_crawlers,
                       w.blocked_crawler_names
                FROM web_intelligence w
                LEFT JOIN brands b ON b.brand_id = w.brand_id
                ORDER BY w.is_own_site DESC, brand_name
            """).fetchall()

    def get_web_entry(self, entry_id):
        self._ensure_web_table()
        with self._conn() as c:
            return c.execute("""
                SELECT w.id, w.brand_id, COALESCE(b.name,'?') AS brand_name, w.domain,
                       w.monthly_visits_est, w.domain_authority, w.organic_keywords_est,
                       w.backlink_count, w.top_keywords, w.notes, w.data_source, w.is_own_site
                FROM web_intelligence w
                LEFT JOIN brands b ON b.brand_id = w.brand_id
                WHERE w.id=?
            """, (entry_id,)).fetchone()

    def add_web_entry(self, brand_id, domain, monthly_visits=0, domain_authority=0,
                      organic_keywords=0, backlinks=0, top_keywords="", notes="", source="manual",
                      is_own_site=False):
        self._ensure_web_table()
        with self._conn() as c:
            cur = c.execute("""
                INSERT INTO web_intelligence
                    (brand_id, domain, monthly_visits_est, domain_authority,
                     organic_keywords_est, backlink_count, top_keywords, notes, data_source,
                     is_own_site)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (brand_id, domain.strip(), monthly_visits, domain_authority,
                  organic_keywords, backlinks, top_keywords.strip(), notes.strip(), source,
                  int(is_own_site)))
            return cur.lastrowid

    def update_web_entry(self, entry_id, brand_id, domain, monthly_visits=0, domain_authority=0,
                          organic_keywords=0, backlinks=0, top_keywords="", notes="", source="manual",
                          is_own_site=False):
        self._ensure_web_table()
        with self._conn() as c:
            c.execute("""
                UPDATE web_intelligence
                SET brand_id=?, domain=?, monthly_visits_est=?, domain_authority=?,
                    organic_keywords_est=?, backlink_count=?, top_keywords=?, notes=?,
                    data_source=?, is_own_site=?, recorded_at=datetime('now')
                WHERE id=?
            """, (brand_id, domain.strip(), monthly_visits, domain_authority,
                  organic_keywords, backlinks, top_keywords.strip(), notes.strip(), source,
                  int(is_own_site), entry_id))

    def delete_web_entry(self, entry_id):
        self._ensure_web_table()
        with self._conn() as c:
            c.execute("DELETE FROM web_intelligence WHERE id=?", (entry_id,))

    def update_web_scrape_result(self, entry_id: int, scrape: dict):
        """Persist scraped on-page signals back to the web_intelligence row."""
        self._ensure_web_table()
        import json
        from datetime import datetime
        h1s = json.dumps(scrape.get("h1s", []))
        h2s = json.dumps(scrape.get("h2s", []))
        with self._conn() as c:
            c.execute("""
                UPDATE web_intelligence
                SET page_title=?, meta_description=?, h1_tags=?, h2_tags=?,
                    top_keywords=?, has_schema=?, has_sitemap=?, is_https=?,
                    load_ms=?, data_source='scraped', scraped_at=?,
                    has_robots_txt=?, blocks_ai_crawlers=?, blocked_crawler_names=?
                WHERE id=?
            """, (
                scrape.get("title", "")[:200],
                scrape.get("meta_description", "")[:300],
                h1s, h2s,
                scrape.get("top_keywords", ""),
                int(scrape.get("has_schema", False)),
                int(scrape.get("has_sitemap", False)),
                int(scrape.get("is_https", False)),
                scrape.get("load_ms", 0),
                datetime.now().isoformat(),
                int(scrape.get("has_robots_txt", False)),
                int(scrape.get("blocks_ai_crawlers", False)),
                ", ".join(scrape.get("blocked_crawler_names", [])),
                entry_id,
            ))

    def list_web_intelligence_for_briefing(self) -> list:
        """
        Return scraped/manual entries suitable for feeding into the
        intelligence briefing. is_own_site/blocks_ai_crawlers/
        blocked_crawler_names are appended at the end (not inserted earlier
        in the SELECT) so existing positional unpacking of the first 12
        columns keeps working unchanged.
        """
        self._ensure_web_table()
        with self._conn() as c:
            return c.execute("""
                SELECT COALESCE(b.name, '?') AS brand_name, w.domain,
                       w.page_title, w.meta_description, w.h1_tags,
                       w.top_keywords, w.domain_authority, w.monthly_visits_est,
                       w.has_schema, w.has_sitemap, w.is_https, w.scraped_at,
                       w.is_own_site, w.blocks_ai_crawlers, w.blocked_crawler_names
                FROM web_intelligence w
                LEFT JOIN brands b ON b.brand_id = w.brand_id
                WHERE w.domain IS NOT NULL AND w.domain != ''
                ORDER BY w.is_own_site DESC, brand_name
            """).fetchall()

    def filter_new_brands(self, candidates: list[str]) -> list[str]:
        """Return only candidate names that don't already exist in the library (name or alias)."""
        self._migrate_brands_table()
        existing: set[str] = set()
        with self._conn() as c:
            for name, aliases in c.execute(
                "SELECT name, COALESCE(aliases,'') FROM brands WHERE market_id=?",
                (self.MARKET_ID,),
            ).fetchall():
                existing.add(name.lower().strip())
                for alias in aliases.split(","):
                    a = alias.strip().lower()
                    if a:
                        existing.add(a)
        return [b for b in candidates if b.lower().strip() not in existing]

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
