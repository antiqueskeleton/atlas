from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ActivityFeed(QFrame):
    def __init__(self, title="Recent Activity"):
        super().__init__()

        # 2026-07 redesign: Panel treatment — condensed header over a
        # hairline divider, matching home_page._status_card.
        self.setObjectName("Panel")

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(16, 12, 16, 14)

        heading = QLabel(title)
        heading.setObjectName("PanelTitle")

        divider = QFrame()
        divider.setObjectName("PanelDivider")
        divider.setFixedHeight(1)

        self.body = QLabel("No activity yet.")
        self.body.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(divider)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_items(self, items):
        self.body.setText("\n".join(f"• {item}" for item in items))
