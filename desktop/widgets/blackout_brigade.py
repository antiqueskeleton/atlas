"""
Blackout Brigade — the hidden generator-response game behind the © in
About Atlas (replaces the earlier "Keep the Lights On" reaction toy).

A storm has knocked out a neighborhood. You run the generator-response
truck: match the right generator to each location's load, powering as
much of the grid as you can before utility service returns — while the
heart of the game, the starting-watts-vs-running-watts overload mechanic,
punishes an undersized unit the instant a motor tries to spin up.

Design notes:
  - One PySide6 widget, no second window / no extra dependency, so it
    packages inside Atlas's PyInstaller bundle unchanged.
  - Game LOGIC (load math, fuel, scoring) is pure module-level functions
    and dataclasses with no Qt imports, so it's unit-testable headless —
    the rendering widget only ever calls into them.
  - Data is inline dataclasses, not JSON assets: an easter egg shouldn't
    add packaged data files. Wiring in real Atlas product specs later is
    a deliberate future step, not MVP scope.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QFont, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

# ── Palette (self-contained dark "stormy" theme) ──────────────────────────────
_BG        = "#0F172A"   # slate-900
_PANEL     = "#1E293B"   # slate-800
_PANEL_HI  = "#334155"   # slate-700
_TEXT      = "#E2E8F0"
_MUTED     = "#94A3B8"
_AMBER     = "#F59E0B"
_RED       = "#DC2626"
_YELLOW    = "#FBBF24"
_GREEN     = "#16A34A"
_BLUE      = "#0B84FF"
_GOLD      = "#EAB308"

_BEST_KEY  = "blackout_brigade_best"
_PLAYS_KEY = "blackout_brigade_plays"

_STORM_SECONDS = 180        # 3-minute round
_START_ACTIVE  = 3          # locations already requesting at kickoff
_SPAWN_EVERY   = (14, 22)   # seconds between new requests
_DEADLINE      = (45, 80)   # seconds a request stays open


# ── Pure data ─────────────────────────────────────────────────────────────────

@dataclass
class Appliance:
    name: str
    run: int
    start: int
    priority: int      # 1 low … 5 critical
    active: bool = False


@dataclass
class Generator:
    name: str
    run_cap: int
    start_cap: int
    fuel_cap: float
    fuel: float
    noise: int          # dB — lower is quieter (inverter perk)
    inverter: bool = False
    golden: bool = False
    assigned_to: int | None = None   # Location index, or None (in the truck)

    @property
    def out_of_fuel(self) -> bool:
        return self.fuel <= 0 and not self.golden


@dataclass
class Location:
    name: str
    kind: str
    priority: int                 # 1 low … 5 critical
    appliances: list[Appliance]
    deadline: float               # storm-clock second the request expires
    restore_at: float             # storm-clock second utility power returns
    gen_index: int | None = None
    powered: bool = False
    expired: bool = False
    restored: bool = False
    scored: bool = False
    noise_sensitive: bool = False


# Four generator classes for the MVP (doc §5, first four rungs).
_GEN_CLASSES = [
    dict(name="Compact Inverter",  run_cap=1600,  start_cap=2000,  fuel_cap=1.0,  noise=52, inverter=True),
    dict(name="Mid-Size Inverter", run_cap=3000,  start_cap=3500,  fuel_cap=2.0,  noise=57, inverter=True),
    dict(name="Standard Portable", run_cap=5500,  start_cap=7000,  fuel_cap=4.0,  noise=72),
    dict(name="Dual-Fuel Portable", run_cap=7500, start_cap=9400,  fuel_cap=6.0,  noise=74),
]

# Appliance pool (doc §3/§6). start == run for resistive/electronic loads;
# motor loads carry the big surge that makes sizing matter.
_APPLIANCES = [
    ("Refrigerator",       700, 1800, 3),
    ("Chest Freezer",      500, 1500, 3),
    ("Sump Pump",         1000, 2200, 5),
    ("Well Pump",         1200, 2400, 5),
    ("Window AC",          900, 2100, 4),
    ("Furnace Blower",     800, 1600, 4),
    ("Medical Equipment",  400,  600, 5),
    ("Lights",             300,  300, 2),
    ("Phone Chargers",      60,   60, 2),
    ("Television",         200,  200, 1),
    ("Microwave",         1500, 1500, 2),
    ("Space Heater",      1500, 1500, 2),
]
_AP = {a[0]: a for a in _APPLIANCES}


def _appl(name: str) -> Appliance:
    n, run, start, pri = _AP[name]
    return Appliance(n, run, start, pri)


# Location templates: (name, kind, priority, [appliance names], noise_sensitive)
_LOCATIONS = [
    ("Maple St. House",   "Home",     3, ["Refrigerator", "Lights", "Television"], False),
    ("Elder Care Flat",   "Medical",  5, ["Medical Equipment", "Lights", "Refrigerator"], False),
    ("Rosa's Food Truck", "Business", 2, ["Refrigerator", "Microwave", "Lights"], False),
    ("Elm Ave. Shelter",  "Shelter",  4, ["Lights", "Phone Chargers", "Space Heater"], True),
    ("Corner Market",     "Retail",   3, ["Refrigerator", "Chest Freezer", "Lights"], False),
    ("Flooded Basement",  "Critical", 5, ["Sump Pump", "Well Pump"], False),
    ("Oak Hill House",    "Home",     3, ["Furnace Blower", "Lights", "Refrigerator"], False),
    ("Charging Point",    "Community", 2, ["Phone Chargers", "Lights", "Television"], True),
    ("Pine St. Duplex",   "Home",     4, ["Window AC", "Refrigerator", "Lights"], False),
]


# ── Pure logic (no Qt — unit-tested headless) ─────────────────────────────────

def load_stats(appliances: list[Appliance]) -> tuple[int, int]:
    """(steady running watts, worst-case starting surge) for the ACTIVE set.

    The surge is the peak instantaneous demand as each motor spins up: the
    others' running draw plus that appliance's starting draw, maximized over
    the set. This is the whole educational point — a set can sit fine at
    steady state yet overload the moment the fridge kicks in.
    """
    active = [a for a in appliances if a.active]
    running = sum(a.run for a in active)
    surge = 0
    for a in active:
        surge = max(surge, (running - a.run) + a.start)
    return running, surge


def overload_reason(appliances: list[Appliance], gen: Generator) -> str:
    """"" if the set fits the generator, else a short human reason."""
    running, surge = load_stats(appliances)
    if running > gen.run_cap:
        return f"Running load {running:,} W exceeds {gen.run_cap:,} W capacity"
    if surge > gen.start_cap:
        return f"Startup surge {surge:,} W exceeds {gen.start_cap:,} W peak"
    return ""


def reserve_fraction(appliances: list[Appliance], gen: Generator) -> float:
    running, _ = load_stats(appliances)
    if gen.run_cap <= 0:
        return 0.0
    return max(0.0, 1.0 - running / gen.run_cap)


def fuel_burn_per_sec(appliances: list[Appliance], gen: Generator) -> float:
    """Doc §6: burn scales 0.35→1.0 of base with load. Base sized so a
    well-loaded unit lasts roughly base_cap × ~90s of game time."""
    if gen.golden:
        return 0.0
    running, _ = load_stats(appliances)
    load_pct = min(1.0, running / gen.run_cap) if gen.run_cap else 0.0
    base = gen.fuel_cap / 90.0      # ~90s at full tank, full load
    return base * (0.35 + 0.65 * load_pct)


def rank_for(score: int) -> str:
    for threshold, name in (
        (10000, "Blackout Commander"),
        (7500, "Storm Specialist"),
        (5000, "Generator Operator"),
        (2500, "Watt Wrangler"),
    ):
        if score >= threshold:
            return name
    return "Extension Cord Trainee"


def build_round(rng: random.Random) -> tuple[list[Generator], list[Location], int]:
    """Fresh randomized fleet + neighborhood. Pure — takes a seeded RNG so a
    storm seed replays identically. Returns (generators, locations, fuel_cans)."""
    fleet = [
        Generator(**_GEN_CLASSES[0], fuel=_GEN_CLASSES[0]["fuel_cap"]),
        Generator(**_GEN_CLASSES[1], fuel=_GEN_CLASSES[1]["fuel_cap"]),
        Generator(**_GEN_CLASSES[1], fuel=_GEN_CLASSES[1]["fuel_cap"]),
        Generator(**_GEN_CLASSES[2], fuel=_GEN_CLASSES[2]["fuel_cap"]),
        Generator(**_GEN_CLASSES[3], fuel=_GEN_CLASSES[3]["fuel_cap"]),
    ]
    # 1-in-25 rare golden generator with unlimited fuel (doc §13).
    if rng.random() < 0.04:
        fleet.append(Generator(name="✨ Golden Generator", run_cap=9000,
                               start_cap=12000, fuel_cap=99, fuel=99,
                               noise=48, inverter=True, golden=True))

    templates = _LOCATIONS[:]
    rng.shuffle(templates)
    chosen = templates[:min(8, len(templates))]
    locations: list[Location] = []
    for i, (name, kind, pri, appl_names, quiet) in enumerate(chosen):
        appls = [_appl(n) for n in appl_names]
        # Staggered requests: first few live immediately, the rest arrive later.
        if i < _START_ACTIVE:
            appear = 0.0
        else:
            appear = _START_ACTIVE * 0.0 + rng.uniform(*_SPAWN_EVERY) * (i - _START_ACTIVE + 1)
        deadline = min(_STORM_SECONDS - 5, appear + rng.uniform(*_DEADLINE))
        restore = rng.uniform(deadline + 15, _STORM_SECONDS + 40)
        loc = Location(name=name, kind=kind, priority=pri, appliances=appls,
                       deadline=deadline, restore_at=restore,
                       noise_sensitive=quiet)
        loc._appear = appear   # dynamic attr; only the widget reads it
        locations.append(loc)

    fuel_cans = 6
    return fleet, locations, fuel_cans


# ── Load meter widget ─────────────────────────────────────────────────────────

class _LoadMeter(QWidget):
    """Running fill + a startup-surge marker against the generator's two
    capacity lines — the visual that teaches running vs starting watts."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(78)
        self.running = 0
        self.surge = 0
        self.run_cap = 0
        self.start_cap = 0

    def set_values(self, running, surge, run_cap, start_cap):
        self.running, self.surge = running, surge
        self.run_cap, self.start_cap = run_cap, start_cap
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), 26
        y = 6
        scale_max = max(self.start_cap, self.surge, 1) * 1.05

        def x_of(watts):
            return int(w * min(1.0, watts / scale_max))

        # Track
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(_PANEL_HI))
        p.drawRoundedRect(0, y, w, h, 5, 5)

        # Running fill — green under capacity, red over
        over = self.running > self.run_cap or self.surge > self.start_cap
        p.setBrush(QColor(_RED if over else _GREEN))
        p.drawRoundedRect(0, y, x_of(self.running), h, 5, 5)

        # Startup surge ghost (amber, semi-transparent) beyond running fill
        if self.surge > self.running:
            p.setBrush(QColor(245, 158, 11, 150))
            p.drawRect(x_of(self.running), y, x_of(self.surge) - x_of(self.running), h)

        # Capacity lines: running cap (white) and start cap (blue dashed)
        for cap, color, dash in ((self.run_cap, QColor("#FFFFFF"), False),
                                 (self.start_cap, QColor(_BLUE), True)):
            if cap <= 0:
                continue
            x = x_of(cap)
            pen = QPen(color, 2)
            if dash:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(x, y - 2, x, y + h + 2)

        # Labels — two lines, both left-aligned, so long numbers never
        # collide the way a left/right pair did.
        p.setFont(QFont("Inter", 8))
        over = self.running > self.run_cap or self.surge > self.start_cap
        p.setPen(QColor(_RED if over else _TEXT))
        p.drawText(QRect(0, y + h + 2, w, 14), Qt.AlignLeft,
                   f"Load  {self.running:,} W running  ·  {self.surge:,} W startup surge")
        p.setPen(QColor(_MUTED))
        p.drawText(QRect(0, y + h + 16, w, 14), Qt.AlignLeft,
                   f"Generator  {self.run_cap:,} W capacity  ·  {self.start_cap:,} W peak")
        p.end()


# ── Map widget ────────────────────────────────────────────────────────────────

class _MapWidget(QWidget):
    location_clicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(430, 380)
        self._locs: list[Location] = []
        self._now = 0.0
        self._selected = -1
        self._tiles: list[tuple[QRect, int]] = []
        self._flash = 0

    def set_state(self, locs, now, selected, flash):
        self._locs, self._now, self._selected, self._flash = locs, now, selected, flash
        self.update()

    def mousePressEvent(self, e):
        for rect, idx in self._tiles:
            if rect.contains(e.position().toPoint()):
                self.location_clicked.emit(idx)
                return

    def _tile_color(self, loc: Location) -> QColor:
        if loc.restored:
            return QColor(_GREEN)
        if loc.expired:
            return QColor("#450A0A")
        if loc.powered:
            return QColor(_YELLOW)
        if getattr(loc, "_appear", 0) > self._now:
            return QColor("#1E293B")          # not requesting yet
        return QColor(_RED if loc.priority >= 5 else _AMBER)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(_BG))
        # occasional lightning wash
        if self._flash:
            p.fillRect(self.rect(), QColor(255, 255, 255, 30))

        visible = [(i, l) for i, l in enumerate(self._locs)]
        if not visible:
            return
        cols = 3
        rows = (len(visible) + cols - 1) // cols
        pad = 12
        cw = (self.width() - pad * (cols + 1)) // cols
        ch = (self.height() - pad * (rows + 1)) // rows
        self._tiles = []
        for slot, (idx, loc) in enumerate(visible):
            r, c = divmod(slot, cols)
            x = pad + c * (cw + pad)
            y = pad + r * (ch + pad)
            rect = QRect(x, y, cw, ch)
            self._tiles.append((rect, idx))

            not_live = getattr(loc, "_appear", 0) > self._now
            color = self._tile_color(loc)
            p.setBrush(color)
            pen = QPen(QColor(_BLUE if idx == self._selected else "#0F172A"),
                       3 if idx == self._selected else 1)
            p.setPen(pen)
            p.drawRoundedRect(rect, 8, 8)

            dark = loc.powered or loc.restored
            p.setPen(QColor("#0F172A") if dark else QColor(_TEXT if not not_live else _MUTED))
            p.setFont(QFont("Inter", 9, QFont.Bold))
            p.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.TextWordWrap,
                       loc.name if not not_live else "· · ·")

            p.setFont(QFont("Inter", 8))
            if not_live:
                tag = "incoming"
            elif loc.restored:
                tag = "utility restored"
            elif loc.expired:
                tag = "request missed"
            elif loc.powered:
                tag = "POWERED"
            else:
                left = max(0, int(loc.deadline - self._now))
                tag = f"{loc.kind} · {left}s left"
            p.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignBottom | Qt.AlignLeft, tag)
        p.end()


# ── Main dialog ───────────────────────────────────────────────────────────────

class BlackoutBrigadeDialog(QDialog):
    def __init__(self, parent=None, config_service=None, seed: int | None = None):
        super().__init__(parent)
        self._config = config_service
        self.setWindowTitle("Blackout Brigade")
        self.setFixedSize(1040, 700)
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        self._seed = seed if seed is not None else random.randrange(1, 99_999_999)
        self._rng = random.Random(self._seed)
        self.fleet, self.locations, self.fuel_cans = build_round(self._rng)

        self._elapsed = 0.0
        self._score = 0
        self._selected = -1
        self._sel_gen = -1
        self._flash = 0
        self._missed_critical = 0
        self._overload_free = True
        self._running = True
        self._ended = False

        self._build_ui()
        self._show_intro()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top status bar
        self._topbar = QLabel()
        self._topbar.setStyleSheet(
            f"background: {_PANEL}; color: {_TEXT}; font-size: 13px; "
            "font-weight: 600; padding: 10px 16px;")
        root.addWidget(self._topbar)

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 8)
        body.setSpacing(12)

        # Left: fleet
        fleet_wrap = QWidget()
        fleet_wrap.setFixedWidth(210)
        fl = QVBoxLayout(fleet_wrap)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)
        cap = QLabel("RESPONSE TRUCK")
        cap.setStyleSheet(f"color: {_MUTED}; font-size: 10px; font-weight: 700;")
        fl.addWidget(cap)
        self._fleet_box = QVBoxLayout()
        self._fleet_box.setSpacing(6)
        from PySide6.QtWidgets import QFrame
        fleet_scroll = QScrollArea()
        fleet_scroll.setWidgetResizable(True)
        fleet_scroll.setFrameShape(QFrame.NoFrame)
        fleet_scroll.setStyleSheet("background: transparent; border: none;")
        fw = QWidget()
        fw.setStyleSheet("background: transparent;")
        fw.setLayout(self._fleet_box)
        self._fleet_box.addStretch()
        fleet_scroll.setWidget(fw)
        fl.addWidget(fleet_scroll, 1)
        body.addWidget(fleet_wrap)

        # Center: map
        self._map = _MapWidget()
        self._map.location_clicked.connect(self._select_location)
        body.addWidget(self._map, 1)

        # Right: location detail
        detail = QWidget()
        detail.setFixedWidth(300)
        detail.setStyleSheet(f"background: {_PANEL}; border-radius: 8px;")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(14, 14, 14, 14)
        dl.setSpacing(8)
        self._loc_title = QLabel("Select a location on the map")
        self._loc_title.setStyleSheet(f"color: {_TEXT}; font-size: 15px; font-weight: 700;")
        self._loc_title.setWordWrap(True)
        self._loc_sub = QLabel("")
        self._loc_sub.setStyleSheet(f"color: {_MUTED}; font-size: 11px;")
        self._loc_sub.setWordWrap(True)
        dl.addWidget(self._loc_title)
        dl.addWidget(self._loc_sub)

        self._gen_combo = QComboBox()
        self._gen_combo.setStyleSheet(
            f"QComboBox {{ background: {_PANEL_HI}; color: {_TEXT}; border: none; "
            "border-radius: 5px; padding: 5px 8px; font-size: 12px; }}")
        self._gen_combo.currentIndexChanged.connect(self._on_gen_changed)
        dl.addWidget(self._gen_combo)

        self._appl_box = QVBoxLayout()
        self._appl_box.setSpacing(4)
        appl_wrap = QWidget()
        appl_wrap.setStyleSheet("background: transparent;")
        appl_wrap.setLayout(self._appl_box)
        dl.addWidget(appl_wrap)

        self._meter = _LoadMeter()
        dl.addWidget(self._meter)

        self._deploy_btn = QPushButton("Deploy")
        self._deploy_btn.setStyleSheet(self._btn_css(_GREEN))
        self._deploy_btn.clicked.connect(self._deploy)
        dl.addWidget(self._deploy_btn)

        self._refuel_btn = QPushButton("Refuel (F)")
        self._refuel_btn.setStyleSheet(self._btn_css(_PANEL_HI))
        self._refuel_btn.clicked.connect(self._refuel)
        dl.addWidget(self._refuel_btn)

        dl.addStretch()
        body.addWidget(detail)
        root.addLayout(body, 1)

        # Bottom: alert + controls
        bottom = QHBoxLayout()
        bottom.setContentsMargins(16, 0, 16, 12)
        self._alert = QLabel("Match a generator to each request. Watch the startup surge.")
        self._alert.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
        bottom.addWidget(self._alert, 1)
        quit_btn = QPushButton("Quit")
        quit_btn.setStyleSheet(self._btn_css(_PANEL_HI))
        quit_btn.clicked.connect(self.reject)
        bottom.addWidget(quit_btn)
        root.addLayout(bottom)

        # Intro overlay (dark flash) sits on top until the first tick.
        self._overlay = QLabel("UTILITY POWER LOST", self)
        self._overlay.setAlignment(Qt.AlignCenter)
        self._overlay.setGeometry(0, 0, 1040, 700)
        self._overlay.setStyleSheet(
            f"background: {_BG}; color: {_RED}; font-size: 34px; font-weight: 800; "
            "letter-spacing: 3px;")

        self._render_fleet()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    @staticmethod
    def _btn_css(bg: str) -> str:
        return (
            f"QPushButton {{ background: {bg}; color: white; border: none; "
            "border-radius: 6px; padding: 8px 14px; font-size: 12px; font-weight: 600; }}"
            "QPushButton:hover { background: #475569; }"
            "QPushButton:disabled { background: #475569; color: #94A3B8; }")

    def _show_intro(self):
        QTimer.singleShot(1100, self._start_game)

    def _start_game(self):
        self._overlay.hide()
        self._timer.start(100)   # 10 Hz logic

    # ── Fleet rendering ─────────────────────────────────────────────────────────

    def _render_fleet(self):
        while self._fleet_box.count() > 1:   # keep trailing stretch
            item = self._fleet_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for gi, gen in enumerate(self.fleet):
            card = QLabel()
            card.setTextFormat(Qt.RichText)
            busy = gen.assigned_to is not None
            fuel_pct = 100 if gen.golden else int(100 * gen.fuel / gen.fuel_cap) if gen.fuel_cap else 0
            fuel_color = _GREEN if fuel_pct > 40 else _AMBER if fuel_pct > 15 else _RED
            border = _GOLD if gen.golden else (_BLUE if busy else "#0F172A")
            state = ("assigned" if busy else "available")
            if gen.out_of_fuel:
                state = "OUT OF FUEL"
                fuel_color = _RED
            card.setText(
                f"<b style='color:{_GOLD if gen.golden else _TEXT}'>{gen.name}</b><br>"
                f"<span style='color:{_MUTED};font-size:10px'>"
                f"Run {gen.run_cap:,} · Peak {gen.start_cap:,}</span><br>"
                f"<span style='color:{fuel_color};font-size:10px'>"
                f"{'⛽ ∞' if gen.golden else f'⛽ {fuel_pct}%'} · {state}</span>")
            card.setStyleSheet(
                f"background: {_PANEL}; border: 1px solid {border}; "
                "border-radius: 6px; padding: 7px 9px;")
            card.setWordWrap(True)
            self._fleet_box.insertWidget(self._fleet_box.count() - 1, card)

    # ── Selection & detail panel ────────────────────────────────────────────────

    def _select_location(self, idx: int):
        loc = self.locations[idx]
        if getattr(loc, "_appear", 0) > self._elapsed and not loc.powered:
            self._alert.setText("That request hasn't come in yet — hold tight.")
            return
        self._selected = idx
        self._refresh_detail()

    def _refresh_detail(self):
        if self._selected < 0:
            return
        loc = self.locations[self._selected]
        crit = " · CRITICAL" if loc.priority >= 5 else ""
        quiet = " · quiet zone (inverter bonus)" if loc.noise_sensitive else ""
        self._loc_title.setText(loc.name)
        self._loc_sub.setText(f"{loc.kind}{crit}{quiet}")

        # Generator combo: unassigned units + this location's current one.
        self._gen_combo.blockSignals(True)
        self._gen_combo.clear()
        self._gen_combo.addItem("— choose a generator —", -1)
        for gi, gen in enumerate(self.fleet):
            if gen.assigned_to in (None, self._selected) and not gen.out_of_fuel:
                self._gen_combo.addItem(
                    f"{gen.name}  ({gen.run_cap:,}/{gen.start_cap:,} W)", gi)
        if loc.gen_index is not None:
            i = self._gen_combo.findData(loc.gen_index)
            if i >= 0:
                self._gen_combo.setCurrentIndex(i)
        self._gen_combo.blockSignals(False)

        # Appliance toggles
        while self._appl_box.count():
            item = self._appl_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        from PySide6.QtWidgets import QCheckBox
        self._appl_checks = []
        for a in loc.appliances:
            pr = {1: "low", 2: "med", 3: "high", 4: "high", 5: "CRIT"}[a.priority]
            cb = QCheckBox(f"{a.name}  ·  {a.run:,}/{a.start:,} W  ·  {pr}")
            cb.setChecked(a.active)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {_RED if a.priority>=5 else _TEXT}; font-size: 11px; }}")
            cb.stateChanged.connect(lambda _s, ap=a: self._toggle_appl(ap))
            self._appl_box.addWidget(cb)
            self._appl_checks.append(cb)

        self._update_meter()

    def _toggle_appl(self, ap: Appliance):
        ap.active = not ap.active
        self._update_meter()

    def _on_gen_changed(self, _i):
        self._update_meter()

    def _current_gen(self) -> Generator | None:
        gi = self._gen_combo.currentData()
        if gi is None or gi < 0:
            return None
        return self.fleet[gi]

    def _update_meter(self):
        if self._selected < 0:
            return
        loc = self.locations[self._selected]
        gen = self._current_gen()
        running, surge = load_stats(loc.appliances)
        if gen:
            self._meter.set_values(running, surge, gen.run_cap, gen.start_cap)
            reason = overload_reason(loc.appliances, gen)
            any_active = any(a.active for a in loc.appliances)
            self._deploy_btn.setEnabled(bool(gen) and any_active and not reason)
            self._deploy_btn.setText("Update" if loc.gen_index is not None else "Deploy")
            if reason:
                self._alert.setText(f"⚠ OVERLOAD — {reason}")
                self._alert.setStyleSheet(f"color: {_RED}; font-size: 12px;")
            else:
                res = int(reserve_fraction(loc.appliances, gen) * 100)
                self._alert.setText(f"Fits — {res}% reserve. Ready to deploy.")
                self._alert.setStyleSheet(f"color: {_GREEN}; font-size: 12px;")
        else:
            self._meter.set_values(running, surge, 0, 0)
            self._deploy_btn.setEnabled(False)

    # ── Deploy / refuel ─────────────────────────────────────────────────────────

    def _deploy(self):
        loc = self.locations[self._selected]
        gen = self._current_gen()
        if not gen:
            return
        reason = overload_reason(loc.appliances, gen)
        if reason:
            self._overload_free = False
            return
        # Free a previously-assigned generator at this location if swapping.
        if loc.gen_index is not None and loc.gen_index != self.fleet.index(gen):
            self.fleet[loc.gen_index].assigned_to = None
        gen.assigned_to = self._selected
        loc.gen_index = self.fleet.index(gen)
        loc.powered = True
        loc.expired = False
        if not loc.scored:
            self._score_power(loc, gen)
            loc.scored = True
        self._alert.setText(f"⚡ {loc.name} powered by {gen.name}.")
        self._alert.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
        self._render_fleet()
        self._refresh_detail()

    def _score_power(self, loc: Location, gen: Generator):
        gain = 500 if loc.priority >= 5 else 250
        # Time bonus for beating the deadline.
        left = max(0.0, loc.deadline - self._elapsed)
        gain += int(min(150, left * 2))
        # Sizing bonus: rewarding a snug fit, not a wildly oversized unit.
        res = reserve_fraction(loc.appliances, gen)
        if 0.10 <= res <= 0.35:
            gain += 100
        elif res >= 0.20:
            gain += 50
        # Inverter at a quiet zone.
        if loc.noise_sensitive and gen.inverter:
            gain += 75
        self._score += gain

    def _refuel(self):
        loc = self.locations[self._selected] if self._selected >= 0 else None
        if not loc or loc.gen_index is None:
            self._alert.setText("Select a powered location to refuel its generator.")
            return
        gen = self.fleet[loc.gen_index]
        if gen.golden:
            return
        if self.fuel_cans <= 0:
            self._alert.setText("Out of fuel cans!")
            self._alert.setStyleSheet(f"color: {_RED}; font-size: 12px;")
            return
        self.fuel_cans -= 1
        gen.fuel = gen.fuel_cap
        self._alert.setText(f"Refueled {gen.name}. {self.fuel_cans} cans left.")
        self._render_fleet()

    # ── Game tick ───────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._running:
            return
        self._elapsed += 0.1
        self._flash = 0
        if self._rng.random() < 0.012:
            self._flash = 1

        # Fuel + restoration + expiry, evaluated ~every tick but fuel/sec scaled.
        for i, loc in enumerate(self.locations):
            if loc.restored or loc.expired:
                continue
            # Utility power returns.
            if self._elapsed >= loc.restore_at:
                loc.restored = True
                if loc.gen_index is not None:
                    self.fleet[loc.gen_index].assigned_to = None
                    loc.gen_index = None
                if not loc.scored:      # restored before you got to it — neutral
                    loc.scored = True
                continue
            # Missed request.
            live = getattr(loc, "_appear", 0) <= self._elapsed
            if live and not loc.powered and self._elapsed >= loc.deadline:
                loc.expired = True
                if loc.priority >= 5:
                    self._score -= 500
                    self._missed_critical += 1
                else:
                    self._score -= 100

        # Fuel burn for deployed generators.
        for loc in self.locations:
            if loc.powered and loc.gen_index is not None:
                gen = self.fleet[loc.gen_index]
                gen.fuel = max(0.0, gen.fuel - fuel_burn_per_sec(loc.appliances, gen) * 0.1)
                if gen.out_of_fuel:
                    gen.assigned_to = None
                    loc.powered = False
                    loc.gen_index = None
                    self._score = max(0, self._score - 250)
                    self._alert.setText(f"⛽ {gen.name} ran dry — {loc.name} went dark!")
                    self._alert.setStyleSheet(f"color: {_RED}; font-size: 12px;")

        self._update_topbar()
        self._map.set_state(self.locations, self._elapsed, self._selected, self._flash)
        if self._selected >= 0:
            # keep fuel% fresh without rebuilding the whole panel every tick
            if int(self._elapsed * 10) % 10 == 0:
                self._render_fleet()

        done = all(l.restored or l.expired or l.powered for l in self.locations) \
            and not any(getattr(l, "_appear", 0) > self._elapsed and not l.expired
                        for l in self.locations)
        if self._elapsed >= _STORM_SECONDS or done:
            self._end_game()

    def _update_topbar(self):
        remaining = max(0, int(_STORM_SECONDS - self._elapsed))
        powered = sum(1 for l in self.locations if l.powered or l.restored)
        self._topbar.setText(
            f"⛈  STORM  {remaining // 60}:{remaining % 60:02d}      "
            f"SCORE  {self._score:,}      "
            f"POWERED  {powered}/{len(self.locations)}      "
            f"FUEL CANS  {self.fuel_cans}      "
            f"SEED  {self._seed}")

    # ── End & results ───────────────────────────────────────────────────────────

    def _end_game(self):
        if self._ended:
            return
        self._ended = True
        self._running = False
        self._timer.stop()

        # End bonuses.
        served = sum(1 for l in self.locations if l.scored and not l.expired)
        if self._missed_critical == 0:
            self._score += 500
        fuel_left = self.fuel_cans + sum(g.fuel for g in self.fleet if not g.golden)
        self._score += int(min(750, fuel_left * 40))
        self._score = max(0, self._score)

        best = self._config.get(_BEST_KEY, 0) if self._config else 0
        record = self._score > best
        if self._config:
            if record:
                self._config.set(_BEST_KEY, self._score)
            self._config.set(_PLAYS_KEY, (self._config.get(_PLAYS_KEY, 0) or 0) + 1)

        rank = rank_for(self._score)
        messages = [
            "Utility crews are asking if you're hiring.",
            "The neighborhood survived. Your circuit breaker needs a vacation.",
            "The lights came back on — the fuel budget needs a talk.",
            "Not bad. A few porch lights are still salty about it.",
        ]
        tier = 0 if self._score >= 6000 else 1 if self._score >= 3000 else 2 if self._score >= 1000 else 3
        crit_line = ("no critical requests missed" if self._missed_critical == 0
                     else f"{self._missed_critical} critical request(s) missed")

        overlay = QLabel(self)
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setAlignment(Qt.AlignCenter)
        overlay.setTextFormat(Qt.RichText)
        overlay.setStyleSheet(
            f"background: rgba(15,23,42,235); color: {_TEXT}; font-size: 15px;")
        overlay.setText(
            f"<div style='line-height:1.6'>"
            f"<div style='font-size:30px;font-weight:800;color:{_YELLOW}'>"
            f"POWER RESTORED</div><br>"
            f"<b style='font-size:22px'>{self._score:,} pts</b>"
            f"{'  <span style=\"color:'+_GREEN+'\">★ NEW BEST</span>' if record else ''}<br>"
            f"<span style='color:{_GOLD};font-size:17px'>{rank}</span><br><br>"
            f"<span style='color:{_MUTED}'>{served} locations served · {crit_line}<br>"
            f"best {max(best, self._score):,} · storm seed {self._seed}</span><br><br>"
            f"<i style='color:{_MUTED}'>{messages[tier]}</i><br><br>"
            f"<span style='color:{_MUTED};font-size:12px'>"
            f"Press <b>R</b> to run another storm · <b>Esc</b> to close</span>"
            f"</div>")
        overlay.show()
        self._results_overlay = overlay

    # ── Keyboard ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reject()
        elif e.key() == Qt.Key_F and not self._ended:
            self._refuel()
        elif e.key() == Qt.Key_R and self._ended:
            self.accept()
            new = BlackoutBrigadeDialog(self.parent(), self._config)
            new.exec()
        else:
            super().keyPressEvent(e)
