from desktop.theme.colors import (
    BACKGROUND, CARD, NAVY, SLATE, STEEL, SILVER, LIGHT,
    PRIMARY, ACCENT, ACCENT_DK, TEXT, TEXT_MUTED, SUCCESS, WARNING, DANGER,
)

STYLE = f"""

/* ── Global ──────────────────────────────────────────────────────────────── */

QMainWindow {{
    background: {BACKGROUND};
}}

QWidget {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

/* ── Scroll bars ─────────────────────────────────────────────────────────── */

QScrollBar:vertical {{
    background: {BACKGROUND};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #94A3B8;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

/* ── Status bar ──────────────────────────────────────────────────────────── */

QStatusBar {{
    background: {CARD};
    border-top: 1px solid #E5E7EB;
    color: {TEXT_MUTED};
    font-size: 12px;
}}

/* ── Menu bar ────────────────────────────────────────────────────────────── */

QMenuBar {{
    background: {NAVY};
    color: {SILVER};
    spacing: 2px;
}}
QMenuBar::item {{
    padding: 5px 12px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {SLATE};
    color: {LIGHT};
}}
QMenu {{
    background: {SLATE};
    color: {LIGHT};
    border: 1px solid {STEEL};
    border-radius: 4px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 20px;
}}
QMenu::item:selected {{
    background: {PRIMARY};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {STEEL};
    margin: 3px 0;
}}

/* ── Nav sidebar ─────────────────────────────────────────────────────────── */

QListWidget#AtlasNav {{
    background: {NAVY};
    border: none;
    outline: none;
    padding: 8px 0;
}}
QListWidget#AtlasNav::item {{
    color: {SILVER};
    padding: 11px 16px;
    border-radius: 6px;
    margin: 2px 8px;
    font-size: 14px;
}}
QListWidget#AtlasNav::item:hover {{
    background: {SLATE};
    color: {LIGHT};
}}
QListWidget#AtlasNav::item:selected {{
    background: {PRIMARY};
    color: white;
    font-weight: bold;
}}

/* ── Stat / info cards ───────────────────────────────────────────────────── */

QFrame#StatCard {{
    background: {CARD};
    border: 1px solid #E5E7EB;
    border-radius: 10px;
}}

QLabel#CardTitle {{
    font-size: 13px;
    color: {TEXT_MUTED};
}}

QLabel#CardValue {{
    font-size: 30px;
    font-weight: bold;
    color: {TEXT};
}}

QLabel#CardSubtitle {{
    color: {PRIMARY};
    font-size: 12px;
}}

/* ── Primary button (app-wide accent) ───────────────────────────────────── */

QPushButton#PrimaryBtn {{
    background: {PRIMARY};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton#PrimaryBtn:hover  {{ background: {ACCENT_DK}; }}
QPushButton#PrimaryBtn:pressed {{ background: #004BB5; }}

/* ── Tab widget (hidden tabs, content area) ──────────────────────────────── */

QTabWidget::pane {{
    background: {BACKGROUND};
    border: none;
}}

"""
