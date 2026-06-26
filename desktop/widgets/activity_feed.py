from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ActivityFeed(QFrame):
    def __init__(self, title="Recent Activity"):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        heading = QLabel(title)
        heading.setObjectName("CardTitle")

        self.body = QLabel("No activity yet.")
        self.body.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_items(self, items):
        self.body.setText("\n".join(f"• {item}" for item in items))