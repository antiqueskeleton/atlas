from desktop.theme.colors import (
    BACKGROUND, CARD, SURFACE_2, BORDER, BORDER_STRONG,
    NAVY, SLATE, STEEL, SILVER, LIGHT,
    PRIMARY, PRIMARY_HOVER, PRIMARY_ACTIVE, PRIMARY_TINT,
    TEXT, TEXT_MUTED, HEADING, FONT_BODY, FONT_HEADING,
    R_SM, R_MD, R_LG,
)

# Global QSS — 2026-07 redesign. QSS is a CSS subset: no text-transform,
# no box-shadow (card shadows are QGraphicsDropShadowEffect in code),
# no transitions. Depth comes from color, hairline borders and spacing.

STYLE = f"""

/* ── Global ──────────────────────────────────────────────────────────────── */

QMainWindow {{
    background: {BACKGROUND};
}}

QWidget {{
    font-family: {FONT_BODY};
    font-size: 13px;
    color: {TEXT};
}}

QToolTip {{
    background: {NAVY};
    color: {LIGHT};
    border: 1px solid {SLATE};
    border-radius: {R_MD}px;
    padding: 5px 8px;
    font-size: 12px;
}}

/* ── Scroll bars ─────────────────────────────────────────────────────────── */

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {STEEL};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {STEEL};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ── Status bar ──────────────────────────────────────────────────────────── */

QStatusBar {{
    background: {CARD};
    border-top: 1px solid {BORDER};
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
    background: {NAVY};
    color: {LIGHT};
    border: 1px solid {SLATE};
    border-radius: {R_MD}px;
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
    background: {SLATE};
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
    padding: 10px 16px;
    border-radius: {R_MD}px;
    margin: 2px 8px;
    font-size: 15px;
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
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
}}

QLabel#CardTitle {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_MUTED};
}}

QLabel#CardValue {{
    font-family: {FONT_HEADING};
    font-size: 34px;
    font-weight: 600;
    color: {HEADING};
}}

QLabel#CardSubtitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

/* ── Panels (generic white cards) ────────────────────────────────────────── */

QFrame#Panel, QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
}}

/* Page titles — one rule so every page's H1 matches (they had drifted to
   22/24/28/30px). Barlow Condensed keeps the display character the big KPI
   numbers have; the body text around them is Inter for legibility. */
QLabel#PageTitle {{
    font-family: {FONT_HEADING};
    font-size: 27px;
    font-weight: 600;
    color: {HEADING};
    border: none;
    background: transparent;
}}

QLabel#PanelTitle {{
    font-family: {FONT_HEADING};
    font-size: 17px;
    font-weight: 600;
    color: {HEADING};
    border: none;
    background: transparent;
}}

QFrame#PanelDivider {{
    background: {BORDER};
    border: none;
    max-height: 1px;
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
/* Base look for any QPushButton that doesn't opt into a named/inline style —
   covers dialog OK/Cancel (QDialogButtonBox), Knowledge's tab action bars,
   and anything future pages add without remembering to style it by hand.
   Buttons with their own setStyleSheet() call are unaffected — a widget's
   own inline stylesheet always wins over this app-wide rule. */

QPushButton {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_MD}px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background: {PRIMARY_TINT};
    border-color: {PRIMARY};
    color: {PRIMARY_ACTIVE};
}}
QPushButton:pressed {{
    background: #D6E7F7;
}}
QPushButton:disabled {{
    color: {BORDER_STRONG};
    border-color: {BORDER};
    background: {BACKGROUND};
}}

/* Primary button (app-wide accent) */

QPushButton#PrimaryBtn {{
    background: {PRIMARY};
    color: white;
    border: none;
    border-radius: {R_MD}px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton#PrimaryBtn:hover   {{ background: {PRIMARY_HOVER}; }}
QPushButton#PrimaryBtn:pressed {{ background: {PRIMARY_ACTIVE}; }}
QPushButton#PrimaryBtn:disabled {{
    background: {BORDER_STRONG};
    color: {CARD};
}}

/* ── Tab widget ──────────────────────────────────────────────────────────── */

QTabWidget::pane {{
    background: {BACKGROUND};
    border: none;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 7px 14px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    color: {PRIMARY_ACTIVE};
    border-bottom: 2px solid {PRIMARY};
}}

/* ── Tables ──────────────────────────────────────────────────────────────── */

QTableWidget, QTableView {{
    background: {CARD};
    alternate-background-color: #F8FAFC;
    gridline-color: #EDF0F4;
    border: 1px solid {BORDER};
    border-radius: {R_MD}px;
    selection-background-color: {PRIMARY_TINT};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE_2};
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 6px 8px;
}}
QHeaderView::section:hover {{
    background: {PRIMARY_TINT};
    color: {PRIMARY_ACTIVE};
}}
QTableCornerButton::section {{
    background: {SURFACE_2};
    border: none;
    border-bottom: 1px solid {BORDER};
}}

/* ── Inputs ──────────────────────────────────────────────────────────────── */

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {CARD};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_MD}px;
    padding: 5px 8px;
    selection-background-color: {PRIMARY};
    selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {PRIMARY};
}}
QLineEdit:disabled, QComboBox:disabled {{
    background: {BACKGROUND};
    color: {TEXT_MUTED};
}}

QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_MD}px;
    padding: 5px 8px;
}}
QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_TINT};
    selection-color: {TEXT};
    outline: none;
}}

QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_SM}px;
    background: {CARD};
}}
QCheckBox::indicator:hover {{
    border-color: {PRIMARY};
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

/* ── Progress bars ───────────────────────────────────────────────────────── */

QProgressBar {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: {R_MD}px;
    text-align: center;
    color: {TEXT};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: {PRIMARY};
    border-radius: {R_SM}px;
}}

/* ── Group boxes ─────────────────────────────────────────────────────────── */

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
    margin-top: 10px;
    background: {CARD};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_MUTED};
}}

"""
