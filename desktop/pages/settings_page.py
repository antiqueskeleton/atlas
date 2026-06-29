from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# Provider display metadata: key -> (label, key_placeholder, default_model, model_hint)
_PROVIDERS = {
    "openai":     ("OpenAI",        "sk-...",      "gpt-4.1-mini",         "gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini"),
    "anthropic":  ("Anthropic",     "sk-ant-...",  "claude-sonnet-4-6",    "claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5-20251001"),
    "gemini":     ("Google Gemini", "AIza...",     "gemini-2.0-flash-001", "gemini-2.0-flash-001, gemini-2.5-flash, gemini-1.5-flash"),
    "perplexity": ("Perplexity",    "pplx-...",    "sonar",                "sonar, sonar-pro, sonar-reasoning"),
    "grok":       ("Grok (xAI)",    "xai-...",     "grok-3",               "grok-3, grok-3-mini, grok-3-fast"),
    "mistral":    ("Mistral",       "...",         "mistral-large-latest", "mistral-large-latest, mistral-small-latest"),
}


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._key_inputs: dict[str, QLineEdit] = {}
        self._model_inputs: dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Configure your target brand, active provider, and AI API keys.")
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
            "Visibility and Intelligence runs let you choose per run."
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

        # ── API keys + models ─────────────────────────────────────────────────
        keys_card = self._card()
        keys_layout = QVBoxLayout()
        keys_layout.setSpacing(10)

        keys_heading = QLabel("API Keys & Models")
        keys_heading.setStyleSheet("font-size:16px;font-weight:bold;")

        keys_note = QLabel(
            "Keys are saved to your local AppData profile and never stored in the project. "
            "Override the Model field if you need a different version."
        )
        keys_note.setStyleSheet("color:#6B7280;font-size:13px;")
        keys_note.setWordWrap(True)

        # Column headers
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        for text, width in [("Provider", 130), ("API Key", 300), ("Model", 220), ("", 70)]:
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size:12px;color:#6B7280;font-weight:bold;")
            lbl.setFixedWidth(width)
            header_row.addWidget(lbl)

        keys_layout.addWidget(keys_heading)
        keys_layout.addWidget(keys_note)
        keys_layout.addSpacing(4)
        keys_layout.addLayout(header_row)

        for key, (label, key_ph, default_model, model_hint) in _PROVIDERS.items():
            # API key
            key_inp = QLineEdit()
            key_inp.setEchoMode(QLineEdit.Password)
            key_inp.setPlaceholderText(key_ph)
            key_inp.setFixedWidth(300)
            saved_key = self.app.config_service.get_api_key(key)
            if saved_key:
                key_inp.setText(saved_key)

            # Model
            model_inp = QLineEdit()
            model_inp.setPlaceholderText(model_hint)
            model_inp.setFixedWidth(220)
            saved_model = self.app.config_service.get_model(key)
            model_inp.setText(saved_model or default_model)

            # Test button
            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(60)
            test_btn.clicked.connect(
                lambda checked, k=key, ki=key_inp, mi=model_inp: self._test_provider(k, ki, mi)
            )

            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setFixedWidth(130)
            row.addWidget(lbl)
            row.addWidget(key_inp)
            row.addWidget(model_inp)
            row.addWidget(test_btn)

            row_widget = QWidget()
            row_widget.setLayout(row)
            keys_layout.addWidget(row_widget)

            self._key_inputs[key] = key_inp
            self._model_inputs[key] = model_inp

        keys_card.setLayout(keys_layout)

        # ── Save + status ─────────────────────────────────────────────────────
        save_btn = QPushButton("Save All Settings")
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self._save_all)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#6B7280;font-size:13px;")
        self.status.setWordWrap(True)

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

        for key, key_inp in self._key_inputs.items():
            api_key = key_inp.text().strip()
            model = self._model_inputs[key].text().strip()

            self.app.provider_manager.set_provider_api_key(key, api_key)
            self.app.config_service.set_api_key(key, api_key)

            self.app.provider_manager.set_provider_model(key, model)
            self.app.config_service.set_model(key, model)

        self.status.setText(
            f"Saved to {self.app.config_service.get_user_config_path()}"
        )

    def _test_provider(self, provider_key: str, key_input: QLineEdit, model_input: QLineEdit):
        api_key = key_input.text().strip()
        if not api_key:
            self.status.setText(f"{provider_key}: no API key entered.")
            return

        provider = self.app.provider_manager.registry.create_provider(provider_key)
        provider.set_api_key(api_key)

        model = model_input.text().strip()
        if model:
            provider.set_model(model)

        label = _PROVIDERS.get(provider_key, (provider_key,))[0]
        self.status.setText(f"Testing {label} ({provider.model})…")
        self.status.repaint()

        response = provider.ask("Reply with one sentence: confirm you are working.")
        self.status.setText(f"{label} [{provider.model}]: {response.executive_summary[:200]}")
