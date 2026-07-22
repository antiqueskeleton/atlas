# Atlas design tokens — 2026-07 redesign ("Atlas, modernized" spec).
# Values come from the Claude Design token sheet (light theme). The legacy
# constant NAMES are kept so existing imports keep working; new tokens are
# additive. DARK below stores the spec's full dark set for a future
# theme toggle — nothing reads it yet.

# ── Chrome (nav rail, menus, splash) ─────────────────────────────────────
NAVY       = "#16324D"   # deep navy chrome — nav rail, menu bar
SLATE      = "#1E4266"   # nav hover / raised element on navy
STEEL      = "#56779B"   # muted elements on navy
SILVER     = "#A9BBCD"   # secondary text on navy
LIGHT      = "#F2F5F8"   # near-white text on navy

# ── Accent ───────────────────────────────────────────────────────────────
PRIMARY        = "#3E7BC2"   # electric steel blue — buttons, accents, selection
PRIMARY_HOVER  = "#336CAE"
PRIMARY_ACTIVE = "#295A94"
PRIMARY_TINT   = "#EAF2FB"   # selected-row / tinted-fill blue
SKY            = "#7FB0E3"   # light accent (sparklines, secondary emphasis)
ACCENT         = SKY         # legacy name
ACCENT_DK      = PRIMARY_HOVER  # legacy name

# ── Ground & surfaces ────────────────────────────────────────────────────
BACKGROUND    = "#EEF1F5"   # cool-gray page ground
CARD          = "#FFFFFF"   # panel / card surface
SURFACE_2     = "#F4F6F9"   # table headers, wells, subtle fills
BORDER        = "#E3E7ED"   # hairline panel border
BORDER_STRONG = "#CBD2DB"   # input / button border

# ── Semantic (state only, never decoration) ──────────────────────────────
SUCCESS       = "#2E8B5E"
SUCCESS_TINT  = "#E6F3EC"
SUCCESS_INK   = "#1F6B45"
WARNING       = "#B8791E"
WARNING_TINT  = "#FBF0DC"
WARNING_INK   = "#8A5A12"
DANGER        = "#C24536"
DANGER_TINT   = "#FBE9E6"
DANGER_INK    = "#97362A"
INFO          = PRIMARY
INFO_TINT     = PRIMARY_TINT
INFO_INK      = PRIMARY_ACTIVE

# ── Typography ───────────────────────────────────────────────────────────
TEXT       = "#2B323A"
TEXT_MUTED = "#69727E"
HEADING    = "#141A21"
# Hybrid pairing (2026-07): Barlow Condensed is a display face — great for
# big KPI numbers and page titles, but Barlow regular reads poorly as dense
# 13px UI text (narrow, low x-height, worse in Qt than in a browser). Inter
# is purpose-built for small screen UI, so body/table/label text uses it
# while headings keep the condensed character.
FONT_BODY    = '"Inter", "Segoe UI", Arial, sans-serif'
FONT_HEADING = '"Barlow Condensed", "Barlow", "Segoe UI", Arial, sans-serif'

# ── Shape ────────────────────────────────────────────────────────────────
R_SM, R_MD, R_LG = 3, 4, 6   # px — crisp, not rounded

# ── Heatmap ramp (light-blue → navy; flip text to white past index 4) ────
HEAT_RAMP = ["#EAF2FB", "#D6E7F7", "#B5D3EE", "#94BCE3", "#749DC4",
             "#597EA3", "#41617F", "#2C455D", "#16324D"]
HEAT_TEXT_FLIP = 5   # ramp index at/after which cell text renders white

# ── Dark theme token set (stored for a future toggle; unused today) ─────
DARK = {
    "BACKGROUND": "#0F141A", "CARD": "#171E27", "SURFACE_2": "#1E2732",
    "BORDER": "#29323E", "BORDER_STRONG": "#3A4552",
    "TEXT_MUTED": "#93A0AE", "TEXT": "#D6DCE4", "HEADING": "#F2F5F8",
    "NAVY": "#0B1A2A",
    "PRIMARY": "#5C97DE", "PRIMARY_HOVER": "#6EA6E8",
    "PRIMARY_ACTIVE": "#4A83C9", "PRIMARY_TINT": "#16283C", "SKY": "#8FBEEE",
    "SUCCESS": "#47B685", "SUCCESS_TINT": "#12251C", "SUCCESS_INK": "#7ED0A6",
    "WARNING": "#D99A34", "WARNING_TINT": "#2A2113", "WARNING_INK": "#E9B968",
    "DANGER": "#DE6152", "DANGER_TINT": "#2C1714", "DANGER_INK": "#EA8B7E",
    "INFO": "#5C97DE", "INFO_TINT": "#14263A", "INFO_INK": "#8FBEEE",
}
