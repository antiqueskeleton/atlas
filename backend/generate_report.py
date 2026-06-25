from pathlib import Path
import sqlite3
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'database' / 'atlas.db'
REPORT_DIR = ROOT / 'reports'
DASHBOARD_PATH = ROOT / 'frontend' / 'dashboard.html'


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def pct(n, d):
    return round((n / d) * 100, 1) if d else 0


def build_report():
    with connect() as conn:
        total_responses = conn.execute('SELECT COUNT(*) c FROM ai_responses').fetchone()['c']
        brand_rows = conn.execute('''
            SELECT b.name,
                   COUNT(DISTINCT bm.response_id) AS mentioned_responses,
                   AVG(CASE bm.sentiment WHEN 'positive' THEN 1 WHEN 'neutral' THEN 0.5 ELSE 0 END) AS sentiment_score,
                   AVG(CASE WHEN bm.rank IS NULL THEN 5 ELSE bm.rank END) AS avg_rank
            FROM brands b
            LEFT JOIN brand_mentions bm ON b.brand_id = bm.brand_id
            GROUP BY b.brand_id, b.name
            HAVING mentioned_responses > 0
            ORDER BY mentioned_responses DESC, sentiment_score DESC
        ''').fetchall()

        feature_rows = conn.execute('''
            SELECT f.name, COUNT(*) AS mentions
            FROM feature_mentions fm
            JOIN features f ON fm.feature_id = f.feature_id
            GROUP BY f.name
            ORDER BY mentions DESC, f.name
        ''').fetchall()

        missing_firman = conn.execute('''
            SELECT p.prompt_text, m.model_name, ar.full_response
            FROM ai_responses ar
            JOIN prompts p ON ar.prompt_id = p.prompt_id
            JOIN ai_models m ON ar.model_id = m.model_id
            WHERE ar.response_id NOT IN (
                SELECT bm.response_id
                FROM brand_mentions bm
                JOIN brands b ON bm.brand_id = b.brand_id
                WHERE b.name = 'Firman'
            )
            LIMIT 25
        ''').fetchall()

        firman_mentions = conn.execute('''
            SELECT COUNT(DISTINCT bm.response_id) c
            FROM brand_mentions bm
            JOIN brands b ON bm.brand_id = b.brand_id
            WHERE b.name = 'Firman'
        ''').fetchone()['c']

        data = {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'total_responses': total_responses,
            'firman_visibility': pct(firman_mentions, total_responses),
            'brands': [dict(r) | {'visibility': pct(r['mentioned_responses'], total_responses)} for r in brand_rows],
            'features': [dict(r) for r in feature_rows],
            'missing_firman': [dict(r) for r in missing_firman],
        }
        return data


def write_html(data):
    REPORT_DIR.mkdir(exist_ok=True)
    rows = ''.join(
        f"<tr><td>{b['name']}</td><td>{b['visibility']}%</td><td>{b['mentioned_responses']}</td><td>{(b['sentiment_score'] or 0):.2f}</td><td>{(b['avg_rank'] or 0):.1f}</td></tr>"
        for b in data['brands']
    )
    features = ''.join(f"<li>{f['name']} <span>{f['mentions']}</span></li>" for f in data['features'])
    missing = ''.join(f"<li><strong>{m['prompt_text']}</strong><br><small>{m['model_name']}</small></li>" for m in data['missing_firman']) or '<li>None in current sample.</li>'

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Atlas AI Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ --bg:#f4f5f7; --card:#fff; --ink:#1d2433; --muted:#667085; --line:#d9dee7; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:Arial, Helvetica, sans-serif; }}
header {{ background:#111827; color:white; padding:28px 36px; }}
header h1 {{ margin:0; font-size:30px; }}
header p {{ margin:8px 0 0; color:#cbd5e1; }}
main {{ padding:28px 36px; max-width:1200px; margin:auto; }}
.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:0 1px 2px rgba(16,24,40,.04); }}
.kpi {{ font-size:34px; font-weight:700; margin-top:8px; }}
.label {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.04em; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:12px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
.section {{ margin-top:22px; }}
ul {{ padding-left:20px; }}
li {{ margin:9px 0; }}
li span {{ color:var(--muted); }}
@media(max-width:800px) {{ .grid {{ grid-template-columns:1fr; }} main {{ padding:18px; }} }}
</style>
</head>
<body>
<header>
  <h1>Atlas AI</h1>
  <p>Portable Power Market Intelligence — generated {data['generated_at']}</p>
</header>
<main>
  <div class="grid">
    <div class="card"><div class="label">Firman Visibility</div><div class="kpi">{data['firman_visibility']}%</div></div>
    <div class="card"><div class="label">Responses Analyzed</div><div class="kpi">{data['total_responses']}</div></div>
    <div class="card"><div class="label">Brands Detected</div><div class="kpi">{len(data['brands'])}</div></div>
    <div class="card"><div class="label">Features Detected</div><div class="kpi">{len(data['features'])}</div></div>
  </div>

  <div class="card section">
    <h2>Brand Visibility</h2>
    <table>
      <thead><tr><th>Brand</th><th>Visibility</th><th>Mentions</th><th>Sentiment Score</th><th>Avg Rank</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="grid section" style="grid-template-columns:1fr 1fr;">
    <div class="card">
      <h2>Feature Signals</h2>
      <ul>{features}</ul>
    </div>
    <div class="card">
      <h2>Firman Missing From</h2>
      <ul>{missing}</ul>
    </div>
  </div>
</main>
</body>
</html>'''
    DASHBOARD_PATH.write_text(html, encoding='utf-8')
    (REPORT_DIR / 'latest_report.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f'Dashboard written: {DASHBOARD_PATH}')


if __name__ == '__main__':
    write_html(build_report())
