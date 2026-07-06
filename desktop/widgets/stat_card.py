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