"""
Keep the Lights On — a tiny reaction game hidden behind the (c) symbol in
About Atlas (click it, nothing announces it's there). Deliberately simple:
a draining power meter, one button to keep it topped up, occasional random
surges/brownouts for flavor. Best survival time persists via ConfigService
so it's worth coming back to beat.
"""
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

_TICK_MS = 150
_BASE_DRAIN = 2
_CLICK_BOOST = 14
_SURGE_CHANCE = 0.02
_BROWNOUT_CHANCE = 0.015
_BEST_KEY = "easter_egg_best_seconds"


class KeepTheLightsOnDialog(QDialog):
    def __init__(self, parent, config_service=None):
        super().__init__(parent)
        self._config = config_service
        self._power = 100
        self._seconds = 0
        self._running = True

        self.setWindowTitle("Keep the Lights On")
        self.setFixedSize(360, 320)

        title = QLabel("⚡ Keep the Lights On")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #111827;")

        self._sub = QLabel("The grid is failing — keep clicking the generator!")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet("font-size: 12px; color: #6B7280; min-height: 32px;")

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(18)
        self._set_bar_color("#16A34A")

        self._timer_lbl = QLabel("Survived: 0s")
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        self._timer_lbl.setStyleSheet("font-size: 13px; color: #374151; font-weight: 600;")

        best = self._config.get(_BEST_KEY, 0) if self._config else 0
        self._best_lbl = QLabel(f"Best: {best}s")
        self._best_lbl.setAlignment(Qt.AlignCenter)
        self._best_lbl.setStyleSheet("font-size: 11px; color: #9CA3AF;")

        self._btn = QPushButton("\U0001F50C  Generator")
        self._btn.setFixedHeight(64)
        self._btn.setStyleSheet(
            "QPushButton { background: #0B84FF; color: white; border: none; "
            "border-radius: 8px; font-size: 16px; font-weight: 700; }"
            "QPushButton:hover { background: #0056CC; }"
            "QPushButton:pressed { background: #003D99; }"
            "QPushButton:disabled { background: #9CA3AF; }"
        )
        self._btn.clicked.connect(self._on_click)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)

        lay = QVBoxLayout()
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)
        lay.addWidget(title)
        lay.addWidget(self._sub)
        lay.addSpacing(4)
        lay.addWidget(self._bar)
        lay.addWidget(self._timer_lbl)
        lay.addWidget(self._best_lbl)
        lay.addSpacing(4)
        lay.addWidget(self._btn)
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)
        self.setLayout(lay)

        self._drain_timer = QTimer(self)
        self._drain_timer.timeout.connect(self._tick)
        self._drain_timer.start(_TICK_MS)

        self._sec_timer = QTimer(self)
        self._sec_timer.timeout.connect(self._on_second)
        self._sec_timer.start(1000)

    def _set_bar_color(self, color: str):
        self._bar.setStyleSheet(
            "QProgressBar { border: 1px solid #D1D5DB; border-radius: 4px; "
            "background: #F3F4F6; }"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
        )

    def _tick(self):
        if not self._running:
            return
        # Drain accelerates the longer you survive — a flat rate made the
        # late game trivially easy to sustain forever.
        drain = _BASE_DRAIN + self._seconds // 8
        roll = random.random()
        if roll < _SURGE_CHANCE:
            self._power = min(100, self._power + 30)
            self._sub.setText("✨ Power surge! Free charge.")
        elif roll < _SURGE_CHANCE + _BROWNOUT_CHANCE:
            self._power = max(0, self._power - 25)
            self._sub.setText("⚠️ Brownout! Power dropping fast.")
        else:
            self._power = max(0, self._power - drain)
        self._bar.setValue(self._power)
        if self._power > 60:
            self._set_bar_color("#16A34A")
        elif self._power > 25:
            self._set_bar_color("#D97706")
        else:
            self._set_bar_color("#DC2626")
        if self._power <= 0:
            self._end_game()

    def _on_second(self):
        if not self._running:
            return
        self._seconds += 1
        self._timer_lbl.setText(f"Survived: {self._seconds}s")

    def _on_click(self):
        if not self._running:
            return
        self._power = min(100, self._power + _CLICK_BOOST)
        self._bar.setValue(self._power)

    def _end_game(self):
        self._running = False
        self._drain_timer.stop()
        self._sec_timer.stop()
        self._btn.setEnabled(False)
        best = self._config.get(_BEST_KEY, 0) if self._config else 0
        if self._seconds > best:
            if self._config:
                self._config.set(_BEST_KEY, self._seconds)
            self._best_lbl.setText(f"Best: {self._seconds}s — new record!")
            self._sub.setText(f"\U0001F4A1 Blackout after {self._seconds}s — new best!")
        else:
            self._sub.setText(f"\U0001F4A1 Blackout after {self._seconds}s. Best: {best}s")
