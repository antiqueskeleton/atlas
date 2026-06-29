from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app

        root = QVBoxLayout()
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Configure your target brand and AI provider API keys.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        # ── Target brand ──────────────────────────────────────────────────────
        brand_card = self._card()
        brand_layout = QVBoxLayout()

        brand_heading = QLabel("Target Brand")
        brand_heading.setStyleSheet("font-size:16px;font-weight:bold;")

        brand_note = QLabel(
            "The brand Atlas measures visibility for. "
            "Used in analytics scores and KPI labels."
        )
        brand_note.setStyleSheet("color:#6B7280;font-size:13px;")
        brand_note.setWordWrap(True)

        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("e.g. Firman")
        self.brand_input.setText(self.app.config_service.get_target_brand())
        self.brand_input.setFixedWidth(260)

        brand_layout.addWidget(brand_heading)
        brand_layout.addWidget(brand_note)
        brand_layout.addSpacing(6)
        brand_layout.addWidget(self.brand_input)
        brand_card.setLayout(brand_layout)

        # ── Active provider ───────────────────────────────────────────────────
        provider_card = self._card()
        prov_layout = QVBoxLayout()

        prov_heading = QLabel("Active AI Provider")
        prov_heading.setStyleSheet("font-size:16px;font-weight:bold;")

        prov_note = QLabel(
            "The provider used for Investigation queries. "
            "Visibility runs let you choose a provider per run."
        )
        prov_note.setStyleSheet("color:#6B7280;font-size:13px;")
        prov_note.setWordWrap(True)

        self.provider_select = QComboBox()
        self.provider_select.setFixedWidth(260)
        for key in self.app.provider_manager.list_providers():
            p = self.app.provider_manager.registry.create_provider(key)
            self.provider_select.addItem(p.provider_name, key)

        active = self.app.provider_manager.active_provider_name
        for i in range(self.provider_select.count()):
            if self.provider_select.itemData(i) == active:
                self.provider_select.setCurrentIndex(i)
                break

        self.provider_select.currentIndexChanged.connect(self._change_active_provider)

        prov_layout.addWidget(prov_heading)
        prov_layout.addWidget(prov_note)
        prov_layout.addSpacing(6)
        prov_layout.addWidget(self.provider_select)
        provider_card.setLayout(prov_layout)

        # ── API keys ──────────────────────────────────────────────────────────
        keys_card = self._card()
        keys_layout = QVBoxLayout()
        keys_layout.setSpacing(10)

        keys_heading = QLabel("API Keys")
        keys_heading.setStyleSheet("font-size:16px;font-weight:bold;")

        keys_note = QLabel(
            "Keys are saved to your local user profile (AppData). "
            "They are never stored in the project files."
        )
        keys_note.setStyleSheet("color:#6B7280;font-size:13px;")
        keys_note.setWordWrap(True)

        keys_layout.addWidget(keys_heading)
        keys_layout.addWidget(keys_note)
        keys_layout.addSpacing(6)

        self._key_inputs = {}
        providers_meta = {
            "openai":     ("OpenAI",         "sk-..."),
            "anthropic":  ("Anthropic",       "sk-ant-..."),
            "gemini":     ("Google Gemini",   "AIza..."),
            "perplexity": ("Perplexity",      "pplx-..."),
            "grok":       ("Grok (xAI)",      "xai-..."),
            "mistral":    ("Mistral",         "..."),
        }

        form = QFormLayout()
        form.setSpacing(8)

        for key, (label, placeholder) in providers_meta.items():
            inp = QLineEdit()
            inp.setEchoMode(QLineEdit.Password)
            inp.setPlaceholderText(placeholder)
            inp.setFixedWidth(360)
            saved = self.app.config_service.get_api_key(key)
            if saved:
                inp.setText(saved)

            row = QHBoxLayout()
            row.addWidget(inp)

            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(60)
            test_btn.clicked.connect(lambda checked, k=key, i=inp: self._test_provider(k, i))
            row.addWidget(test_btn)

            row_widget = QWidget()
            row_widget.setLayout(row)

            lbl = QLabel(label)
            lbl.setFixedWidth(130)
            form.addRow(lbl, row_widget)

            self._key_inputs[key] = inp

        keys_layout.addLayout(form)
        keys_card.setLayout(keys_layout)

        # ── Save + status ─────────────────────────────────────────────────────
        save_btn = QPushButton("Save All Settings")
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self._save_all)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#6B7280;font-size:13px;")

        # ── Assemble ──────────────────────────────────────────────────────────
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(brand_card)
        root.addWidget(provider_card)
        root.addWidget(keys_card)
        root.addWidget(save_btn)
        root.addWidget(self.status)
        root.addStretch()

        self.setLayout(root)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _card(self):
        frame = QFrame()
        frame.setObjectName("StatCard")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return frame

    def _change_active_provider(self):
        key = self.provider_select.currentData()
        if key:
            self.app.provider_manager.set_active_provider(key)

    def _save_all(self):
        brand = self.brand_input.text().strip()
        self.app.config_service.set_target_brand(brand)

        for key, inp in self._key_inputs.items():
            api_key = inp.text().strip()
            self.app.provider_manager.set_provider_api_key(key, api_key)
            self.app.config_service.set_api_key(key, api_key)

        self.status.setText(
            f"Settings saved to {self.app.config_service.get_user_config_path()}"
        )

    def _test_provider(self, provider_key: str, key_input: QLineEdit):
        api_key = key_input.text().strip()
        if not api_key:
            self.status.setText(f"{provider_key}: no API key entered.")
            return

        self.app.provider_manager.set_provider_api_key(provider_key, api_key)
        self.app.provider_manager.set_active_provider(provider_key)

        provider = self.app.provider_manager.get_active_provider()
        self.status.setText(f"Testing {provider.provider_name}…")
        self.status.repaint()

        response = provider.ask("Reply with one sentence: confirm you are working.")
        self.status.setText(
            f"{provider.provider_name}: {response.executive_summary[:120]}"
        )
