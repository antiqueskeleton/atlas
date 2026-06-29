from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

# key -> (label, key_placeholder, default_model, model_hint, console_url)
_PROVIDERS = {
    "openai":     ("OpenAI",        "sk-...",     "gpt-4.1-mini",         "gpt-4.1 / gpt-4.1-mini / gpt-4o",            "platform.openai.com/api-keys"),
    "anthropic":  ("Anthropic",     "sk-ant-...", "claude-sonnet-4-6",    "claude-opus-4-8 / claude-sonnet-4-6",         "console.anthropic.com"),
    "gemini":     ("Google Gemini", "AIza...",    "gemini-2.0-flash-001", "gemini-2.0-flash-001 / gemini-2.5-flash",     "aistudio.google.com"),
    "perplexity": ("Perplexity",    "pplx-...",   "sonar",                "sonar / sonar-pro / sonar-reasoning",         "www.perplexity.ai/settings/api"),
    "grok":       ("Grok (xAI)",    "xai-...",    "grok-3",               "grok-3 / grok-3-mini",                        "console.x.ai"),
    "mistral":    ("Mistral",       "...",        "mistral-large-latest", "mistral-large-latest / mistral-small-latest", "console.mistral.ai"),
}

_CARD_SS = """
QFrame#SettingsCard {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
}
QFrame#SettingsCard QLabel { background: transparent; border: none; }
QFrame#SettingsCard QLineEdit {
    border: 1px solid #D1D5DB;
    border-radius: 4px;
    padding: 5px 9px;
    font-size: 13px;
    min-height: 28px;
    background: #FAFAFA;
}
QFrame#SettingsCard QLineEdit:focus { border-color: #2563EB; background: #FFF; }
QFrame#SettingsCard QPushButton {
    border: 1px solid #D1D5DB;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 12px;
    background: #F9FAFB;
    min-height: 28px;
}
QFrame#SettingsCard QPushButton:hover { background: #F3F4F6; border-color: #9CA3AF; }
QFrame#SettingsCard QPushButton:pressed { background: #E5E7EB; }
"""


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._key_inputs: dict[str, QLineEdit] = {}
        self._model_inputs: dict[str, QLineEdit] = {}
        self._show_btns: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        # ── Scroll area wraps everything ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        root = QVBoxLayout()
        root.setContentsMargins(4, 4, 12, 16)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        subtitle = QLabel("Configure your target brand, active AI provider, and API keys.")
        subtitle.setStyleSheet("font-size: 13px; color: #6B7280;")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self._brand_card())
        root.addWidget(self._provider_card())
        root.addWidget(self._keys_card())
        root.addStretch()

        content.setLayout(root)
        scroll.setWidget(content)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.setLayout(outer)

    # ── Cards ─────────────────────────────────────────────────────────────────

    def _brand_card(self) -> QFrame:
        card, lay = self._card("Target Brand")
        lay.addWidget(self._note(
            "The brand Atlas measures visibility for. "
            "Used in analytics scores and Firman KPI labels."
        ))
        lay.addSpacing(8)

        row = QHBoxLayout()
        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("e.g. Firman")
        self.brand_input.setText(self.app.config_service.get_target_brand())
        self.brand_input.setMaximumWidth(320)
        self.brand_input.setMinimumWidth(160)

        save_brand = QPushButton("Save")
        save_brand.setFixedWidth(70)
        save_brand.clicked.connect(self._save_brand)

        row.addWidget(self.brand_input)
        row.addWidget(save_brand)
        row.addStretch()
        lay.addLayout(row)
        return card

    def _provider_card(self) -> QFrame:
        card, lay = self._card("Active AI Provider")
        lay.addWidget(self._note(
            "Used for Investigation queries. "
            "Visibility and Intelligence runs let you choose per run."
        ))
        lay.addSpacing(8)

        row = QHBoxLayout()
        self.provider_select = QComboBox()
        self.provider_select.setMinimumWidth(200)
        self.provider_select.setMaximumWidth(280)
        for key in self.app.provider_manager.list_providers():
            p = self.app.provider_manager.registry.create_provider(key)
            self.provider_select.addItem(p.provider_name, key)

        active = self.app.provider_manager.active_provider_name
        for i in range(self.provider_select.count()):
            if self.provider_select.itemData(i) == active:
                self.provider_select.setCurrentIndex(i)
                break

        self.provider_select.currentIndexChanged.connect(self._change_active_provider)

        row.addWidget(self.provider_select)
        row.addStretch()
        lay.addLayout(row)
        return card

    def _keys_card(self) -> QFrame:
        card, lay = self._card("API Keys & Models")
        lay.addWidget(self._note(
            "Keys are saved to your local profile and never stored in the project. "
            "Override the Model field to pin a specific version."
        ))
        lay.addSpacing(10)

        # Column headers
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        for text, w, stretch in [
            ("Provider", 150, False),
            ("API Key", 0,   True),
            ("", 55,         False),
            ("Model", 230,   False),
            ("", 70,         False),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #9CA3AF;")
            if stretch:
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            else:
                lbl.setFixedWidth(w)
            hdr.addWidget(lbl)
        lay.addLayout(hdr)
        lay.addWidget(self._hsep())

        for key, (label, key_ph, default_model, model_hint, console_url) in _PROVIDERS.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            # Provider label + link
            prov_col = QVBoxLayout()
            prov_col.setSpacing(2)
            prov_col.setContentsMargins(0, 0, 0, 0)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #111827;")
            link_lbl = QLabel(f'<a href="https://{console_url}" style="color:#2563EB;text-decoration:none;font-size:11px;">Get key →</a>')
            link_lbl.setOpenExternalLinks(True)
            prov_col.addWidget(name_lbl)
            prov_col.addWidget(link_lbl)
            prov_widget = QWidget()
            prov_widget.setFixedWidth(150)
            prov_widget.setLayout(prov_col)
            row.addWidget(prov_widget)

            # API key field
            key_inp = QLineEdit()
            key_inp.setEchoMode(QLineEdit.Password)
            key_inp.setPlaceholderText(key_ph)
            key_inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            saved_key = self.app.config_service.get_api_key(key)
            if saved_key:
                key_inp.setText(saved_key)

            # Show / Hide toggle
            show_btn = QPushButton("Show")
            show_btn.setFixedWidth(55)
            show_btn.setCheckable(True)
            show_btn.toggled.connect(
                lambda on, f=key_inp, b=show_btn: (
                    f.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
                    b.setText("Hide" if on else "Show"),
                )
            )

            # Model field
            model_inp = QLineEdit()
            model_inp.setPlaceholderText(model_hint)
            model_inp.setFixedWidth(230)
            saved_model = self.app.config_service.get_model(key)
            model_inp.setText(saved_model or default_model)

            # Test button
            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(70)
            test_btn.clicked.connect(
                lambda checked, k=key, ki=key_inp, mi=model_inp: self._test_provider(k, ki, mi)
            )

            row.addWidget(key_inp)
            row.addWidget(show_btn)
            row.addWidget(model_inp)
            row.addWidget(test_btn)

            lay.addLayout(row)
            lay.addWidget(self._hsep())

            self._key_inputs[key] = key_inp
            self._model_inputs[key] = model_inp
            self._show_btns[key] = show_btn

        # Save row
        lay.addSpacing(4)
        save_row = QHBoxLayout()
        save_btn = QPushButton("Save All Settings")
        save_btn.setFixedWidth(180)
        save_btn.setStyleSheet(
            "QPushButton { background: #1D4ED8; color: white; border: none; "
            "border-radius: 4px; padding: 7px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #1E40AF; }"
            "QPushButton:pressed { background: #1E3A8A; }"
        )
        save_btn.clicked.connect(self._save_all)

        self.status = QLabel("")
        self.status.setStyleSheet("font-size: 12px; color: #6B7280;")
        self.status.setWordWrap(True)

        save_row.addWidget(save_btn)
        save_row.addWidget(self.status)
        save_row.addStretch()
        lay.addLayout(save_row)

        return card

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _card(self, heading: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("SettingsCard")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        frame.setStyleSheet(_CARD_SS)

        lay = QVBoxLayout()
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(6)

        hdr = QLabel(heading)
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #111827;")
        lay.addWidget(hdr)

        frame.setLayout(lay)
        return frame, lay

    def _note(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; color: #6B7280;")
        lbl.setWordWrap(True)
        return lbl

    def _hsep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #F3F4F6; border: none;")
        return sep

    # ── Actions ───────────────────────────────────────────────────────────────

    def _change_active_provider(self):
        key = self.provider_select.currentData()
        if key:
            self.app.provider_manager.set_active_provider(key)

    def _save_brand(self):
        brand = self.brand_input.text().strip()
        self.app.config_service.set_target_brand(brand)

    def _save_all(self):
        self._save_brand()

        for key, key_inp in self._key_inputs.items():
            api_key = key_inp.text().strip()
            model = self._model_inputs[key].text().strip()

            self.app.provider_manager.set_provider_api_key(key, api_key)
            self.app.config_service.set_api_key(key, api_key)

            self.app.provider_manager.set_provider_model(key, model)
            self.app.config_service.set_model(key, model)

        path = self.app.config_service.get_user_config_path()
        self.status.setText(f"Saved — {path}")

    def _test_provider(self, provider_key: str, key_input: QLineEdit, model_input: QLineEdit):
        api_key = key_input.text().strip()
        if not api_key:
            self.status.setText(f"No API key entered for {provider_key}.")
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
        self.status.setText(f"{label} [{provider.model}]: {response.executive_summary[:220]}")
