from PySide6.QtWidgets import QLabel, QComboBox, QVBoxLayout, QWidget


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app

        layout = QVBoxLayout()

        title = QLabel("Settings")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Configure Atlas providers and application preferences.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        provider_label = QLabel("AI Provider")
        provider_label.setStyleSheet("font-size:16px;font-weight:bold;")

        self.provider_select = QComboBox()
        self.provider_select.addItem("Mock AI Provider", "mock")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(provider_label)
        layout.addWidget(self.provider_select)
        layout.addStretch()

        self.setLayout(layout)