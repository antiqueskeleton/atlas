from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ProviderCard(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("AI Provider")
        title.setObjectName("CardTitle")

        self.name = QLabel("Mock AI Provider")
        self.name.setStyleSheet("font-size:18px;font-weight:bold;")

        self.details = QLabel("Development mode")
        self.details.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.name)
        layout.addWidget(self.details)

        self.setLayout(layout)

    def set_provider(self, provider_name):
        self.name.setText(provider_name)
        self.details.setText("Active reasoning provider")