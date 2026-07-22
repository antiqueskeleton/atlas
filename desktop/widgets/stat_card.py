from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QSizePolicy, QVBoxLayout,
)

from desktop.theme.colors import (
    DANGER_INK, DANGER_TINT, SUCCESS_INK, SUCCESS_TINT,
    SURFACE_2, TEXT_MUTED, WARNING_INK,
)
from desktop.widgets.info_icon import info_icon


class StatCard(QFrame):
    """
    Shared KPI card: title (+ optional info icon), value, optional delta
    chip, optional subtitle.

    The `expanding`/`spacing`/`margins`/`always_show_subtitle` knobs exist
    because several pages (visibility, intelligence, trends) each grew their
    own near-identical copy of this widget with slightly different layout
    tuning before this class existed anywhere but home_page.py — consolidating
    them means reproducing each page's exact prior layout via these
    parameters rather than forcing one rigid shape on every caller.

    2026-07 redesign: the value renders in Barlow Condensed via the global
    #CardValue rule, the card carries the spec's single soft shadow
    (QGraphicsDropShadowEffect — QSS has no box-shadow), and set_delta()
    adds the "is this good, and which way is it moving" chip.
    """

    def __init__(self, title, value="-", subtitle="", info="",
                 expanding=False, spacing=None, margins=None,
                 always_show_subtitle=True):
        super().__init__()

        self.setObjectName("StatCard")
        if expanding:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # The spec's one-level card shadow (0 2px 4px rgba(20,32,50,.08)).
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(20, 32, 50, 20))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        if spacing is not None:
            layout.setSpacing(spacing)
        if margins is not None:
            layout.setContentsMargins(*margins)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        title_row.addWidget(self.title)
        if info:
            title_row.addWidget(info_icon(info))
        title_row.addStretch()

        self.value = QLabel(value)
        self.value.setObjectName("CardValue")

        # Delta chip — hidden until set_delta() gives it something to say.
        self.delta = QLabel("")
        self.delta.setObjectName("CardDelta")
        self.delta.hide()
        delta_row = QHBoxLayout()
        delta_row.setContentsMargins(0, 0, 0, 0)
        delta_row.addWidget(self.delta)
        delta_row.addStretch()

        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("CardSubtitle")

        layout.addLayout(title_row)
        layout.addWidget(self.value)
        layout.addLayout(delta_row)
        if always_show_subtitle or subtitle:
            layout.addWidget(self.subtitle)

        self.setLayout(layout)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_subtitle(self, text):
        self.subtitle.setText(text)

    def set_delta(self, text: str, good: bool | None = None):
        """Show the movement chip: "▲ +4.2 pts" etc. `good` colors it —
        True success, False danger, None neutral. Empty text hides it.
        Semantic color is used strictly for state, per the redesign spec."""
        if not text:
            self.delta.hide()
            return
        tint, ink = {
            True:  (SUCCESS_TINT, SUCCESS_INK),
            False: (DANGER_TINT, DANGER_INK),
            None:  (SURFACE_2, TEXT_MUTED),
        }[good]
        self.delta.setText(text)
        self.delta.setStyleSheet(
            f"QLabel#CardDelta {{ background: {tint}; color: {ink};"
            f" border-radius: 3px; padding: 1px 6px;"
            f" font-size: 11px; font-weight: 600; }}"
        )
        self.delta.show()

    # Below ~30 responses, a rate KPI is mostly noise — the tile stays
    # readable but its provenance line turns amber so a thin sample can't
    # masquerade as a solid number (#88).
    LOW_SAMPLE_THRESHOLD = 30

    def set_provenance(self, n: int, as_of: str = "", unit: str = "responses"):
        """
        Stamp the card with what its number is computed FROM (#88/#100):
        sample size and as-of date. A number without "out of how many" and
        "when" isn't a fact — every headline KPI should carry both.
        Forces the subtitle visible even on cards built with
        always_show_subtitle=False, because provenance is the one subtitle
        that must never be hidden.
        """
        parts = [f"n = {n:,} {unit}"]
        if as_of:
            parts.append(f"as of {as_of}")
        low = n < self.LOW_SAMPLE_THRESHOLD
        if low:
            parts.append("small sample — treat as directional")
        self.subtitle.setText("  ·  ".join(parts))
        self.subtitle.setStyleSheet(
            f"QLabel#CardSubtitle {{ color: {WARNING_INK}; font-size: 12px; }}"
            if low else ""  # revert to the app-wide CardSubtitle style
        )
        if self.subtitle.parent() is None or not self.subtitle.isVisibleTo(self):
            layout = self.layout()
            if layout is not None and layout.indexOf(self.subtitle) == -1:
                layout.addWidget(self.subtitle)
        self.subtitle.show()
