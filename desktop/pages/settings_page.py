from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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

# key -> (label, site_url_placeholder, setup_url)
_VOLUME_PROVIDERS = {
    "google_search_console": (
        "Google Search Console",
        "https://www.firmanpowerequipment.com/  or  sc-domain:firmanpowerequipment.com",
        "console.cloud.google.com",
    ),
}

# key -> (label, key_placeholder, default_model, model_hint, console_url)
_PROVIDERS = {
    "openai":     ("OpenAI",        "sk-...",     "gpt-4.1-mini",         "gpt-4.1 / gpt-4.1-mini / gpt-4o",            "platform.openai.com/api-keys"),
    "anthropic":  ("Anthropic",     "sk-ant-...", "claude-sonnet-4-6",    "claude-opus-4-8 / claude-sonnet-4-6",         "console.anthropic.com"),
    "gemini":     ("Google Gemini", "AIza...",    "gemini-2.0-flash-001", "gemini-2.0-flash-001 / gemini-2.5-flash",     "aistudio.google.com"),
    "perplexity": ("Perplexity",    "pplx-...",   "sonar",                "sonar / sonar-pro / sonar-reasoning",         "www.perplexity.ai/settings/api"),
    "grok":       ("Grok (xAI)",    "xai-...",    "grok-3",               "grok-3 / grok-3-mini",                        "console.x.ai"),
    "mistral":    ("Mistral",       "...",        "mistral-large-latest", "mistral-large-latest / mistral-small-latest", "console.mistral.ai"),
    "deepseek":   ("DeepSeek",      "sk-...",     "deepseek-chat",        "deepseek-chat / deepseek-reasoner",           "platform.deepseek.com"),
    "cohere":     ("Cohere",        "...",        "command-r-plus",       "command-r-plus / command-r / command-a-03-2025", "dashboard.cohere.com/api-keys"),
}

# Providers Atlas intends to add, but deliberately does NOT support yet (#62,
# 2026-07-05) because the actual consumer product has no public developer
# API — the only technical proxies available (Azure OpenAI for Copilot, a
# third-party Llama host for Meta AI) call a DIFFERENT underlying model than
# the real product, which would be a factual-accuracy problem in its own
# right (the exact kind of issue #77 already flagged elsewhere in Atlas).
# label -> why it's not buildable yet
_COMING_SOON_PROVIDERS = {
    "Microsoft Copilot": (
        "No public API for the Copilot consumer product. Azure OpenAI Service calls the "
        "same underlying GPT models Atlas already queries directly via OpenAI — it would not "
        "reflect Copilot's real Bing-grounded behavior, so Atlas isn't building a proxy for it."
    ),
    "Meta AI (Llama)": (
        "No direct developer API for the Meta AI consumer product. A third-party Llama host "
        "(Together.ai, Groq, etc.) only serves the base open-weight model — without whatever "
        "system prompt, fine-tuning, or live web-search grounding Meta applies to the real "
        "product, so Atlas isn't building a proxy for it."
    ),
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


class _TestWorker(QThread):
    result = Signal(str)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def run(self):
        try:
            resp = self.provider.ask("Reply with one sentence: confirm you are working.")
            self.result.emit(resp.executive_summary[:220])
        except Exception as exc:
            self.result.emit(f"Error: {exc}")


class _VolumeTestWorker(QThread):
    result = Signal(str)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def run(self):
        try:
            data = self.provider.get_query_volumes(days=90)
            if data["error"]:
                self.result.emit(f"Error: {data['error']}")
            else:
                self.result.emit(
                    f"Connected — retrieved {len(data['queries'])} queries from the last 90 days."
                )
        except Exception as exc:
            self.result.emit(f"Error: {exc}")


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._key_inputs: dict[str, QLineEdit] = {}
        self._model_inputs: dict[str, QLineEdit] = {}
        self._show_btns: dict[str, QPushButton] = {}
        self._test_workers: list = []
        self._volume_cred_inputs: dict[str, QLineEdit] = {}
        self._volume_site_inputs: dict[str, QLineEdit] = {}
        self._volume_test_workers: list = []
        self._platform_cred_inputs: dict[tuple[str, str], QLineEdit] = {}
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
        root.addWidget(self._coming_soon_card())
        root.addWidget(self._volume_providers_card())
        root.addWidget(self._platform_research_card())
        root.addWidget(self._health_card())
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
        self.brand_input.setToolTip(
            "This brand's mentions drive every KPI, chart, and briefing across the app — "
            "change it to analyze a different brand's AI visibility"
        )

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
        self.provider_select.setToolTip(
            "Default provider for Investigation queries — Visibility and Intelligence "
            "runs let you pick providers separately each time"
        )

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
            show_btn.setToolTip("Reveal or mask the API key text")

            # Model field
            model_inp = QLineEdit()
            model_inp.setPlaceholderText(model_hint)
            model_inp.setFixedWidth(230)
            saved_model = self.app.config_service.get_model(key)
            model_inp.setText(saved_model or default_model)
            model_inp.setToolTip("Pin a specific model version — leave as-is to use the default")

            # Test button
            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(70)
            test_btn.clicked.connect(
                lambda checked, k=key, ki=key_inp, mi=model_inp: self._test_provider(k, ki, mi)
            )
            test_btn.setToolTip("Send a small test request to verify this key and model work")

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
            "QPushButton { background: #0B84FF; color: white; border: none; "
            "border-radius: 5px; padding: 7px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #0056CC; }"
            "QPushButton:pressed { background: #004BB5; }"
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

    def _coming_soon_card(self) -> QFrame:
        card, lay = self._card("Coming Soon")
        lay.addWidget(self._note(
            "Providers Atlas plans to add once a real, direct public API for the actual "
            "consumer product exists — not shown as selectable providers yet, since the only "
            "technical workarounds available today would measure a different product than the "
            "one people actually use."
        ))
        lay.addSpacing(8)

        for label, reason in _COMING_SOON_PROVIDERS.items():
            row = QHBoxLayout()
            row.setSpacing(10)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #9CA3AF;")
            name_lbl.setFixedWidth(150)
            reason_lbl = self._note(reason)
            row.addWidget(name_lbl)
            row.addWidget(reason_lbl, 1)
            lay.addLayout(row)
            lay.addWidget(self._hsep())

        return card

    def _volume_providers_card(self) -> QFrame:
        card, lay = self._card("Keyword Volume Providers")
        lay.addWidget(self._note(
            "Real search-query volume, used to sanity-check the prompt library against "
            "genuine query demand (Knowledge → Prompt Sets). Configured the same way as "
            "AI providers above — add a credential, then Test."
        ))
        lay.addSpacing(10)

        for key, (label, site_ph, setup_url) in _VOLUME_PROVIDERS.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            name_col = QVBoxLayout()
            name_col.setSpacing(2)
            name_col.setContentsMargins(0, 0, 0, 0)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #111827;")
            link_lbl = QLabel(
                f'<a href="https://{setup_url}" style="color:#2563EB;text-decoration:none;'
                f'font-size:11px;">Set up →</a>'
            )
            link_lbl.setOpenExternalLinks(True)
            name_col.addWidget(name_lbl)
            name_col.addWidget(link_lbl)
            name_widget = QWidget()
            name_widget.setFixedWidth(150)
            name_widget.setLayout(name_col)
            row.addWidget(name_widget)

            cred_inp = QLineEdit()
            cred_inp.setPlaceholderText("Path to service-account JSON key…")
            cred_inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            saved_cred = self.app.config_service.get_volume_credential(key)
            if saved_cred:
                cred_inp.setText(saved_cred)
            cred_inp.setToolTip(
                "A Google Cloud service-account JSON key that has been added as a "
                "Restricted (read-only) user on this property in Search Console"
            )

            browse_btn = QPushButton("Browse…")
            browse_btn.setFixedWidth(75)
            browse_btn.clicked.connect(lambda _, ci=cred_inp: self._browse_volume_credential(ci))

            site_inp = QLineEdit()
            site_inp.setPlaceholderText(site_ph)
            site_inp.setFixedWidth(230)
            saved_site = self.app.config_service.get_volume_site_url(key)
            if saved_site:
                site_inp.setText(saved_site)
            site_inp.setToolTip(
                "The exact property identifier as it appears in Search Console — "
                "a URL-prefix property (https://example.com/) or a domain property (sc-domain:example.com)"
            )

            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(70)
            test_btn.clicked.connect(
                lambda checked, k=key, ci=cred_inp, si=site_inp: self._test_volume_provider(k, ci, si)
            )
            test_btn.setToolTip("Fetch a small sample of real query data to verify the credential and site URL work")

            row.addWidget(cred_inp)
            row.addWidget(browse_btn)
            row.addWidget(site_inp)
            row.addWidget(test_btn)

            lay.addLayout(row)
            lay.addWidget(self._hsep())

            self._volume_cred_inputs[key] = cred_inp
            self._volume_site_inputs[key] = site_inp

        lay.addSpacing(4)
        self.volume_status = QLabel("")
        self.volume_status.setStyleSheet("font-size: 12px; color: #6B7280;")
        self.volume_status.setWordWrap(True)
        lay.addWidget(self.volume_status)

        return card

    # ── Platform research card (Targeted Review, #25) ─────────────────────────

    # platform_key -> (display label, setup URL, note). Credential FIELDS come
    # from each provider's own credential_fields, so a future platform with
    # different fields renders correctly without touching this page.
    _RESEARCH_PLATFORMS = {
        "youtube": ("YouTube Data API",
                    "console.cloud.google.com/apis/library/youtube.googleapis.com",
                    "Free tier: 10,000 quota units/day (~50 brand collections)."),
        "reddit":  ("Reddit API",
                    "www.reddit.com/prefs/apps",
                    "Create a 'script' type app — no Reddit account password "
                    "is stored, only the app's ID and secret."),
        "editorial": ("Google Custom Search",
                      "programmablesearchengine.google.com/controlpanel/create",
                      "Create an engine set to 'search the entire web'. The API "
                      "key can be the SAME Google Cloud key as YouTube if the "
                      "Custom Search API is enabled on that project. Free tier: "
                      "100 queries/day (~2 collections at 6 brands)."),
    }

    def _platform_research_card(self) -> QFrame:
        from backend.targeted_review.targeted_review_service import PLATFORMS

        card, lay = self._card("Platform Research (Targeted Review)")
        lay.addWidget(self._note(
            "Credentials for the Targeted Review page's real platform data — "
            "YouTube content volume, Reddit conversation share, and editorial-"
            "site coverage per brand. Retail listings need no credential (they "
            "work from product URLs saved on the Targeted Review page)."
        ))
        lay.addSpacing(10)

        for key, (label, setup_url, note) in self._RESEARCH_PLATFORMS.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            name_col = QVBoxLayout()
            name_col.setSpacing(2)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #111827;")
            link_lbl = QLabel(
                f'<a href="https://{setup_url}" style="color:#2563EB;'
                f'text-decoration:none;font-size:11px;">Set up →</a>'
            )
            link_lbl.setOpenExternalLinks(True)
            name_col.addWidget(name_lbl)
            name_col.addWidget(link_lbl)
            name_widget = QWidget()
            name_widget.setFixedWidth(150)
            name_widget.setLayout(name_col)
            row.addWidget(name_widget)

            for field_key, field_label in PLATFORMS[key].credential_fields.items():
                inp = QLineEdit()
                inp.setPlaceholderText(field_label)
                inp.setEchoMode(QLineEdit.Password)
                inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                saved = self.app.config_service.get_platform_credential(key, field_key)
                if saved:
                    inp.setText(saved)
                inp.setToolTip(f"{label} — {field_label}. {note}")
                self._platform_cred_inputs[(key, field_key)] = inp
                row.addWidget(inp)

            lay.addLayout(row)
            lay.addWidget(self._hsep())

        lay.addSpacing(4)
        lay.addWidget(self._note(
            "Saved with the Save All button below, alongside AI provider keys."
        ))
        return card

    # ── Health card ───────────────────────────────────────────────────────────

    def _health_card(self) -> QFrame:
        card, lay = self._card("Health Check")
        lay.addWidget(self._note(
            "Sanity checks on your local database. No API calls are made."
        ))
        lay.addSpacing(6)

        refresh_btn = QPushButton("Run Health Check")
        refresh_btn.setFixedWidth(160)
        refresh_btn.clicked.connect(self._run_health_checks)
        refresh_btn.setToolTip("Verify database integrity and configuration — no API calls made")
        btn_row = QHBoxLayout()
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addSpacing(4)

        self._health_rows_widget = QWidget()
        self._health_rows_layout = QVBoxLayout()
        self._health_rows_layout.setSpacing(4)
        self._health_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._health_rows_widget.setLayout(self._health_rows_layout)
        lay.addWidget(self._health_rows_widget)

        # Run on first paint
        self._run_health_checks()
        return card

    def _run_health_checks(self):
        from backend.intelligence.intelligence_repository import IntelligenceRepository
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        from backend.visibility.visibility_repository import VisibilityRepository

        ir = IntelligenceRepository()
        kr = KnowledgeRepository()
        vr = VisibilityRepository()

        import os
        checks: list[tuple[str, str, str, str | None, str | None]] = []
        # (status, label, detail, action_label, action_key)

        # 0a — Target brand configured
        brand = self.app.config_service.get_target_brand()
        if not brand:
            checks.append(("red", "Target Brand", "No target brand set — configure it in the Target Brand card above.", None, None))
        else:
            checks.append(("green", "Target Brand", f"Tracking: {brand}", None, None))

        # 0b — At least one API key configured
        keys_set = sum(1 for k in _PROVIDERS if self.app.config_service.get_api_key(k))
        if keys_set == 0:
            checks.append(("red", "API Keys", "No API keys configured — add at least one provider key above.", None, None))
        else:
            checks.append(("green", "API Keys", f"{keys_set} of {len(_PROVIDERS)} providers configured.", None, None))

        # 1 — Stuck intelligence runs
        stuck = ir.get_stuck_runs(older_than_minutes=30)
        if stuck:
            checks.append((
                "red", "Stuck Runs",
                f"{len(stuck)} run(s) frozen in 'running' status — process crashed mid-run.",
                "Mark Failed", "mark_failed",
            ))
        else:
            checks.append(("green", "Intelligence Runs", "No stuck runs.", None, None))

        # 2 — Unparsed briefings
        unparsed = ir.get_unparsed_briefing_runs()
        if unparsed:
            checks.append((
                "amber", "Unparsed Opportunities",
                f"{len(unparsed)} briefing(s) have no structured opportunity rows (pre-date parser). "
                "Click Re-parse to extract them now — no API calls needed.",
                "Re-parse", "reparse_opps",
            ))
        else:
            checks.append(("green", "Opportunity Rows", "All briefings have parsed opportunity rows.", None, None))

        # 3 — Brands missing website
        import sqlite3
        from backend.services.paths import get_db_path
        with sqlite3.connect(get_db_path()) as conn:
            total_brands = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
            no_site = conn.execute(
                "SELECT COUNT(*) FROM brands WHERE website IS NULL OR website = ''"
            ).fetchone()[0]
        if no_site:
            checks.append((
                "amber", "Brands Missing Website",
                f"{no_site} of {total_brands} brands have no website — they will be skipped by web scraping.",
                None, None,
            ))
        else:
            checks.append(("green", "Brand Websites", f"All {total_brands} brands have a website.", None, None))

        # 4 — Web intelligence coverage
        with sqlite3.connect(get_db_path()) as conn:
            web_entries = conn.execute("SELECT COUNT(*) FROM web_intelligence").fetchone()[0]
            scraped = conn.execute(
                "SELECT COUNT(*) FROM web_intelligence WHERE scraped_at IS NOT NULL"
            ).fetchone()[0]
        if web_entries == 0:
            checks.append((
                "amber", "Web Intelligence",
                "No entries yet. Add brand domains on Knowledge → Web Intelligence, then Scrape All.",
                None, None,
            ))
        else:
            checks.append((
                "green" if scraped == web_entries else "amber",
                "Web Intelligence",
                f"{scraped} of {web_entries} entries scraped.",
                None, None,
            ))

        # 5 — Visibility data volume
        vis_stats = vr.count_stats()
        checks.append((
            "green" if vis_stats["total"] > 0 else "amber",
            "Visibility Data",
            f"{vis_stats['total']} responses · {vis_stats['runs']} runs · "
            f"{vis_stats['providers']} provider(s) · {vis_stats['families']} families.",
            None, None,
        ))

        # 6 — Intelligence briefings
        with sqlite3.connect(get_db_path()) as conn:
            briefing_count = conn.execute("SELECT COUNT(*) FROM intelligence_briefings").fetchone()[0]
            run_count      = conn.execute("SELECT COUNT(*) FROM intelligence_runs").fetchone()[0]
        checks.append((
            "green" if briefing_count > 0 else "amber",
            "Intelligence Briefings",
            f"{briefing_count} briefing(s) from {run_count} total run(s).",
            None, None,
        ))

        # 7 — Prompt library (CSV vs stale DB table)
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        families = kr.list_prompt_families()
        with sqlite3.connect(get_db_path()) as conn:
            db_fam = conn.execute("SELECT COUNT(*) FROM prompt_families").fetchone()[0]
        if db_fam > 0:
            checks.append((
                "amber", "Prompt Library",
                f"{len(families)} families in CSV (canonical). "
                f"{db_fam} stale rows remain in legacy prompt_families table — informational only.",
                None, None,
            ))
        else:
            checks.append(("green", "Prompt Library", f"{len(families)} families in CSV.", None, None))

        # 8 — Failed intelligence runs
        with sqlite3.connect(get_db_path()) as conn:
            failed_count = conn.execute(
                "SELECT COUNT(*) FROM intelligence_runs WHERE status = 'failed'"
            ).fetchone()[0]
        if failed_count > 0:
            checks.append(("amber", "Failed Runs", f"{failed_count} intelligence run(s) ended in failure — informational.", None, None))
        else:
            checks.append(("green", "Failed Runs", "No failed intelligence runs.", None, None))

        # 9 — Database file size
        db_path = get_db_path()
        db_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        checks.append(("green", "Database", f"{db_mb:.1f} MB on disk.", None, None))

        self._health_check_data = {"stuck": stuck, "unparsed": unparsed}
        self._render_health_rows(checks)

    def _render_health_rows(self, checks):
        # Clear existing rows
        while self._health_rows_layout.count():
            item = self._health_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        _COLORS = {"green": "#16A34A", "amber": "#D97706", "red": "#DC2626"}
        _DOTS   = {"green": "●", "amber": "●", "red": "●"}

        for status, label, detail, action_label, action_key in checks:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(10)

            dot = QLabel(_DOTS[status])
            dot.setFixedWidth(14)
            dot.setStyleSheet(f"color: {_COLORS[status]}; font-size: 14px;")

            name = QLabel(label)
            name.setFixedWidth(180)
            name.setStyleSheet("font-size: 12px; font-weight: bold; color: #111827;")

            desc = QLabel(detail)
            desc.setWordWrap(True)
            desc.setStyleSheet("font-size: 12px; color: #374151;")
            desc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            rl.addWidget(dot)
            rl.addWidget(name)
            rl.addWidget(desc)

            if action_label and action_key:
                btn = QPushButton(action_label)
                btn.setFixedWidth(90)
                btn.clicked.connect(lambda checked, k=action_key: self._health_action(k))
                rl.addWidget(btn)

            self._health_rows_layout.addWidget(row)

    def _health_action(self, key: str):
        from backend.intelligence.intelligence_repository import IntelligenceRepository
        from backend.intelligence.intelligence_service import IntelligenceService
        ir = IntelligenceRepository()

        if key == "mark_failed":
            stuck = self._health_check_data.get("stuck", [])
            for run_id, *_ in stuck:
                ir.mark_run_failed(run_id)
            self._run_health_checks()

        elif key == "reparse_opps":
            from PySide6.QtWidgets import QMessageBox
            unparsed = self._health_check_data.get("unparsed", [])
            count = 0
            errors = []
            for run_id, opp_text in unparsed:
                if not opp_text:
                    continue
                try:
                    parsed = IntelligenceService._parse_opportunities(opp_text)
                    if parsed:
                        ir.save_opportunities(run_id, parsed)
                        count += len(parsed)
                except Exception as exc:
                    errors.append(f"{run_id[:8]}: {exc}")
            self._run_health_checks()
            if errors:
                QMessageBox.warning(
                    self, "Re-parse Errors",
                    f"Saved {count} opportunit(y/ies). Errors:\n" + "\n".join(errors),
                )

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

        for key, cred_inp in self._volume_cred_inputs.items():
            credential = cred_inp.text().strip()
            site_url = self._volume_site_inputs[key].text().strip()

            self.app.volume_provider_manager.set_provider_credential(key, credential)
            self.app.config_service.set_volume_credential(key, credential)

            self.app.volume_provider_manager.set_provider_site_url(key, site_url)
            self.app.config_service.set_volume_site_url(key, site_url)

        for (platform, field), inp in self._platform_cred_inputs.items():
            self.app.config_service.set_platform_credential(
                platform, field, inp.text().strip())

        path = self.app.config_service.get_user_config_path()
        self.status.setText(f"Saved — {path}")

    def _browse_volume_credential(self, cred_input: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Service Account JSON Key", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            cred_input.setText(path)

    def _test_volume_provider(self, provider_key: str, cred_input: QLineEdit, site_input: QLineEdit):
        credential = cred_input.text().strip()
        site_url = site_input.text().strip()
        if not credential:
            self.volume_status.setText(f"No credential set for {provider_key}.")
            return
        if not site_url:
            self.volume_status.setText(f"No site URL set for {provider_key}.")
            return

        provider = self.app.volume_provider_manager.registry.create_provider(provider_key)
        provider.set_credential(credential)
        provider.set_site_url(site_url)

        label = _VOLUME_PROVIDERS.get(provider_key, (provider_key,))[0]
        self.volume_status.setText(f"Testing {label}…")

        worker = _VolumeTestWorker(provider)
        self._volume_test_workers.append(worker)
        worker.result.connect(
            lambda text, lbl=label: self.volume_status.setText(f"{lbl}: {text}")
        )
        worker.finished.connect(
            lambda w=worker: self._volume_test_workers.remove(w) if w in self._volume_test_workers else None
        )
        worker.start()

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

        worker = _TestWorker(provider)
        self._test_workers.append(worker)
        worker.result.connect(
            lambda text, lbl=label, mdl=provider.model: self.status.setText(f"{lbl} [{mdl}]: {text}")
        )
        worker.finished.connect(
            lambda w=worker: self._test_workers.remove(w) if w in self._test_workers else None
        )
        worker.start()
