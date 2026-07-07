from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from desktop.widgets.info_icon import info_icon


class StatCard(QFrame):
    """
    Shared KPI card: title (+ optional info icon), value, optional subtitle.

    The `expanding`/`spacing`/`margins`/`always_show_subtitle` knobs exist
    because several pages (visibility, intelligence, trends) each grew their
    own near-identical copy of this widget with slightly different layout
    tuning before this class existed anywhere but home_page.py — consolidating
    them means reproducing each page's exact prior layout via these
    parameters rather than forcing one rigid shape on every caller.
    """

    def __init__(self, title, value="-", subtitle="", info="",
                 expanding=False, spacing=None, margins=None,
                 always_show_subtitle=True):
        super().__init__()

        self.setObjectName("StatCard")
        if expanding:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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

        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("CardSubtitle")

        layout.addLayout(title_row)
        layout.addWidget(self.value)
        if always_show_subtitle or subtitle:
            layout.addWidget(self.subtitle)

        self.setLayout(layout)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_subtitle(self, text):
        self.subtitle.setText(text)

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
            "QLabel#CardSubtitle { color: #B45309; font-size: 12px; }" if low
            else ""  # revert to the app-wide CardSubtitle style
        )
        if self.subtitle.parent() is None or not self.subtitle.isVisibleTo(self):
            layout = self.layout()
            if layout is not None and layout.indexOf(self.subtitle) == -1:
                layout.addWidget(self.subtitle)
        self.subtitle.show()