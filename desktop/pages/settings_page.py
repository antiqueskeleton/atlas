from PySide6.QtWidgets import QLabel, QComboBox, QPushButton, QVBoxLayout, QWidget, QLineEdit


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
        self.load_providers()

        api_key_label = QLabel("API Key")
        api_key_label.setStyleSheet("font-size:16px;font-weight:bold;")

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter API key for selected provider")
        self.api_key_input.setEchoMode(QLineEdit.Password)

        self.status = QLabel("Provider status: Ready")
        self.status.setStyleSheet("font-size:13px;color:#6B7280;")

        save_button = QPushButton("Save Provider Settings")
        save_button.clicked.connect(self.save_provider_settings)

        test_button = QPushButton("Test Provider")
        test_button.clicked.connect(self.test_provider)

        self.provider_select.currentIndexChanged.connect(self.change_provider)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(provider_label)
        layout.addWidget(self.provider_select)
        layout.addSpacing(15)
        layout.addWidget(api_key_label)
        layout.addWidget(self.api_key_input)
        layout.addWidget(save_button)
        layout.addWidget(test_button)
        layout.addWidget(self.status)
        layout.addStretch()

        self.setLayout(layout)

    def load_providers(self):
        self.provider_select.clear()

        for provider_key in self.app.provider_manager.list_providers():
            provider = self.app.provider_manager.registry.create_provider(provider_key)
            self.provider_select.addItem(provider.provider_name, provider_key)

    def change_provider(self):
        provider_key = self.provider_select.currentData()

        if provider_key:
            self.app.provider_manager.set_active_provider(provider_key)
            provider = self.app.provider_manager.get_active_provider()
            self.status.setText(f"Provider status: {provider.provider_name} selected")

    def save_provider_settings(self):
        provider_key = self.provider_select.currentData()
        api_key = self.api_key_input.text().strip()

        self.app.provider_manager.set_provider_api_key(provider_key, api_key)

        self.status.setText("Provider status: Settings saved for current session")

    def test_provider(self):
        provider = self.app.provider_manager.get_active_provider()
        response = provider.ask("Test provider connection")

        self.status.setText(
            f"Provider status: {provider.provider_name} is working. "
            f"Confidence: {response.confidence}"
        )