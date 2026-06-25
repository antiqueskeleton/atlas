from pathlib import Path
import csv
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'database' / 'atlas.db'
DATA_DIR = ROOT / 'data'


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def get_id(conn, table, id_col, where_col, value, market_id=None):
    if market_id is None:
        row = conn.execute(f'SELECT {id_col} FROM {table} WHERE {where_col} = ?', (value,)).fetchone()
    else:
        row = conn.execute(f'SELECT {id_col} FROM {table} WHERE {where_col} = ? AND market_id = ?', (value, market_id)).fetchone()
    return row[id_col] if row else None


def main():
    with connect() as conn:
        market_id = get_id(conn, 'markets', 'market_id', 'name', 'Portable Power')
        if not market_id:
            conn.execute("INSERT INTO markets (name, description) VALUES (?, ?)", (
                'Portable Power',
                'Portable generators, inverter generators, battery backup, solar generators, and emergency power.'
            ))
            market_id = get_id(conn, 'markets', 'market_id', 'name', 'Portable Power')

        # Personas
        with open(DATA_DIR / 'personas.csv', newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                conn.execute(
                    '''INSERT OR IGNORE INTO personas
                       (market_id, name, description, primary_goal, concerns, priority)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (market_id, row['name'], row.get('description'), row.get('primary_goal'), row.get('concerns'), int(row.get('priority') or 3))
                )

        # Buying stages
        with open(DATA_DIR / 'buying_stages.csv', newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                conn.execute(
                    'INSERT OR IGNORE INTO buying_stages (name, description, sort_order) VALUES (?, ?, ?)',
                    (row['name'], row.get('description'), int(row.get('sort_order') or 0))
                )

        # Prompt families and market questions
        with open(DATA_DIR / 'prompt_families.csv', newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                topic_id = get_id(conn, 'topics', 'topic_id', 'name', row['topic'], market_id)
                scenario_id = get_id(conn, 'buying_scenarios', 'scenario_id', 'name', row['scenario'], market_id)
                # Auto-create scenario if needed because Sprint 1 uses richer scenario terms.
                if scenario_id is None:
                    conn.execute('INSERT OR IGNORE INTO buying_scenarios (market_id, name, description) VALUES (?, ?, ?)', (market_id, row['scenario'], 'Added by Atlas Intelligence Library.'))
                    scenario_id = get_id(conn, 'buying_scenarios', 'scenario_id', 'name', row['scenario'], market_id)
                persona_id = get_id(conn, 'personas', 'persona_id', 'name', row['persona'], market_id)
                stage_id = get_id(conn, 'buying_stages', 'stage_id', 'name', row['stage'])

                conn.execute(
                    '''INSERT OR IGNORE INTO prompt_families
                       (market_id, topic_id, scenario_id, persona_id, stage_id, family_name, search_intent,
                        business_value, seasonality, priority)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (market_id, topic_id, scenario_id, persona_id, stage_id, row['family_name'], row['search_intent'],
                     int(row.get('business_value') or 50), row.get('seasonality'), int(row.get('priority') or 3))
                )
                fam = conn.execute(
                    '''SELECT family_id FROM prompt_families
                       WHERE market_id = ? AND family_name = ? AND persona_id IS ? AND scenario_id IS ?''',
                    (market_id, row['family_name'], persona_id, scenario_id)
                ).fetchone()
                if not fam:
                    fam = conn.execute('SELECT family_id FROM prompt_families WHERE market_id=? AND family_name=?', (market_id, row['family_name'])).fetchone()
                family_id = fam['family_id']

                variants = [
                    ('search', row['search_prompt'], int(row.get('business_value') or 50)),
                    ('natural', row['natural_prompt'], max(1, int(row.get('business_value') or 50) - 2)),
                    ('conversational', row['conversational_prompt'], min(100, int(row.get('business_value') or 50) + 1)),
                ]
                for style, text, pis in variants:
                    conn.execute(
                        '''INSERT OR IGNORE INTO market_questions
                           (family_id, prompt_style, prompt_text, prompt_influence_score)
                           VALUES (?, ?, ?, ?)''',
                        (family_id, style, text, pis)
                    )
                    conn.execute(
                        '''INSERT OR IGNORE INTO prompts
                           (market_id, topic_id, scenario_id, prompt_text, priority, prompt_style, persona_id, stage_id, prompt_influence_score)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (market_id, topic_id, scenario_id, text, int(row.get('priority') or 3), style, persona_id, stage_id, pis)
                    )
        conn.commit()

        counts = {
            'personas': conn.execute('SELECT COUNT(*) c FROM personas').fetchone()['c'],
            'prompt_families': conn.execute('SELECT COUNT(*) c FROM prompt_families').fetchone()['c'],
            'market_questions': conn.execute('SELECT COUNT(*) c FROM market_questions').fetchone()['c'],
            'prompts': conn.execute('SELECT COUNT(*) c FROM prompts').fetchone()['c'],
        }
    print('Atlas Intelligence Library loaded:', counts)


if __name__ == '__main__':
    main()
