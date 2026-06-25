PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS markets (
    market_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS brands (
    brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    website TEXT,
    description TEXT,
    active INTEGER DEFAULT 1,
    UNIQUE(market_id, name),
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    UNIQUE(market_id, name),
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);

CREATE TABLE IF NOT EXISTS buying_scenarios (
    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE(market_id, name),
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);

CREATE TABLE IF NOT EXISTS features (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    UNIQUE(market_id, name),
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);

CREATE TABLE IF NOT EXISTS personas (
    persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    primary_goal TEXT,
    concerns TEXT,
    priority INTEGER DEFAULT 3,
    UNIQUE(market_id, name),
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);

CREATE TABLE IF NOT EXISTS buying_stages (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prompt_families (
    family_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    topic_id INTEGER,
    scenario_id INTEGER,
    persona_id INTEGER,
    stage_id INTEGER,
    family_name TEXT NOT NULL,
    search_intent TEXT,
    business_value INTEGER DEFAULT 50,
    seasonality TEXT,
    priority INTEGER DEFAULT 3,
    UNIQUE(market_id, family_name, persona_id, scenario_id),
    FOREIGN KEY (market_id) REFERENCES markets(market_id),
    FOREIGN KEY (topic_id) REFERENCES topics(topic_id),
    FOREIGN KEY (scenario_id) REFERENCES buying_scenarios(scenario_id),
    FOREIGN KEY (persona_id) REFERENCES personas(persona_id),
    FOREIGN KEY (stage_id) REFERENCES buying_stages(stage_id)
);

CREATE TABLE IF NOT EXISTS market_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    prompt_style TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_influence_score INTEGER DEFAULT 50,
    active INTEGER DEFAULT 1,
    UNIQUE(family_id, prompt_style),
    FOREIGN KEY (family_id) REFERENCES prompt_families(family_id)
);

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    topic_id INTEGER,
    scenario_id INTEGER,
    prompt_text TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    status TEXT DEFAULT 'active',
    prompt_style TEXT DEFAULT 'legacy',
    persona_id INTEGER,
    stage_id INTEGER,
    prompt_influence_score INTEGER DEFAULT 50,
    UNIQUE(market_id, prompt_text),
    FOREIGN KEY (market_id) REFERENCES markets(market_id),
    FOREIGN KEY (topic_id) REFERENCES topics(topic_id),
    FOREIGN KEY (scenario_id) REFERENCES buying_scenarios(scenario_id),
    FOREIGN KEY (persona_id) REFERENCES personas(persona_id),
    FOREIGN KEY (stage_id) REFERENCES buying_stages(stage_id)
);

CREATE TABLE IF NOT EXISTS ai_models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    model_name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    UNIQUE(vendor, model_name)
);

CREATE TABLE IF NOT EXISTS ai_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    run_date TEXT NOT NULL,
    full_response TEXT NOT NULL,
    response_status TEXT DEFAULT 'success',
    processing_version TEXT DEFAULT 'v0.2',
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
    FOREIGN KEY (model_id) REFERENCES ai_models(model_id)
);

CREATE TABLE IF NOT EXISTS brand_mentions (
    mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL,
    brand_id INTEGER NOT NULL,
    rank INTEGER,
    sentiment TEXT,
    confidence REAL,
    FOREIGN KEY (response_id) REFERENCES ai_responses(response_id),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
);

CREATE TABLE IF NOT EXISTS feature_mentions (
    mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL,
    feature_id INTEGER NOT NULL,
    brand_id INTEGER,
    sentiment TEXT,
    confidence REAL,
    FOREIGN KEY (response_id) REFERENCES ai_responses(response_id),
    FOREIGN KEY (feature_id) REFERENCES features(feature_id),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    created_date TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence TEXT,
    confidence REAL,
    priority TEXT,
    estimated_impact TEXT,
    status TEXT DEFAULT 'open',
    FOREIGN KEY (market_id) REFERENCES markets(market_id)
);
