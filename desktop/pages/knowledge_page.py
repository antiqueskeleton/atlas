from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
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

        btn_add = QPushButton("+ Add Brand")
        btn_edit = QPushButton("Edit")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add_brand)
        btn_edit.clicked.connect(self._edit_brand)
        btn_del.clicked.connect(self._delete_brand)

        bar = _action_bar(btn_add, btn_edit, btn_del, "stretch", self._brands_count)

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

        left_lay.addWidget(lbl)
        left_lay.addWidget(self._family_list)
        left_lay.addWidget(btn_new_fam)
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
        return w

    def _refresh_families(self):
        counts = self.repo.get_prompt_counts()
        families = self.repo.list_prompt_families()
        prev = self._current_family_name()

        self._family_list.clear()
        for _, fname, *_ in families:
            count = counts.get(fname, 0)
            item = QListWidgetItem(f"{fname}  ({count})")
            item.setData(Qt.UserRole, fname)
            self._family_list.addItem(item)

        if prev:
            self._select_family_by_name(prev)

    def _on_family_selected(self, current, _=None):
        if not current:
            return
        fname = current.data(Qt.UserRole)
        self._load_prompts_for(fname)

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

    # ─── Web Intelligence ─────────────────────────────────────────────────────

    def _web_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)

        note = QLabel(
            "Track website metrics per brand — monthly visits, domain authority, backlinks, and organic keywords. "
            "Enter data manually or import from SEO tools (SimilarWeb, SEMrush, Ahrefs, Moz)."
        )
        note.setStyleSheet("color: #6B7280; font-size: 12px;")
        note.setWordWrap(True)

        self._web_table = _make_table(
            ["Brand", "Domain", "Monthly Visits", "Domain Authority", "Keywords", "Backlinks", "Source", "Updated"],
            [120, 160, 110, 130, 90, 90, 80, 110],
        )
        self._web_table.doubleClicked.connect(lambda _: self._edit_web())

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
        for entry_id, brand, domain, visits, da, kw, backlinks, top_kw, notes, source, recorded, scraped in rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _cell(brand, entry_id))
            t.setItem(r, 1, _cell(domain or "—"))
            t.setItem(r, 2, _cell(f"{visits:,}" if visits else "—"))
            t.setItem(r, 3, _cell(f"{da}/100" if da else "—"))
            kw_display = (top_kw or "")[:40] or (f"{kw:,}" if kw else "—")
            t.setItem(r, 4, _cell(kw_display))
            t.setItem(r, 5, _cell(f"{backlinks:,}" if backlinks else "—"))
            t.setItem(r, 6, _cell(source or "manual"))
            date_str = (scraped or recorded or "")[:10]
            t.setItem(r, 7, _cell(date_str))
        self._web_count.setText(f"{len(rows)} entries")

    def _web_fields(self, brands_list):
        """Build field spec list for the web intelligence dialog."""
        return [
            ("Brand *",          "brand",            "combo", brands_list),
            ("Domain",           "domain",           "text",  ""),
            ("Monthly Visits",   "monthly_visits",   "text",  "0"),
            ("Domain Authority", "domain_authority", "text",  "0"),
            ("Organic Keywords", "organic_keywords", "text",  "0"),
            ("Backlinks",        "backlinks",        "text",  "0"),
            ("Top Keywords",     "top_keywords",     "text",  ""),
            ("Notes",            "notes",            "area",  ""),
            ("Source",           "data_source",      "combo", ["manual", "similarweb", "semrush", "ahrefs", "moz"]),
        ]

    @staticmethod
    def _safe_int(v) -> int:
        try:
            return max(0, int(str(v).replace(",", "").strip()))
        except (ValueError, TypeError):
            return 0

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
            monthly_visits=self._safe_int(v.get("monthly_visits")),
            domain_authority=self._safe_int(v.get("domain_authority")),
            organic_keywords=self._safe_int(v.get("organic_keywords")),
            backlinks=self._safe_int(v.get("backlinks")),
            top_keywords=v.get("top_keywords", ""),
            notes=v.get("notes", ""),
            source=v.get("data_source", "manual"),
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
        _, brand_id, brand_name, domain, visits, da, kw, backlinks, top_kw, notes, source = rec

        brands = [(bid, bname) for bid, bname, *_ in self.repo.list_brands()]
        brand_names = [bname for _, bname in brands]
        initial = {
            "brand": brand_name, "domain": domain or "",
            "monthly_visits": str(visits or 0), "domain_authority": str(da or 0),
            "organic_keywords": str(kw or 0), "backlinks": str(backlinks or 0),
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
            monthly_visits=self._safe_int(v.get("monthly_visits")),
            domain_authority=self._safe_int(v.get("domain_authority")),
            organic_keywords=self._safe_int(v.get("organic_keywords")),
            backlinks=self._safe_int(v.get("backlinks")),
            top_keywords=v.get("top_keywords", ""),
            notes=v.get("notes", ""),
            source=v.get("data_source", "manual"),
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
