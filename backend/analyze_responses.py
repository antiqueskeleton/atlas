from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'database' / 'atlas.db'

POSITIVE_WORDS = {'best','reliable','excellent','strong','good','great','quiet','affordable','value','premium','efficient','dependable','solid','recommended'}
NEGATIVE_WORDS = {'avoid','poor','bad','weak','expensive','loud','heavy','unreliable','limited','problem','problems'}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def sentiment_for_context(text):
    words = set(re.findall(r'[a-z]+', text.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg:
        return 'positive'
    if neg > pos:
        return 'negative'
    return 'neutral'


def rank_brand(response, brand_name):
    lines = response.splitlines()
    for line in lines:
        match = re.match(r'\s*(\d+)[\).:-]?\s*(.*)', line)
        if match and brand_name.lower() in match.group(2).lower():
            return int(match.group(1))
    return None


def analyze():
    with connect() as conn:
        brands = conn.execute('SELECT brand_id, name FROM brands WHERE active = 1').fetchall()
        features = conn.execute('SELECT feature_id, name FROM features').fetchall()
        responses = conn.execute('SELECT response_id, full_response FROM ai_responses').fetchall()

        conn.execute('DELETE FROM brand_mentions')
        conn.execute('DELETE FROM feature_mentions')

        for response in responses:
            text = response['full_response']
            lower = text.lower()

            for brand in brands:
                name = brand['name']
                if re.search(r'\b' + re.escape(name.lower()) + r'\b', lower):
                    idx = lower.find(name.lower())
                    context = text[max(0, idx-120): idx+180]
                    conn.execute(
                        '''INSERT INTO brand_mentions (response_id, brand_id, rank, sentiment, confidence)
                           VALUES (?, ?, ?, ?, ?)''',
                        (response['response_id'], brand['brand_id'], rank_brand(text, name), sentiment_for_context(context), 0.85)
                    )

            for feature in features:
                name = feature['name']
                if re.search(r'\b' + re.escape(name.lower()) + r'\b', lower):
                    idx = lower.find(name.lower())
                    context = text[max(0, idx-120): idx+180]
                    brand_id = None
                    for brand in brands:
                        if brand['name'].lower() in context.lower():
                            brand_id = brand['brand_id']
                            break
                    conn.execute(
                        '''INSERT INTO feature_mentions (response_id, feature_id, brand_id, sentiment, confidence)
                           VALUES (?, ?, ?, ?, ?)''',
                        (response['response_id'], feature['feature_id'], brand_id, sentiment_for_context(context), 0.70)
                    )
        conn.commit()
        print(f'Analyzed {len(responses)} responses.')


if __name__ == '__main__':
    analyze()
