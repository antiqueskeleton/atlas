from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from backend.knowledge.knowledge_repository import KnowledgeRepository

_PROVIDER_INFO = {
    "openai":     ("OpenAI",        "gpt-4.1-mini"),
    "anthropic":  ("Anthropic",     "claude-sonnet-4-6"),
    "gemini":     ("Google Gemini", "gemini-2.0-flash-001"),
    "perplexity": ("Perplexity",    "sonar"),
    "grok":       ("Grok (xAI)",    "grok-3"),
    "mistral":    ("Mistral",       "mistral-large-latest"),
    "deepseek":   ("DeepSeek",      "deepseek-chat"),
}

_BRAND_FIELDS = [
    ("Name *",         "name",           "text",  ""),
    ("Aliases",        "aliases",        "text",  ""),
    ("Product Types",  "product_types",  "text",  ""),
    ("Country",        "country",        "combo", ["US", "Canada", "Global", "Other"]),
    ("Parent Company", "parent_company", "text",  ""),
    ("Website",        "website",        "text",  ""),
    ("Active",         "active",         "check", True),
]
_FEATURE_FIELDS = [
    ("Name *",   "name",     "text", ""),
    ("Category", "category", "text", ""),
]
_PERSONA_FIELDS = [
    ("Name *",       "name",         "text",  ""),
    ("Priority",     "priority",     "combo", ["High", "Medium", "Low"]),
    ("Description",  "description",  "area",  ""),
    ("Primary Goal", "primary_goal", "area",  ""),
    ("Concerns",     "concerns",     "area",  ""),
]
_SCENARIO_FIELDS = [
    ("Name *",      "name",        "text", ""),
    ("Description", "description", "area", ""),
]
_STAGE_FIELDS = [
    ("Name *",      "name",        "text", ""),
    ("Description", "description", "area", ""),
    ("Sort Order",  "sort_order",  "spin", 99),
]
_FAMILY_FIELDS = [
    ("Family Name *", "family_name", "text", ""),
]
_PROMPT_FIELDS = [
    ("Prompt Style",          "style", "text", "question"),
    ("Prompt Text *",         "text",  "area", ""),
    ("Influence Score (1-10)","score", "spin", 5),
]


class _ScrapeWorker(QThread):
    """Scrapes each (entry_id, domain) pair sequentially and emits progress."""
    progress = Signal(int, int, str)   # current, total, brand_name
    done     = Signal(int, dict)       # entry_id, scrape_result
    finished_all = Signal()

    def __init__(self, entries: list):
        super().__init__()
        self._entries = entries  # list of (entry_id, brand_name, domain)

    def run(self):
        from backend.intelligence.web_scraper import scrape_domain
        total = len(self._entries)
        for idx, (entry_id, brand_name, domain) in enumerate(self._entries, 1):
            self.progress.emit(idx, total, brand_name)
            result = scrape_domain(domain)
            self.done.emit(entry_id, result)
        self.finished_all.emit()


class _BrandDiscoveryWorker(QThread):
    done  = Signal(list, list)   # all_brands, providers_queried
    error = Signal(str)

    def __init__(self, provider_manager, provider_names: list):
        super().__init__()
        self._pm = provider_manager
        self._names = provider_names

    def run(self):
        from backend.knowledge.brand_discovery import discover_brands
        try:
            brands, providers = discover_brands(self._pm, self._names)
            self.done.emit(brands, providers)
        except Exception as exc:
            self.error.emit(str(exc))


class _VolumeComparisonWorker(QThread):
    """Fetches real query-volume data from a VolumeProvider (#61) and
    compares it against the prompt library — runs off the UI thread since
    it makes a real network call."""
    done  = Signal(list)   # list of per-family result dicts
    error = Signal(str)

    def __init__(self, volume_provider, knowledge_repo):
        super().__init__()
        self._provider = volume_provider
        self._knowledge_repo = knowledge_repo

    def run(self):
        from backend.knowledge.prompt_volume_service import PromptVolumeService
        try:
            data = self._provider.get_query_volumes(days=90)
            if data["error"]:
                self.error.emit(data["error"])
                return
            svc = PromptVolumeService(knowledge_repo=self._knowledge_repo)
            results = svc.compare_families_to_queries(data["queries"])
            self.done.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class _BrandDiscoveryDialog(QDialog):
    def __init__(self, new_brands: list, providers_queried: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discovered Brands")
        self.setMinimumWidth(480)
        self.setMinimumHeight(500)

        root = QVBoxLayout()
        root.setSpacing(10)

        summary = QLabel(
            f"<b>{len(new_brands)}</b> brand(s) not currently in your library.<br>"
            f"<span style='color:#6B7280;font-size:11px;'>"
            f"Queried: {', '.join(providers_queried) if providers_queried else 'none'}</span>"
        )
        summary.setWordWrap(True)
        root.addWidget(summary)

        sel_bar = QHBoxLayout()
        btn_all  = QPushButton("Select All")
        btn_none = QPushButton("Deselect All")
        sel_bar.addWidget(btn_all)
        sel_bar.addWidget(btn_none)
        sel_bar.addStretch()
        root.addLayout(sel_bar)

        self._list = QListWidget()
        for brand in new_brands:
            item = QListWidgetItem(brand)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self._list.addItem(item)
        root.addWidget(self._list)

        self._add_btn = QPushButton(f"Add Selected ({len(new_brands)})")
        cancel_btn = QPushButton("Cancel")
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(self._add_btn)
        root.addLayout(btn_bar)

        btn_all.clicked.connect(self._select_all)
        btn_none.clicked.connect(self._deselect_all)
        self._list.itemChanged.connect(self._update_count)
        self._add_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        self.setLayout(root)

    def _select_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Unchecked)

    def _update_count(self):
        n = sum(
            1 for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        )
        self._add_btn.setText(f"Add Selected ({n})")

    def selected_brands(self) -> list:
        return [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        ]


class _FieldDialog(QDialog):
    def __init__(self, title, fields, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self._fields = fields
        self._widgets: dict = {}

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)

        for label, key, wtype, opts in fields:
            val = initial.get(key) if initial else None
            w = self._make_widget(wtype, opts, val)
            self._widgets[key] = w
            form.addRow(label, w)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        root = QVBoxLayout()
        root.setSpacing(16)
        root.addLayout(form)
        root.addWidget(btns)
        self.setLayout(root)

    @staticmethod
    def _make_widget(wtype, opts, val):
        if wtype == "text":
            w = QLineEdit(str(val) if val is not None else str(opts))
            w.setMinimumWidth(300)
            return w
        if wtype == "area":
            w = QPlainTextEdit()
            w.setPlainText(str(val) if val is not None else str(opts))
            w.setFixedHeight(90)
            return w
        if wtype == "combo":
            w = QComboBox()
            for opt in opts:
                w.addItem(opt)
            current = str(val) if val is not None else (opts[0] if opts else "")
            idx = w.findText(current)
            if idx >= 0:
                w.setCurrentIndex(idx)
            return w
        if wtype == "spin":
            w = QSpinBox()
            w.setRange(0, 999)
            w.setValue(int(val) if val is not None else int(opts))
            return w
        if wtype == "check":
            w = QCheckBox()
            w.setChecked(bool(val) if val is not None else bool(opts))
            return w
        return QLineEdit()

    def values(self) -> dict:
        result = {}
        for _, key, wtype, _ in self._fields:
            w = self._widgets.get(key)
            if w is None:
                continue
            if wtype == "text":
                result[key] = w.text().strip()
            elif wtype == "area":
                result[key] = w.toPlainText().strip()
            elif wtype == "combo":
                result[key] = w.currentText()
            elif wtype == "spin":
                result[key] = w.value()
            elif wtype == "check":
                result[key] = w.isChecked()
        return result


def _make_table(columns: list, widths: list) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setSelectionMode(QTableWidget.SingleSelection)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    for i, w in enumerate(widths):
        if w == -1:
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        else:
            t.setColumnWidth(i, w)
    return t


def _cell(text, row_id=None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    if row_id is not None:
        item.setData(Qt.UserRole, row_id)
    return item


def _trunc(s: str, n: int = 80) -> str:
    s = str(s) if s else ""
    return s[:n] + "…" if len(s) > n else s


def _action_bar(*buttons) -> QHBoxLayout:
    bar = QHBoxLayout()
    bar.setContentsMargins(0, 4, 0, 0)
    for b in buttons:
        if isinstance(b, str):
            bar.addStretch()
        else:
            bar.addWidget(b)
    return bar


class KnowledgePage(QWidget):
    def __init__(self, app=None):
        super().__init__()
        self.app = app
        self.repo = KnowledgeRepository()

        root = QVBoxLayout()
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        title = QLabel("Knowledge Library")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        subtitle = QLabel("Manage the brands, features, personas, and prompt sets Atlas tracks.")
        subtitle.setStyleSheet("font-size: 13px; color: #6B7280;")

        self._tabs = QTabWidget()
        self._tabs.addTab(self._brands_tab(),   "Brands")
        self._tabs.addTab(self._features_tab(), "Features")
        self._tabs.addTab(self._personas_tab(), "Personas")
        self._tabs.addTab(self._scenarios_tab(),"Scenarios")
        self._tabs.addTab(self._stages_tab(),   "Buying Stages")
        self._tabs.addTab(self._prompt_sets_tab(), "Prompt Sets")
        self._tabs.addTab(self._search_volume_tab(), "Search Volume")
        self._tabs.addTab(self._web_tab(),      "Web Intelligence")
        self._tabs.addTab(self._providers_tab(),"Providers")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self._tabs)
        self.setLayout(root)

    # ─── Brands ───────────────────────────────────────────────────────────────

    def _brands_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)

        self._brands_table = _make_table(
            ["Name", "Types", "Aliases", "Country", "Active"],
            [160, 130, 220, 80, 55]
        )
        self._brands_table.doubleClicked.connect(lambda _: self._edit_brand())

        self._brands_count = QLabel()

        btn_add      = QPushButton("+ Add Brand")
        btn_edit     = QPushButton("Edit")
        btn_del      = QPushButton("Delete")
        btn_discover = QPushButton("Discover Brands")
        btn_add.clicked.connect(self._add_brand)
        btn_edit.clicked.connect(self._edit_brand)
        btn_del.clicked.connect(self._delete_brand)
        btn_discover.clicked.connect(self._discover_brands)
        btn_discover.setToolTip(
            "Query AI providers for brands mentioned but not yet tracked — "
            "review and add any new competitors found"
        )

        self._disc_lbl = QLabel("")
        self._disc_lbl.setStyleSheet("color:#6B7280; font-size:11px;")
        self._disc_worker = None

        bar = _action_bar(btn_add, btn_edit, btn_del, btn_discover, "stretch", self._disc_lbl, self._brands_count)

        lay.addWidget(self._brands_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._refresh_brands()
        return w

    def _refresh_brands(self):
        rows = self.repo.list_brands()
        t = self._brands_table
        t.setRowCount(0)
        for row in rows:
            brand_id, name, website, description, active, aliases, tier, product_types, country, parent_company = row
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(name, brand_id))
            t.setItem(r, 1, _cell(product_types or ""))
            t.setItem(r, 2, _cell(_trunc(aliases or "", 40)))
            t.setItem(r, 3, _cell(country or ""))
            t.setItem(r, 4, _cell("Yes" if active else "No"))
        self._brands_count.setText(f"{len(rows)} brands")

    def _add_brand(self):
        dlg = _FieldDialog("Add Brand", _BRAND_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Brand name cannot be empty.")
            return
        self.repo.add_brand(
            name=v["name"],
            website=v.get("website", ""),
            description="",
            aliases=v.get("aliases", ""),
            product_types=v.get("product_types", ""),
            country=v.get("country", "US"),
            parent_company=v.get("parent_company", ""),
        )
        self._refresh_brands()

    def _edit_brand(self):
        row = self._brands_table.currentRow()
        if row < 0:
            return
        brand_id = self._brands_table.item(row, 0).data(Qt.UserRole)
        rec = self.repo.get_brand(brand_id)
        if not rec:
            return
        _, name, website, description, active, aliases, tier, product_types, country, parent_company = rec
        dlg = _FieldDialog(
            "Edit Brand", _BRAND_FIELDS,
            initial={
                "name": name,
                "website": website or "",
                "aliases": aliases or "",
                "product_types": product_types or "",
                "country": country or "US",
                "parent_company": parent_company or "",
                "active": bool(active),
            },
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Brand name cannot be empty.")
            return
        self.repo.update_brand(
            brand_id,
            name=v["name"],
            website=v.get("website", ""),
            description=description or "",
            active=1 if v.get("active") else 0,
            aliases=v.get("aliases", ""),
            tier=tier,
            product_types=v.get("product_types", ""),
            country=v.get("country", "US"),
            parent_company=v.get("parent_company", ""),
        )
        self._refresh_brands()

    def _delete_brand(self):
        row = self._brands_table.currentRow()
        if row < 0:
            return
        name = self._brands_table.item(row, 0).text()
        brand_id = self._brands_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Brand", f"Delete '{name}'?\nThis will also remove it from the tracking CSV.", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_brand(brand_id)
        self._refresh_brands()

    def _discover_brands(self):
        if self._disc_worker and self._disc_worker.isRunning():
            return
        pm = self.app.provider_manager if self.app else None
        if not pm:
            QMessageBox.warning(self, "Not Ready", "App not fully initialized.")
            return
        active = [name for name in pm.list_providers() if pm.get_provider_api_key(name)]
        if not active:
            QMessageBox.warning(
                self, "No Providers",
                "No API keys are configured. Add API keys in Settings first.",
            )
            return
        self._disc_lbl.setText(f"Querying {len(active)} provider(s)…")
        self._disc_worker = _BrandDiscoveryWorker(pm, active)
        self._disc_worker.done.connect(self._on_discovery_done)
        self._disc_worker.error.connect(self._on_discovery_error)
        self._disc_worker.start()

    def _on_discovery_done(self, all_brands: list, providers: list):
        new_brands = self.repo.filter_new_brands(all_brands)
        self._disc_lbl.setText(f"Found {len(all_brands)} total, {len(new_brands)} new")
        if not new_brands:
            QMessageBox.information(
                self, "No New Brands",
                f"All {len(all_brands)} brands returned by AI providers are already in your library.",
            )
            return
        dlg = _BrandDiscoveryDialog(new_brands, providers, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        selected = dlg.selected_brands()
        if not selected:
            return
        for name in selected:
            self.repo.add_brand(name=name)
        self._refresh_brands()
        self._disc_lbl.setText(f"Added {len(selected)} brand(s)")

    def _on_discovery_error(self, msg: str):
        self._disc_lbl.setText("Discovery failed")
        QMessageBox.critical(self, "Discovery Error", f"Brand discovery failed:\n{msg}")

    # ─── Features ─────────────────────────────────────────────────────────────

    def _features_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)

        self._features_table = _make_table(["Name", "Category"], [220, -1])
        self._features_table.doubleClicked.connect(lambda _: self._edit_feature())

        self._features_count = QLabel()

        btn_add = QPushButton("+ Add Feature")
        btn_edit = QPushButton("Edit")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add_feature)
        btn_edit.clicked.connect(self._edit_feature)
        btn_del.clicked.connect(self._delete_feature)

        bar = _action_bar(btn_add, btn_edit, btn_del, "stretch", self._features_count)

        lay.addWidget(self._features_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._refresh_features()
        return w

    def _refresh_features(self):
        rows = self.repo.list_features()
        t = self._features_table
        t.setRowCount(0)
        for feature_id, name, category in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(name, feature_id))
            t.setItem(r, 1, _cell(category))
        self._features_count.setText(f"{len(rows)} features")

    def _add_feature(self):
        dlg = _FieldDialog("Add Feature", _FEATURE_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Feature name cannot be empty.")
            return
        self.repo.add_feature(v["name"], v.get("category", ""))
        self._refresh_features()

    def _edit_feature(self):
        row = self._features_table.currentRow()
        if row < 0:
            return
        feature_id = self._features_table.item(row, 0).data(Qt.UserRole)
        name = self._features_table.item(row, 0).text()
        category = self._features_table.item(row, 1).text()
        dlg = _FieldDialog(
            "Edit Feature", _FEATURE_FIELDS,
            initial={"name": name, "category": category},
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Feature name cannot be empty.")
            return
        self.repo.update_feature(feature_id, v["name"], v.get("category", ""))
        self._refresh_features()

    def _delete_feature(self):
        row = self._features_table.currentRow()
        if row < 0:
            return
        name = self._features_table.item(row, 0).text()
        feature_id = self._features_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Feature", f"Delete '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_feature(feature_id)
        self._refresh_features()

    # ─── Personas ─────────────────────────────────────────────────────────────

    def _personas_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)

        self._personas_table = _make_table(
            ["Name", "Priority", "Primary Goal"],
            [160, 80, -1]
        )
        self._personas_table.doubleClicked.connect(lambda _: self._edit_persona())

        self._personas_count = QLabel()

        btn_add = QPushButton("+ Add Persona")
        btn_edit = QPushButton("Edit")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add_persona)
        btn_edit.clicked.connect(self._edit_persona)
        btn_del.clicked.connect(self._delete_persona)

        bar = _action_bar(btn_add, btn_edit, btn_del, "stretch", self._personas_count)

        lay.addWidget(self._personas_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._refresh_personas()
        return w

    def _refresh_personas(self):
        rows = self.repo.list_personas()
        t = self._personas_table
        t.setRowCount(0)
        for persona_id, name, description, primary_goal, concerns, priority in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(name, persona_id))
            t.setItem(r, 1, _cell(priority))
            t.setItem(r, 2, _cell(_trunc(primary_goal, 90)))
        self._personas_count.setText(f"{len(rows)} personas")

    def _add_persona(self):
        dlg = _FieldDialog("Add Persona", _PERSONA_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Persona name cannot be empty.")
            return
        self.repo.add_persona(v["name"], v.get("description", ""), v.get("primary_goal", ""), v.get("concerns", ""), v.get("priority", "Medium"))
        self._refresh_personas()

    def _edit_persona(self):
        row = self._personas_table.currentRow()
        if row < 0:
            return
        persona_id = self._personas_table.item(row, 0).data(Qt.UserRole)
        rec = self.repo.get_persona(persona_id)
        if not rec:
            return
        _, name, description, primary_goal, concerns, priority = rec
        dlg = _FieldDialog(
            "Edit Persona", _PERSONA_FIELDS,
            initial={"name": name, "description": description or "", "primary_goal": primary_goal or "", "concerns": concerns or "", "priority": priority or "Medium"},
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Persona name cannot be empty.")
            return
        self.repo.update_persona(persona_id, v["name"], v.get("description", ""), v.get("primary_goal", ""), v.get("concerns", ""), v.get("priority", "Medium"))
        self._refresh_personas()

    def _delete_persona(self):
        row = self._personas_table.currentRow()
        if row < 0:
            return
        name = self._personas_table.item(row, 0).text()
        persona_id = self._personas_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Persona", f"Delete '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_persona(persona_id)
        self._refresh_personas()

    # ─── Scenarios ────────────────────────────────────────────────────────────

    def _scenarios_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)

        self._scenarios_table = _make_table(["Name", "Description"], [200, -1])
        self._scenarios_table.doubleClicked.connect(lambda _: self._edit_scenario())

        self._scenarios_count = QLabel()

        btn_add = QPushButton("+ Add Scenario")
        btn_edit = QPushButton("Edit")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add_scenario)
        btn_edit.clicked.connect(self._edit_scenario)
        btn_del.clicked.connect(self._delete_scenario)

        bar = _action_bar(btn_add, btn_edit, btn_del, "stretch", self._scenarios_count)

        lay.addWidget(self._scenarios_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._refresh_scenarios()
        return w

    def _refresh_scenarios(self):
        rows = self.repo.list_scenarios()
        t = self._scenarios_table
        t.setRowCount(0)
        for scenario_id, name, description in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(name, scenario_id))
            t.setItem(r, 1, _cell(_trunc(description, 100)))
        self._scenarios_count.setText(f"{len(rows)} scenarios")

    def _add_scenario(self):
        dlg = _FieldDialog("Add Scenario", _SCENARIO_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Scenario name cannot be empty.")
            return
        self.repo.add_scenario(v["name"], v.get("description", ""))
        self._refresh_scenarios()

    def _edit_scenario(self):
        row = self._scenarios_table.currentRow()
        if row < 0:
            return
        scenario_id = self._scenarios_table.item(row, 0).data(Qt.UserRole)
        rec = self.repo.get_scenario(scenario_id)
        if not rec:
            return
        _, name, description = rec
        dlg = _FieldDialog(
            "Edit Scenario", _SCENARIO_FIELDS,
            initial={"name": name, "description": description or ""},
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Scenario name cannot be empty.")
            return
        self.repo.update_scenario(scenario_id, v["name"], v.get("description", ""))
        self._refresh_scenarios()

    def _delete_scenario(self):
        row = self._scenarios_table.currentRow()
        if row < 0:
            return
        name = self._scenarios_table.item(row, 0).text()
        scenario_id = self._scenarios_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Scenario", f"Delete '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_scenario(scenario_id)
        self._refresh_scenarios()

    # ─── Buying Stages ────────────────────────────────────────────────────────

    def _stages_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)

        self._stages_table = _make_table(["Order", "Stage", "Description"], [60, 180, -1])
        self._stages_table.doubleClicked.connect(lambda _: self._edit_stage())

        self._stages_count = QLabel()

        btn_add = QPushButton("+ Add Stage")
        btn_edit = QPushButton("Edit")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add_stage)
        btn_edit.clicked.connect(self._edit_stage)
        btn_del.clicked.connect(self._delete_stage)

        bar = _action_bar(btn_add, btn_edit, btn_del, "stretch", self._stages_count)

        lay.addWidget(self._stages_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._refresh_stages()
        return w

    def _refresh_stages(self):
        rows = self.repo.list_buying_stages()
        t = self._stages_table
        t.setRowCount(0)
        for stage_id, name, description, sort_order in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(sort_order, stage_id))
            t.setItem(r, 1, _cell(name))
            t.setItem(r, 2, _cell(_trunc(description, 100)))
        self._stages_count.setText(f"{len(rows)} stages")

    def _add_stage(self):
        dlg = _FieldDialog("Add Buying Stage", _STAGE_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Stage name cannot be empty.")
            return
        self.repo.add_buying_stage(v["name"], v.get("description", ""), v.get("sort_order", 99))
        self._refresh_stages()

    def _edit_stage(self):
        row = self._stages_table.currentRow()
        if row < 0:
            return
        stage_id = self._stages_table.item(row, 0).data(Qt.UserRole)
        rec = self.repo.get_buying_stage(stage_id)
        if not rec:
            return
        _, name, description, sort_order = rec
        dlg = _FieldDialog(
            "Edit Buying Stage", _STAGE_FIELDS,
            initial={"name": name, "description": description or "", "sort_order": sort_order or 0},
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            QMessageBox.warning(self, "Name Required", "Stage name cannot be empty.")
            return
        self.repo.update_buying_stage(stage_id, v["name"], v.get("description", ""), v.get("sort_order", 99))
        self._refresh_stages()

    def _delete_stage(self):
        row = self._stages_table.currentRow()
        if row < 0:
            return
        name = self._stages_table.item(row, 1).text()
        stage_id = self._stages_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Stage", f"Delete '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_buying_stage(stage_id)
        self._refresh_stages()

    # ─── Prompt Sets ──────────────────────────────────────────────────────────

    def _prompt_sets_tab(self) -> QWidget:
        w = QWidget()
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(0, 8, 0, 0)

        # Left: family list
        left = QWidget()
        left_lay = QVBoxLayout()
        left_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.setSpacing(4)

        lbl = QLabel("Prompt Families")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")

        self._family_list = QListWidget()
        self._family_list.currentItemChanged.connect(self._on_family_selected)

        btn_new_fam = QPushButton("+ New Family")
        btn_new_fam.clicked.connect(self._add_family)

        # Category — a purely additive tier above families, for grouping
        # related families so the Visibility page can select a whole cluster
        # with one checkbox. Assigning here never changes market_questions.csv.
        cat_row = QHBoxLayout()
        cat_row.setContentsMargins(0, 0, 0, 0)
        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet("font-size: 12px; color: #6B7280;")
        self._category_combo = QComboBox()
        self._category_combo.currentIndexChanged.connect(self._on_category_combo_changed)
        btn_new_cat = QPushButton("+")
        btn_new_cat.setFixedWidth(28)
        btn_new_cat.setToolTip("Create a new category")
        btn_new_cat.clicked.connect(self._add_category)
        cat_row.addWidget(cat_lbl)
        cat_row.addWidget(self._category_combo, 1)
        cat_row.addWidget(btn_new_cat)

        left_lay.addWidget(lbl)
        left_lay.addWidget(self._family_list)
        left_lay.addWidget(btn_new_fam)
        left_lay.addLayout(cat_row)
        left.setLayout(left_lay)
        left.setFixedWidth(240)

        # Right: prompts in selected family
        right = QWidget()
        right_lay = QVBoxLayout()
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)

        self._family_header = QLabel("Select a family to view its prompts")
        self._family_header.setStyleSheet("font-weight: bold; font-size: 13px;")

        self._prompts_table = _make_table(["Style", "Prompt Text", "Score"], [90, -1, 55])

        btn_add_prompt = QPushButton("+ Add Prompt")
        btn_rem_prompt = QPushButton("Remove")
        btn_add_prompt.clicked.connect(self._add_prompt)
        btn_rem_prompt.clicked.connect(self._delete_prompt)

        self._prompts_count = QLabel()

        prompt_bar = _action_bar(btn_add_prompt, btn_rem_prompt, "stretch", self._prompts_count)

        right_lay.addWidget(self._family_header)
        right_lay.addWidget(self._prompts_table)
        right_lay.addLayout(prompt_bar)
        right.setLayout(right_lay)

        main_lay.addWidget(left)
        main_lay.addWidget(right)
        w.setLayout(main_lay)

        self._refresh_families()
        if not self._current_family_name():
            self._refresh_category_combo("")
        return w

    def _refresh_families(self):
        counts = self.repo.get_prompt_counts()
        families = self.repo.list_prompt_families()
        fam_categories = self.repo.get_family_category_map()
        prev = self._current_family_name()

        self._family_list.clear()
        for _, fname, *_ in families:
            count = counts.get(fname, 0)
            cat = fam_categories.get(fname)
            label = f"{fname}  ({count})" + (f"  ·  {cat}" if cat else "")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, fname)
            self._family_list.addItem(item)

        if prev:
            self._select_family_by_name(prev)

    def _on_family_selected(self, current, _=None):
        if not current:
            return
        fname = current.data(Qt.UserRole)
        self._load_prompts_for(fname)
        self._refresh_category_combo(fname)

    # ─── Categories ───────────────────────────────────────────────────────────

    def _refresh_category_combo(self, fname: str):
        """Repopulate the combo and select fname's current category, without
        firing _on_category_combo_changed (which would re-assign fname)."""
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        self._category_combo.addItem("(Uncategorized)", None)
        categories = self.repo.list_prompt_categories()
        current_category = self.repo.get_family_category_map().get(fname)
        select_index = 0
        for i, (cat_id, name, _count) in enumerate(categories, start=1):
            self._category_combo.addItem(name, cat_id)
            if name == current_category:
                select_index = i
        self._category_combo.setCurrentIndex(select_index)
        self._category_combo.blockSignals(False)

    def _on_category_combo_changed(self, _index: int):
        fname = self._current_family_name()
        if not fname:
            return
        category_id = self._category_combo.currentData()
        self.repo.set_family_category(fname, category_id)
        self._refresh_families()
        self._select_family_by_name(fname)

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if not ok or not name.strip():
            return
        cat_id = self.repo.add_prompt_category(name.strip())
        fname = self._current_family_name()
        if fname:
            self.repo.set_family_category(fname, cat_id)
            self._refresh_families()
            self._select_family_by_name(fname)
        else:
            self._refresh_category_combo("")

    def _load_prompts_for(self, fname: str):
        self._family_header.setText(f"Prompts — {fname}")
        prompts = self.repo.list_prompts_in_family(fname)
        t = self._prompts_table
        t.setRowCount(0)
        for style, text, score in prompts:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(style))
            item = _cell(text)
            item.setData(Qt.UserRole, text)
            t.setItem(r, 1, item)
            t.setItem(r, 2, _cell(score))
        self._prompts_count.setText(f"{len(prompts)} prompts")

    def _current_family_name(self) -> str:
        item = self._family_list.currentItem()
        return item.data(Qt.UserRole) if item else ""

    def _select_family_by_name(self, name: str):
        for i in range(self._family_list.count()):
            item = self._family_list.item(i)
            if item.data(Qt.UserRole) == name:
                self._family_list.setCurrentItem(item)
                return

    def _add_family(self):
        dlg = _FieldDialog("New Prompt Family", _FAMILY_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["family_name"]:
            QMessageBox.warning(self, "Name Required", "Family name cannot be empty.")
            return
        self.repo.add_prompt_family(v["family_name"])
        self._refresh_families()
        self._select_family_by_name(v["family_name"])

    def _add_prompt(self):
        fname = self._current_family_name()
        if not fname:
            QMessageBox.information(self, "No Family", "Select a prompt family first.")
            return
        dlg = _FieldDialog(f"Add Prompt to '{fname}'", _PROMPT_FIELDS, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["text"]:
            QMessageBox.warning(self, "Text Required", "Prompt text cannot be empty.")
            return
        self.repo.add_prompt(fname, v.get("style", "question"), v["text"], str(v.get("score", 5)))
        self._refresh_families()
        self._select_family_by_name(fname)

    def _delete_prompt(self):
        row = self._prompts_table.currentRow()
        if row < 0:
            return
        fname = self._current_family_name()
        item = self._prompts_table.item(row, 1)
        if not item:
            return
        prompt_text = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Remove Prompt", f"Remove this prompt from '{fname}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_prompt(fname, prompt_text)
        self._refresh_families()
        self._select_family_by_name(fname)

    # ─── Search Volume ────────────────────────────────────────────────────────
    # #61: sanity-checks the hand-curated prompt library (168 families) against
    # real search-query volume from a VolumeProvider (Settings > Keyword Volume
    # Providers), distinguishing families with genuine real-world query
    # backing from ones that are just a reasonable-sounding guess.

    def _search_volume_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)

        note = QLabel(
            "Compares every prompt family against real search queries from a configured "
            "Keyword Volume Provider (Settings), to show which families reflect genuine "
            "real-world search demand versus a reasonable-sounding guess — useful when "
            "deciding which families deserve the Visibility page's \"Top 20\" treatment. "
            "Configure a provider in Settings first, then Run Comparison."
        )
        note.setStyleSheet("color: #6B7280; font-size: 12px;")
        note.setWordWrap(True)

        self._volume_table = _make_table(
            ["Family", "Influence Score", "Real Search Backing", "Matched Queries",
             "Real Impressions", "Real Clicks"],
            [220, 100, 130, 110, 110, 90],
        )
        self._volume_table.horizontalHeaderItem(2).setToolTip(
            "Whether at least one real search query meaningfully overlaps with this "
            "family's prompt text (word-overlap match, not fuzzy/ML matching)."
        )

        self._volume_run_btn = QPushButton("Run Comparison")
        self._volume_run_btn.clicked.connect(self._run_volume_comparison)
        self._volume_status_lbl = QLabel("")
        self._volume_status_lbl.setStyleSheet("color:#6B7280; font-size:11px;")

        bar = _action_bar(self._volume_run_btn, "stretch", self._volume_status_lbl)

        lay.addWidget(note)
        lay.addWidget(self._volume_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._volume_worker = None
        return w

    def _run_volume_comparison(self):
        if self._volume_worker and self._volume_worker.isRunning():
            return
        vpm = self.app.volume_provider_manager if self.app else None
        if not vpm:
            QMessageBox.warning(self, "Not Ready", "App not fully initialized.")
            return
        provider_keys = vpm.list_providers()
        if not provider_keys:
            QMessageBox.information(self, "No Volume Providers", "No volume providers are registered.")
            return
        # Only one provider exists today (Google Search Console); once a
        # second is added, this should become a combo like the Web
        # Intelligence source selector rather than always using the first.
        provider = vpm.get_provider(provider_keys[0])
        if not provider.credential or not provider.site_url:
            QMessageBox.information(
                self, "Not Configured",
                f"Configure a credential and site URL for {provider.provider_name} "
                "in Settings first.",
            )
            return

        self._volume_run_btn.setEnabled(False)
        self._volume_status_lbl.setText(f"Fetching real query data from {provider.provider_name}…")
        self._volume_worker = _VolumeComparisonWorker(provider, self.repo)
        self._volume_worker.done.connect(self._on_volume_comparison_done)
        self._volume_worker.error.connect(self._on_volume_comparison_error)
        self._volume_worker.finished.connect(lambda: self._volume_run_btn.setEnabled(True))
        self._volume_worker.start()

    def _on_volume_comparison_done(self, results: list):
        t = self._volume_table
        t.setSortingEnabled(False)
        t.setRowCount(len(results))
        for r, res in enumerate(results):
            t.setItem(r, 0, _cell(res["family_name"]))
            t.setItem(r, 1, _cell(res["prompt_influence_score"]))
            backed_item = _cell("✓ Backed" if res["has_real_backing"] else "No real queries found")
            backed_item.setForeground(QColor("#16a34a") if res["has_real_backing"] else QColor("#dc2626"))
            t.setItem(r, 2, backed_item)
            t.setItem(r, 3, _cell(res["matched_query_count"]))
            t.setItem(r, 4, _cell(f"{res['real_search_impressions']:,}"))
            t.setItem(r, 5, _cell(f"{res['real_search_clicks']:,}"))
        t.setSortingEnabled(True)
        backed_count = sum(1 for r in results if r["has_real_backing"])
        self._volume_status_lbl.setText(
            f"{backed_count} of {len(results)} families have real search-query backing."
        )

    def _on_volume_comparison_error(self, message: str):
        self._volume_status_lbl.setText(f"Error: {message}")

    # ─── Web Intelligence ─────────────────────────────────────────────────────

    def _web_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)

        note = QLabel(
            "Scrapes each brand's homepage for on-page SEO signals — title, meta description, "
            "keywords, HTTPS/schema/sitemap presence, load time, and whether robots.txt blocks "
            "known AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Bingbot, CCBot) "
            "— and feeds them into the Intelligence briefing's competitive web analysis. Mark one "
            "entry as your own site (checkbox in Add/Edit) to audit it directly — it's sorted to "
            "the top and shown in bold, and scraping it will warn immediately if it's blocking an "
            "AI crawler. (Off-page metrics like Domain Authority or backlink counts require a paid "
            "SEO tool subscription and aren't scraped here.)"
        )
        note.setStyleSheet("color: #6B7280; font-size: 12px;")
        note.setWordWrap(True)

        self._web_table = _make_table(
            ["Brand", "Domain", "Own Site", "Title", "Meta Description", "Keywords",
             "HTTPS", "Schema", "Sitemap", "Load (ms)", "AI Crawlers", "Source", "Updated"],
            [110, 140, 70, 150, 190, 130, 55, 60, 60, 75, 120, 80, 90],
        )
        self._web_table.doubleClicked.connect(lambda _: self._edit_web())
        self._web_table.horizontalHeaderItem(2).setToolTip(
            "Flags this entry as your own company's site rather than a competitor. "
            "Own-site entries sort to the top and appear in bold."
        )
        self._web_table.horizontalHeaderItem(10).setToolTip(
            "Whether this domain's robots.txt blocks a known AI crawler (GPTBot, ClaudeBot, "
            "PerplexityBot, Google-Extended, Bingbot, CCBot) from the entire site. Blocking one "
            "of these on your OWN site can directly suppress AI visibility."
        )

        self._web_count = QLabel()
        self._web_scrape_lbl = QLabel("")
        self._web_scrape_lbl.setStyleSheet("color:#6B7280; font-size:11px;")

        btn_add       = QPushButton("+ Add Entry")
        btn_edit      = QPushButton("Edit")
        btn_del       = QPushButton("Delete")
        self._btn_scrape     = QPushButton("Scrape Selected")
        self._btn_scrape_all = QPushButton("Scrape All")
        btn_add.clicked.connect(self._add_web)
        btn_edit.clicked.connect(self._edit_web)
        btn_del.clicked.connect(self._delete_web)
        self._btn_scrape.clicked.connect(self._scrape_selected)
        self._btn_scrape_all.clicked.connect(self._scrape_all)

        bar = _action_bar(
            btn_add, btn_edit, btn_del,
            self._btn_scrape, self._btn_scrape_all,
            "stretch", self._web_scrape_lbl, self._web_count,
        )

        lay.addWidget(note)
        lay.addWidget(self._web_table)
        lay.addLayout(bar)
        w.setLayout(lay)
        self._web_worker = None
        self._refresh_web()
        return w

    def _refresh_web(self):
        rows = self.repo.list_web_intelligence()
        t = self._web_table
        t.setRowCount(0)
        for (entry_id, brand, domain, title, meta_desc, top_kw,
             is_https, has_schema, has_sitemap, load_ms,
             notes, source, recorded, scraped,
             is_own_site, has_robots_txt, blocks_ai_crawlers, blocked_names) in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(brand, entry_id))
            t.setItem(r, 1, _cell(domain or "—"))
            t.setItem(r, 2, _cell("Yes" if is_own_site else "—"))
            t.setItem(r, 3, _cell(_trunc(title or "", 30) or "—"))
            t.setItem(r, 4, _cell(_trunc(meta_desc or "", 40) or "—"))
            t.setItem(r, 5, _cell(_trunc(top_kw or "", 30) or "—"))
            scraped_yet = bool(scraped)
            t.setItem(r, 6, _cell("Yes" if is_https else ("No" if scraped_yet else "—")))
            t.setItem(r, 7, _cell("Yes" if has_schema else ("No" if scraped_yet else "—")))
            t.setItem(r, 8, _cell("Yes" if has_sitemap else ("No" if scraped_yet else "—")))
            t.setItem(r, 9, _cell(f"{load_ms:,}" if load_ms else "—"))
            if not scraped_yet:
                crawler_item = _cell("—")
            elif blocks_ai_crawlers:
                crawler_item = _cell(f"Blocked: {_trunc(blocked_names or '', 22)}")
                crawler_item.setForeground(QColor("#dc2626"))
            elif has_robots_txt:
                crawler_item = _cell("OK")
                crawler_item.setForeground(QColor("#16a34a"))
            else:
                crawler_item = _cell("No robots.txt")
            t.setItem(r, 10, crawler_item)
            t.setItem(r, 11, _cell(source or "manual"))
            date_str = (scraped or recorded or "")[:10]
            t.setItem(r, 12, _cell(date_str))
            if is_own_site:
                for col in range(t.columnCount()):
                    item = t.item(r, col)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
        self._web_count.setText(f"{len(rows)} entries")

    def _web_fields(self, brands_list):
        """
        Build field spec list for the web intelligence dialog. Deliberately
        excludes Monthly Visits/Domain Authority/Organic Keywords/Backlinks —
        those require a paid SEO tool (Moz/SEMrush/Ahrefs/SimilarWeb) and
        would be dead, never-displayed inputs now that the table only shows
        signals scrape_domain() can actually produce.
        """
        return [
            ("Brand *",       "brand",       "combo", brands_list),
            ("Domain",        "domain",      "text",  ""),
            ("Own Site (Your Company)", "is_own_site", "check", False),
            ("Top Keywords",  "top_keywords","text",  ""),
            ("Notes",         "notes",       "area",  ""),
            ("Source",        "data_source", "combo", ["manual", "similarweb", "semrush", "ahrefs", "moz"]),
        ]

    def _add_web(self):
        brands = [(bid, bname) for bid, bname, *_ in self.repo.list_brands()]
        brand_names = [bname for _, bname in brands]
        if not brand_names:
            QMessageBox.information(self, "No Brands", "Add brands on the Brands tab first.")
            return
        dlg = _FieldDialog("Add Web Intelligence Entry", self._web_fields(brand_names), parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        brand_id = next((bid for bid, bn in brands if bn == v["brand"]), None)
        if not brand_id:
            return
        self.repo.add_web_entry(
            brand_id=brand_id,
            domain=v.get("domain", ""),
            top_keywords=v.get("top_keywords", ""),
            notes=v.get("notes", ""),
            source=v.get("data_source", "manual"),
            is_own_site=v.get("is_own_site", False),
        )
        self._refresh_web()

    def _edit_web(self):
        row = self._web_table.currentRow()
        if row < 0:
            return
        entry_id = self._web_table.item(row, 0).data(Qt.UserRole)
        rec = self.repo.get_web_entry(entry_id)
        if not rec:
            return
        # get_web_entry() still returns the legacy visits/da/kw/backlinks columns
        # (schema kept as-is, just unused by this dialog now — see _web_fields).
        (_, brand_id, brand_name, domain, _visits, _da, _kw, _backlinks, top_kw, notes, source,
         is_own_site) = rec

        brands = [(bid, bname) for bid, bname, *_ in self.repo.list_brands()]
        brand_names = [bname for _, bname in brands]
        initial = {
            "brand": brand_name, "domain": domain or "",
            "is_own_site": bool(is_own_site),
            "top_keywords": top_kw or "", "notes": notes or "",
            "data_source": source or "manual",
        }
        dlg = _FieldDialog("Edit Web Intelligence Entry", self._web_fields(brand_names),
                            initial=initial, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        new_brand_id = next((bid for bid, bn in brands if bn == v["brand"]), brand_id)
        self.repo.update_web_entry(
            entry_id=entry_id,
            brand_id=new_brand_id,
            domain=v.get("domain", ""),
            top_keywords=v.get("top_keywords", ""),
            notes=v.get("notes", ""),
            source=v.get("data_source", "manual"),
            is_own_site=v.get("is_own_site", False),
        )
        self._refresh_web()

    def _delete_web(self):
        row = self._web_table.currentRow()
        if row < 0:
            return
        brand = self._web_table.item(row, 0).text()
        entry_id = self._web_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Delete Entry", f"Delete web intelligence entry for '{brand}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.repo.delete_web_entry(entry_id)
        self._refresh_web()

    def _scrape_selected(self):
        row = self._web_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a row to scrape.")
            return
        entry_id = self._web_table.item(row, 0).data(Qt.UserRole)
        domain   = self._web_table.item(row, 1).text()
        brand    = self._web_table.item(row, 0).text()
        if not domain or domain == "—":
            QMessageBox.information(self, "No Domain", "This entry has no domain set.")
            return
        self._start_scrape([(entry_id, brand, domain)])

    def _scrape_all(self):
        rows = self.repo.list_web_intelligence()
        entries = [
            (r[0], r[1], r[2])
            for r in rows
            if r[2]  # domain not empty
        ]
        if not entries:
            QMessageBox.information(self, "Nothing to Scrape", "Add entries with domains first.")
            return
        self._start_scrape(entries)

    def _start_scrape(self, entries):
        if self._web_worker and self._web_worker.isRunning():
            return
        self._web_own_site_map = {
            row[0]: bool(row[14]) for row in self.repo.list_web_intelligence()
        }
        self._btn_scrape.setEnabled(False)
        self._btn_scrape_all.setEnabled(False)
        self._web_scrape_lbl.setText(f"Starting scrape of {len(entries)} domain(s)…")
        self._web_worker = _ScrapeWorker(entries)
        self._web_worker.progress.connect(self._on_scrape_progress)
        self._web_worker.done.connect(self._on_scrape_done)
        self._web_worker.finished_all.connect(self._on_scrape_finished)
        self._web_worker.start()

    def _on_scrape_progress(self, current, total, brand_name):
        self._web_scrape_lbl.setText(f"Scraping {current}/{total}: {brand_name}…")

    def _on_scrape_done(self, entry_id, result):
        if result.get("error"):
            self._web_scrape_lbl.setText(f"Error on entry {entry_id}: {result['error']}")
        self.repo.update_web_scrape_result(entry_id, result)
        self._refresh_web()
        is_own_site = getattr(self, "_web_own_site_map", {}).get(entry_id, False)
        if is_own_site and result.get("blocks_ai_crawlers"):
            blocked = ", ".join(result.get("blocked_crawler_names", []))
            QMessageBox.warning(
                self, "Your Site Blocks AI Crawlers",
                f"robots.txt on this domain blocks: {blocked}\n\n"
                "This directly prevents that AI provider from crawling your site, which can "
                "suppress AI visibility. Review robots.txt and update it if this wasn't "
                "intentional."
            )

    def _on_scrape_finished(self):
        self._btn_scrape.setEnabled(True)
        self._btn_scrape_all.setEnabled(True)
        self._web_scrape_lbl.setText("Scrape complete.")

    # ─── Providers ────────────────────────────────────────────────────────────

    def _providers_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)

        note = QLabel("Provider API keys and model overrides are configured in ⚙ Settings. "
                       "This view shows current status.")
        note.setStyleSheet("color: #6B7280; font-size: 12px;")
        note.setWordWrap(True)

        t = _make_table(
            ["Provider", "Default Model", "Active Model", "Key Status"],
            [140, 180, 200, 120]
        )

        pm = self.app.provider_manager if self.app else None

        for key, (label, default_model) in _PROVIDER_INFO.items():
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(label))
            t.setItem(r, 1, _cell(default_model))

            if pm:
                custom = pm.get_provider_model(key)
                active_model = custom if custom else default_model
                has_key = bool(pm.get_provider_api_key(key))
            else:
                active_model = default_model
                has_key = False

            t.setItem(r, 2, _cell(active_model))

            status_item = _cell("Configured" if has_key else "No key set")
            status_item.setForeground(QColor("#16a34a") if has_key else QColor("#dc2626"))
            t.setItem(r, 3, status_item)

        lay.addWidget(note)
        lay.addWidget(t)
        lay.addStretch()
        w.setLayout(lay)
        return w
