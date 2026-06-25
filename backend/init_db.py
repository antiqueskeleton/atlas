from pathlib import Path
import csv
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'database' / 'atlas.db'
SCHEMA_PATH = ROOT / 'database' / 'schema.sql'
DATA_DIR = ROOT / 'data'


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def get_id(conn, table, id_col, where_col, value, extra_where='', extra_params=()):
    sql = f'SELECT {id_col} FROM {table} WHERE {where_col} = ? {extra_where}'
    row = conn.execute(sql, (value, *extra_params)).fetchone()
    return row[0] if row else None


def init_schema(conn):
    conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))


def load_seed_data(conn):
    conn.execute("INSERT OR IGNORE INTO markets (name, description) VALUES (?, ?)", (
        'Portable Power',
        'Portable generators, inverter generators, battery backup, solar generators, and emergency power.'
    ))
    market_id = get_id(conn, 'markets', 'market_id', 'name', 'Portable Power')

    with open(DATA_DIR / 'brands.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            conn.execute(
                'INSERT OR IGNORE INTO brands (market_id, name, website, description) VALUES (?, ?, ?, ?)',
                (market_id, row['name'], row.get('website'), row.get('description'))
            )

    with open(DATA_DIR / 'topics.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            conn.execute(
                'INSERT OR IGNORE INTO topics (market_id, name, priority) VALUES (?, ?, ?)',
                (market_id, row['name'], int(row.get('priority') or 3))
            )

    with open(DATA_DIR / 'scenarios.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            conn.execute(
                'INSERT OR IGNORE INTO buying_scenarios (market_id, name, description) VALUES (?, ?, ?)',
                (market_id, row['name'], row.get('description'))
            )

    with open(DATA_DIR / 'features.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            conn.execute(
                'INSERT OR IGNORE INTO features (market_id, name, category) VALUES (?, ?, ?)',
                (market_id, row['name'], row.get('category'))
            )

    with open(DATA_DIR / 'ai_models.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            conn.execute(
                'INSERT OR IGNORE INTO ai_models (vendor, model_name, enabled) VALUES (?, ?, ?)',
                (row['vendor'], row['model_name'], int(row.get('enabled') or 1))
            )

    with open(DATA_DIR / 'prompts.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            topic_id = get_id(conn, 'topics', 'topic_id', 'name', row['topic'], 'AND market_id = ?', (market_id,))
            scenario_id = get_id(conn, 'buying_scenarios', 'scenario_id', 'name', row['scenario'], 'AND market_id = ?', (market_id,))
            conn.execute(
                'INSERT OR IGNORE INTO prompts (market_id, topic_id, scenario_id, prompt_text, priority) VALUES (?, ?, ?, ?, ?)',
                (market_id, topic_id, scenario_id, row['prompt_text'], int(row.get('priority') or 3))
            )
    conn.commit()


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as conn:
        init_schema(conn)
        load_seed_data(conn)
    print(f'Atlas database initialized: {DB_PATH}')


if __name__ == '__main__':
    main()
