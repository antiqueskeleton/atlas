from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from desktop.widgets.info_icon import info_icon


class StatCard(QFrame):

    def __init__(self, title, value="-", subtitle="", info=""):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

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
        layout.addWidget(self.subtitle)

        self.setLayout(layout)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_subtitle(self, text):
        self.subtitle.setText(text)