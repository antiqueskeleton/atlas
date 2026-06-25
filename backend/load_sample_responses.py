from pathlib import Path
import csv
import sqlite3
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'database' / 'atlas.db'
DATA_PATH = ROOT / 'data' / 'sample_responses.csv'


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def main():
    with connect() as conn, open(DATA_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            prompt = conn.execute('SELECT prompt_id FROM prompts WHERE prompt_text = ?', (row['prompt_text'],)).fetchone()
            model = conn.execute('SELECT model_id FROM ai_models WHERE model_name = ?', (row['model_name'],)).fetchone()
            if not prompt or not model:
                print('Skipped row:', row['prompt_text'], row['model_name'])
                continue
            conn.execute(
                '''INSERT INTO ai_responses (prompt_id, model_id, run_date, full_response, processing_version)
                   VALUES (?, ?, ?, ?, ?)''',
                (prompt['prompt_id'], model['model_id'], row.get('run_date') or str(date.today()), row['full_response'], 'v0.1')
            )
        conn.commit()
    print('Sample responses loaded.')


if __name__ == '__main__':
    main()
