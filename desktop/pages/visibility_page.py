import os
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.knowledge.knowledge_repository import KnowledgeRepository
from backend.visibility.visibility_service import VisibilityService
from desktop.sleep_guard import allow_sleep, prevent_sleep
from desktop.widgets.info_icon import info_icon


# ── Worker thread ─────────────────────────────────────────────────────────────

class _RunWorker(QThread):
    progress = Signal(int, int)
    run_done = Signal(dict)
    all_done = Signal()
    error    = Signal(str)

    def __init__(self, service: VisibilityService, prompts: list, label: str,
                 providers: list, prompt_families: dict):
        super().__init__()
        self.service = service
        self.prompts = prompts
        self.label = label
        self.providers = providers
        self.prompt_families = prompt_families
        self._cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._total_prompts = len(prompts)

    def cancel(self):
        self._cancelled = True
        self._pause_event.set()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def run(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = self._total_prompts * len(self.providers)
        lock = threading.Lock()
        completed = [0]

        pm = self.service.provider_manager
        provider_objects = {name: pm.get_provider(name) for name in self.providers}

        def _run_one(provider_name: str):
            if self._cancelled:
                return

            provider_obj = provider_objects[provider_name]

            def _cb(done, _of_run):
                with lock:
                    completed[0] += 1
                    self.progress.emit(completed[0], total)

            try:
                result = self.service.run(
                    prompts=self.prompts,
                    prompt_set=self.label,
                    provider=provider_obj,
                    progress_callback=_cb,
                    cancelled=lambda: self._cancelled,
                    paused=lambda: not self._pause_event.is_set(),
                    prompt_families=self.prompt_families,
                )
                self.run_done.emit(result)
            except Exception as exc:
                self.error.emit(f"{provider_name}: {exc}")

        with ThreadPoolExecutor(max_workers=len(self.providers)) as pool:
            futures = [pool.submit(_run_one, name) for name in self.providers]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    self.error.emit(f"Thread error: {exc}")

        self.all_done.emit()


# ── PDF export worker ─────────────────────────────────────────────────────────

class _PDFWorker(QThread):
    finished = Signal(tuple)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        self.finished.emit(self._fn())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stat_card(title, value, subtitle="", info=""):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lay = QVBoxLayout()
    lay.setSpacing(2)
    lay.setContentsMargins(14, 12, 14, 12)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(4)
    t = QLabel(title);  t.setObjectName("CardTitle")
    title_row.addWidget(t)
    if info:
        title_row.addWidget(info_icon(info))
    title_row.addStretch()

    v = QLabel(value);  v.setObjectName("CardValue")
    lay.addLayout(title_row)
    lay.addWidget(v)

    if subtitle:
        s = QLabel(subtitle); s.setObjectName("CardSubtitle")
        lay.addWidget(s)

    frame.setLayout(lay)
    return frame, t, v


def _compact_card(title, value):
    """Single-row compact card: Title: Value — for dense KPI rows."""
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lay = QHBoxLayout()
    lay.setSpacing(6)
    lay.setContentsMargins(10, 5, 10, 5)

    t = QLabel(title + ":")
    t.setStyleSheet("font-size: 11px; color: #6B7280; font-weight: 600;")
    t.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    v = QLabel(value)
    v.setStyleSheet("font-size: 13px; font-weight: bold; color: #111827;")
    lay.addWidget(t)
    lay.addWidget(v)
    lay.addStretch()
    frame.setLayout(lay)
    return frame, t, v


def _section(title):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    lay = QVBoxLayout()
    lay.setSpacing(6)
    lay.setContentsMargins(12, 10, 12, 10)

    t = QLabel(title); t.setObjectName("CardTitle")
    body = QTextEdit()
    body.setReadOnly(True)
    body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    body.setStyleSheet("font-size: 12px; font-family: Consolas, monospace;")

    lay.addWidget(t)
    lay.addWidget(body)
    frame.setLayout(lay)
    return frame, body


def _table_section(title, columns, stretch_last=True):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    lay = QVBoxLayout()
    lay.setSpacing(6)
    lay.setContentsMargins(12, 10, 12, 10)

    t = QLabel(title); t.setObjectName("CardTitle")

    tbl = QTableWidget()
    tbl.setColumnCount(len(columns))
    tbl.setHorizontalHeaderLabels(columns)
    tbl.verticalHeader().hide()
    tbl.setEditTriggers(QTableWidget.NoEditTriggers)
    tbl.setSelectionBehavior(QTableWidget.SelectRows)
    tbl.setAlternatingRowColors(True)
    tbl.setSortingEnabled(True)
    tbl.setStyleSheet("font-size: 12px;")
    tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    tbl.horizontalHeader().setHighlightSections(False)
    if stretch_last:
        tbl.horizontalHeader().setStretchLastSection(True)

    lay.addWidget(t)
    lay.addWidget(tbl)
    frame.setLayout(lay)
    return frame, t, tbl


def _set_tbl(tbl: QTableWidget, rows: list[list], tooltips: list[list] | None = None):
    tbl.setSortingEnabled(False)
    tbl.setRowCount(len(rows))
    for r, cells in enumerate(rows):
        for c, val in enumerate(cells):
            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, val)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if tooltips and r < len(tooltips) and c < len(tooltips[r]):
                tip = tooltips[r][c]
                if tip:
                    item.setToolTip(tip)
            tbl.setItem(r, c, item)
    tbl.setSortingEnabled(True)


# ── Page ──────────────────────────────────────────────────────────────────────

class VisibilityPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.service = VisibilityService(
            self.app.provider_manager,
            target_brand=self.app.get_target_brand(),
        )
        self._worker: _RunWorker | None = None

        root = QVBoxLayout()
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────────
        title = QLabel("Visibility Collection")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        subtitle = QLabel(
            "Send prompt sets to AI providers and measure how brands are mentioned."
        )
        subtitle.setStyleSheet("font-size: 13px; color: #6B7280;")

        # ── Control panel ─────────────────────────────────────────────────────
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("StatCard")
        ctrl_lay = QVBoxLayout()
        ctrl_lay.setContentsMargins(14, 12, 14, 12)
        ctrl_lay.setSpacing(8)

        # ── Row 1: Prompt set selector ────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self._ps_search = QLineEdit()
        self._ps_search.setPlaceholderText("Search families…")
        self._ps_search.setToolTip("Filter the prompt family list below by name")
        self._ps_search.setFixedHeight(26)
        self._ps_search.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 4px; "
            "padding: 2px 8px; font-size: 12px; }"
        )
        self._ps_search.textChanged.connect(self._filter_family_list)

        self._ps_inner = QWidget()
        self._ps_inner.setStyleSheet("background: white;")
        self._ps_check_grid = QGridLayout()
        self._ps_check_grid.setSpacing(2)
        self._ps_check_grid.setContentsMargins(6, 4, 6, 6)
        self._ps_check_grid.setColumnStretch(0, 1)
        self._ps_check_grid.setColumnStretch(1, 1)
        self._ps_inner.setLayout(self._ps_check_grid)

        self._set_checks: dict[str, QCheckBox] = {}

        self._families_ordered = self.service.prompt_library.list_families()
        families_set = set(self._families_ordered)
        self._scenarios_ordered = sorted(
            s for s in self.service.prompt_library.list_sets()
            if s != "All Prompts" and s not in families_set
        )

        def _hdr_label(text=""):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #9CA3AF; "
                "padding: 4px 0 1px 0; background: white;"
            )
            return lbl

        # Categories — an optional tier ABOVE prompt families (assigned in
        # Knowledge > Prompt Sets) purely for selection convenience: checking
        # one checks every family in it. Families/prompts themselves are
        # never touched by this — it's just a bulk-select shortcut, not part
        # of what actually gets sent to a provider (a category name is never
        # itself a "set" run against providers, so it stays out of
        # self._set_checks). Same one-time-build-at-startup scope as
        # families/scenarios below — a category added in Knowledge while this
        # page is already open needs a restart to appear, same as a new family.
        know_repo = KnowledgeRepository()
        self._categories = know_repo.list_prompt_categories()
        self._category_families: dict[int, list[str]] = {
            cat_id: know_repo.get_families_in_category(cat_id)
            for cat_id, _name, _count in self._categories
        }
        self._category_checks: dict[int, QCheckBox] = {}
        self._cat_hdr = _hdr_label() if self._categories else None
        for cat_id, name, count in self._categories:
            cb = QCheckBox(f"{name}  ({count})")
            cb.setStyleSheet("font-size: 12px; font-weight: 600;")
            cb.setToolTip(f"Selects all {count} prompt famil{'y' if count == 1 else 'ies'} in this category")
            cb.stateChanged.connect(lambda state, cid=cat_id: self._on_category_toggled(cid, state))
            self._category_checks[cat_id] = cb

        self._fam_hdr = _hdr_label()
        self._scen_hdr = _hdr_label() if self._scenarios_ordered else None

        for set_name in self._families_ordered:
            n = self.service.prompt_library.count(set_name)
            cb = QCheckBox(f"{set_name}  ({n})")
            cb.setStyleSheet("font-size: 12px;")
            cb.stateChanged.connect(self._on_sets_changed)
            self._set_checks[set_name] = cb

        for set_name in self._scenarios_ordered:
            n = self.service.prompt_library.count(set_name)
            cb = QCheckBox(f"{set_name}  ({n})")
            cb.setStyleSheet("font-size: 12px;")
            cb.stateChanged.connect(self._on_sets_changed)
            self._set_checks[set_name] = cb

        ps_scroll = QScrollArea()
        ps_scroll.setWidget(self._ps_inner)
        ps_scroll.setWidgetResizable(True)
        ps_scroll.setFixedHeight(170)
        ps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ps_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #D1D5DB; border-radius: 4px; background: white; }"
        )

        ps_center = QVBoxLayout()
        ps_center.setSpacing(4)
        ps_center.setContentsMargins(0, 0, 0, 0)
        ps_center.addWidget(self._ps_search)
        ps_center.addWidget(ps_scroll)
        ps_center_w = QWidget()
        ps_center_w.setLayout(ps_center)

        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        btn_top = QPushButton("Top 20")
        for b in (btn_all, btn_none, btn_top):
            b.setFixedWidth(58)
            b.setStyleSheet("font-size: 11px; padding: 3px 4px;")
        btn_all.clicked.connect(self._select_all_sets)
        btn_none.clicked.connect(self._clear_sets)
        btn_top.clicked.connect(self._select_top_families)
        btn_all.setToolTip("Select every prompt family and scenario")
        btn_none.setToolTip("Clear all selections")
        btn_top.setToolTip("Select the 20 highest-influence prompt families")

        ps_ctrl = QVBoxLayout()
        ps_ctrl.setSpacing(4)
        ps_ctrl.setAlignment(Qt.AlignTop)
        ps_ctrl.addWidget(btn_all)
        ps_ctrl.addWidget(btn_none)
        ps_ctrl.addWidget(btn_top)
        ps_ctrl.addStretch()

        row1.addWidget(ps_center_w, 1)
        row1.addLayout(ps_ctrl)

        # ── Row 2: Provider checkboxes ────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl_prov = QLabel("Providers:")
        lbl_prov.setFixedWidth(88)
        row2.addWidget(lbl_prov)

        self._provider_checks: dict[str, QCheckBox] = {}
        self._provider_dots: dict[str, QLabel] = {}
        provider_keys = [k for k in self.app.provider_manager.list_providers() if k != "mock"]
        for key in provider_keys:
            has_key = bool(self.app.provider_manager.get_provider_api_key(key))
            cb = QCheckBox()
            cb.setChecked(has_key)
            self._provider_checks[key] = cb
            dot_tip = (
                "API key configured — ready to collect"
                if has_key else
                "No API key set — add one in Settings before running this provider"
            )
            dot = QLabel("⬤")
            dot.setFixedWidth(16)
            dot.setStyleSheet(
                f"color: {'#16A34A' if has_key else '#DC2626'}; font-size: 14px; padding: 0 1px;"
            )
            dot.setToolTip(dot_tip)
            cb.setToolTip(dot_tip)
            self._provider_dots[key] = dot
            name_lbl = QLabel(key.capitalize())
            name_lbl.setStyleSheet("font-size: 12px;")
            name_lbl.setCursor(Qt.PointingHandCursor)
            name_lbl.mousePressEvent = lambda _e, c=cb: c.setChecked(not c.isChecked())
            row2.addWidget(cb)
            row2.addWidget(dot)
            row2.addWidget(name_lbl)
            row2.addSpacing(10)
        row2.addStretch()

        # ── Run / Pause / Stop / progress — live in the toolbar row up top,
        # next to the Export buttons, so they stay visible even when the
        # Prompt Sets panel below is collapsed (see toolbar_row).
        self._run_btn = QPushButton("Run Visibility Collection")
        self._run_btn.setFixedWidth(200)
        self._run_btn.setStyleSheet(
            "QPushButton { background: #0B84FF; color: white; border: none; "
            "border-radius: 5px; padding: 7px 14px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #0056CC; }"
            "QPushButton:disabled { background: #9CA3AF; }"
        )
        self._run_btn.clicked.connect(self._start_run)
        self._run_btn.setToolTip(
            "Query every selected AI provider with every selected prompt and store the responses"
        )

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setFixedWidth(70)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setToolTip("Pause the running collection — resume with the same button")

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedWidth(70)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_run)
        self._stop_btn.setToolTip("Stop the collection — responses gathered so far are kept")

        self._progress = QProgressBar()
        self._progress.setFixedHeight(14)
        self._progress.setFixedWidth(140)
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: 1px solid #D1D5DB; border-radius: 6px; text-align: center; font-size: 10px; }"
            "QProgressBar::chunk { background: #0B84FF; border-radius: 5px; }"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")

        self._count_lbl = QLabel("0 sets · 0 prompts")
        self._count_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")

        # Prompt Sets is the only collapsible piece now — Providers (row2)
        # always stays visible underneath the toolbar.
        self._ps_panel = QWidget()
        self._ps_panel.setLayout(row1)

        ctrl_lay.addLayout(row2)
        ctrl_lay.addWidget(self._ps_panel)
        ctrl_frame.setLayout(ctrl_lay)

        # ── KPI cards ─────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        brand_label = self.app.get_target_brand() or "Target Brand"
        self._score_card, self._score_title, self._score_val = _stat_card(
            f"{brand_label} Visibility Score", "—%", f"% of responses mentioning {brand_label}",
            info=(
                f"(Responses mentioning {brand_label}) ÷ (ALL responses collected across "
                f"every Visibility run) × 100. This covers your FULL collection history, "
                f"unlike the Home page's Brand Mention Rate tile, which only reflects your "
                f"most recent Intelligence Analysis run's smaller sample."
            ),
        )
        self._total_card, _, self._total_val = _stat_card(
            "Responses Analyzed", "—", "across all collected runs",
            info="Total AI responses stored across every Visibility collection run, all providers combined.",
        )
        self._top_card, self._top_title, self._top_val = _stat_card(
            "Visibility Mention Rank", "—", "across all visibility collection responses",
            info=(
                "Your target brand's position when ALL tracked active brands are ranked by "
                "mention count, highest first. The \"of N\" denominator is the full tracked "
                "brand count, not just brands that happen to have a mention — a brand with "
                "zero mentions still counts toward the total, ranked at the bottom."
            ),
        )
        self._last_card, _, self._last_val = _stat_card(
            "Last Collection", "—", "most recent visibility run",
            info="Date and time of the most recently completed Visibility collection run.",
        )
        self._last_val.setStyleSheet("QLabel#CardValue { font-size: 14px; font-weight: 600; }")
        for card in (self._score_card, self._total_card, self._top_card, self._last_card):
            kpi_row.addWidget(card)

        kpi_widget = QWidget()
        kpi_widget.setLayout(kpi_row)

        # ── Content panels ────────────────────────────────────────────────────

        # Overview tab panels
        self._runs_frame, _, self._runs_tbl = _table_section(
            "Recent Runs",
            ["Date", "Provider", "Families", "Results"],
            stretch_last=False,
        )
        self._runs_tbl.setColumnWidth(0, 130)
        self._runs_tbl.setColumnWidth(1, 90)
        self._runs_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._runs_tbl.setColumnWidth(3, 90)

        self._responses_frame, self._responses_body = _section("Latest Run Responses")

        # Brands tab — sortable tables instead of text areas
        self._pos_frame, _, self._pos_tbl = _table_section(
            "Brand Position Share",
            ["Position", "Brand", "Mentions", "Share %"],
            stretch_last=False,
        )
        self._pos_tbl.setColumnWidth(0, 70)
        self._pos_tbl.setColumnWidth(2, 70)
        self._pos_tbl.setColumnWidth(3, 70)
        self._pos_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._pos_tbl.horizontalHeaderItem(0).setToolTip(
            "The order this brand was named in a response — Position 1 means it was the "
            "FIRST brand mentioned (the closest proxy to being AI's top recommendation)."
        )
        self._pos_tbl.horizontalHeaderItem(3).setToolTip(
            "% of ALL responses where this brand appeared at exactly this position. Different "
            "from Visibility Score, which counts a mention anywhere in the response — a brand "
            "can have a high Visibility Score while rarely being mentioned first."
        )

        self._brand_frame, _, self._brand_tbl = _table_section(
            "Brand Mentions by Provider",
            ["Provider", "Brand", "Mentions"],
            stretch_last=False,
        )
        self._brand_tbl.setColumnWidth(0, 110)
        self._brand_tbl.setColumnWidth(2, 80)
        self._brand_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self._sentiment_frame, _, self._sentiment_tbl = _table_section(
            "Brand Sentiment & Recommendations",
            ["Brand", "Mentions", "Recommended", "Recommended %", "Negative", "Negative %"],
            stretch_last=False,
        )
        self._sentiment_tbl.setColumnWidth(1, 80)
        self._sentiment_tbl.setColumnWidth(2, 90)
        self._sentiment_tbl.setColumnWidth(3, 100)
        self._sentiment_tbl.setColumnWidth(4, 80)
        self._sentiment_tbl.setColumnWidth(5, 90)
        self._sentiment_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._sentiment_tbl.setToolTip(
            "Recommended = responses where AI actively endorsed this brand (\"I recommend "
            "the...\", \"the best choice would be...\"), not just mentioned it alongside others. "
            "Negative = responses where this brand was mentioned in an unfavorable or "
            "comparative-losing context (e.g. \"unlike Firman, Honda includes...\"). Both "
            "percentages are of that brand's OWN mentions, not of all responses."
        )
        # Per-column header tooltips (#49) — more discoverable than the whole-table
        # tooltip above, since hovering a column HEADER is a more natural way to
        # ask "what does this column mean" than hovering blank table space.
        self._sentiment_tbl.horizontalHeaderItem(1).setToolTip(
            "Number of responses mentioning this brand at all (positive, neutral, or negative)."
        )
        self._sentiment_tbl.horizontalHeaderItem(2).setToolTip(
            "Number of THOSE mentions where AI actively recommended this brand — e.g. \"I'd "
            "recommend the...\" or \"the best choice would be...\" — not just listed it among "
            "other options."
        )
        self._sentiment_tbl.horizontalHeaderItem(3).setToolTip(
            "Recommended ÷ that brand's OWN Mentions column (not ÷ all responses). This answers "
            "\"of the times AI brings this brand up, how often does it actually endorse it\" — "
            "distinct from Visibility Score, which only measures being mentioned at all."
        )
        self._sentiment_tbl.horizontalHeaderItem(4).setToolTip(
            "Number of THOSE mentions that were negative or unfavorable — e.g. the brand lost "
            "a direct comparison or was described critically."
        )
        self._sentiment_tbl.horizontalHeaderItem(5).setToolTip(
            "Negative ÷ that brand's OWN Mentions column (not ÷ all responses). This answers "
            "\"of the times AI brings this brand up, how often is it unfavorable\" — a brand "
            "mentioned rarely but always negatively will show a high % here even though its "
            "overall Visibility Score is low."
        )

        # Features tab — two tables side by side
        self._feat_total_frame, _, self._feat_total_tbl = _table_section(
            "Feature Mentions",
            ["Feature", "Total"],
            stretch_last=False,
        )
        self._feat_total_tbl.setColumnWidth(1, 60)
        self._feat_total_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        self._feat_brand_frame, _, self._feat_brand_tbl = _table_section(
            "Feature Mentions by Brand",
            ["Feature", "Brand", "Mentions"],
            stretch_last=False,
        )
        self._feat_brand_tbl.setColumnWidth(2, 70)
        self._feat_brand_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._feat_brand_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # Channels tab
        self._channel_frame, _, self._channel_tbl = _table_section(
            "Channel Intelligence",
            ["Channel", "Mentions", "Top Brands"],
        )
        self._channel_tbl.setColumnWidth(0, 160)
        self._channel_tbl.setColumnWidth(1, 70)

        target_label = self.app.get_target_brand() or "Target Brand"
        self._gap_frame, self._gap_title, self._gap_tbl = _table_section(
            f"{target_label} Channel Gaps  —  channels where competitors have stronger reach",
            ["Channel", target_label, "Top Competitor", "Their Count"],
            stretch_last=False,
        )
        self._gap_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._gap_tbl.setColumnWidth(1, 70)
        self._gap_tbl.setColumnWidth(2, 130)
        self._gap_tbl.setColumnWidth(3, 80)

        # ── Tabbed layout ─────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; padding-top: 8px; }
            QTabBar::tab {
                padding: 7px 20px; font-size: 12px; font-weight: 500;
                border: none; border-bottom: 2px solid transparent;
                background: transparent; color: #6B7280; margin-right: 4px;
            }
            QTabBar::tab:hover { color: #111827; }
            QTabBar::tab:selected { color: #0B84FF; border-bottom: 2px solid #0B84FF; }
        """)

        # Tab 1 — Overview
        overview = QWidget()
        ov_split = QSplitter(Qt.Horizontal)
        ov_split.addWidget(self._runs_frame)
        ov_split.addWidget(self._responses_frame)
        ov_split.setSizes([500, 500])
        ov_lay = QVBoxLayout(overview)
        ov_lay.setContentsMargins(0, 0, 0, 0)
        ov_lay.addWidget(ov_split)

        # Tab 2 — Brands: position + provider tables on top, sentiment below
        brands_tab = QWidget()
        br_split = QSplitter(Qt.Horizontal)
        br_split.addWidget(self._pos_frame)
        br_split.addWidget(self._brand_frame)
        br_split.setSizes([500, 500])
        br_lay = QVBoxLayout(brands_tab)
        br_lay.setContentsMargins(0, 0, 0, 0)
        br_lay.setSpacing(8)
        br_lay.addWidget(br_split, 2)
        br_lay.addWidget(self._sentiment_frame, 1)

        # Tab 3 — Features: totals + by-brand side by side
        features_tab = QWidget()
        ft_split = QSplitter(Qt.Horizontal)
        ft_split.addWidget(self._feat_total_frame)
        ft_split.addWidget(self._feat_brand_frame)
        ft_split.setSizes([340, 660])
        ft_lay = QVBoxLayout(features_tab)
        ft_lay.setContentsMargins(0, 0, 0, 0)
        ft_lay.addWidget(ft_split)

        # Tab 4 — Channels
        channels_tab = QWidget()
        ch_lay = QHBoxLayout(channels_tab)
        ch_lay.setContentsMargins(0, 0, 0, 0)
        ch_lay.setSpacing(10)
        ch_lay.addWidget(self._channel_frame, 1)
        ch_lay.addWidget(self._gap_frame, 1)

        # Tab 5 — Raw Data
        raw_tab = QWidget()
        raw_lay = QVBoxLayout(raw_tab)
        raw_lay.setContentsMargins(0, 4, 0, 0)
        raw_lay.setSpacing(6)

        # Compact KPI row (single-line tiles)
        raw_kpi_row = QHBoxLayout()
        raw_kpi_row.setSpacing(8)
        self._raw_total_card, _, self._raw_total_val = _compact_card("Total Responses", "—")
        self._raw_prov_card,  _, self._raw_prov_val  = _compact_card("Providers", "—")
        self._raw_runs_card,  _, self._raw_runs_val  = _compact_card("Runs", "—")
        self._raw_fam_card,   _, self._raw_fam_val   = _compact_card("Prompt Families", "—")
        self._raw_flagged_card, _, self._raw_flagged_val = _compact_card("Flagged for Review", "—")
        for card in (self._raw_total_card, self._raw_prov_card,
                     self._raw_runs_card, self._raw_fam_card, self._raw_flagged_card):
            raw_kpi_row.addWidget(card)
        raw_kpi_widget = QWidget()
        raw_kpi_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        raw_kpi_widget.setLayout(raw_kpi_row)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_lbl = QLabel("Search:")
        filter_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._raw_search = QLineEdit()
        self._raw_search.setPlaceholderText("Filter by keyword in prompt, response, or family…")
        self._raw_search.textChanged.connect(self._filter_raw_data)
        self._raw_search.setToolTip("Search the raw response text below by keyword")
        prov_lbl = QLabel("Provider:")
        prov_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._raw_prov_filter = QComboBox()
        self._raw_prov_filter.setFixedWidth(160)
        self._raw_prov_filter.addItem("All Providers")
        self._raw_prov_filter.currentTextChanged.connect(self._filter_raw_data)
        self._raw_prov_filter.setToolTip("Show responses from only one AI provider")
        review_lbl = QLabel("Review:")
        review_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._raw_review_filter = QComboBox()
        self._raw_review_filter.setFixedWidth(130)
        self._raw_review_filter.addItems(["All", "Unreviewed", "Flagged", "Reviewed"])
        self._raw_review_filter.currentTextChanged.connect(self._filter_raw_data)
        self._raw_review_filter.setToolTip(
            "Show only responses with a given review status — useful for working "
            "through everything flagged for a second look."
        )
        self._raw_count_lbl = QLabel("")
        self._raw_count_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._raw_count_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._raw_search, 1)
        filter_row.addWidget(prov_lbl)
        filter_row.addWidget(self._raw_prov_filter)
        filter_row.addWidget(review_lbl)
        filter_row.addWidget(self._raw_review_filter)
        filter_row.addWidget(self._raw_count_lbl)
        filter_widget = QWidget()
        filter_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_widget.setLayout(filter_row)

        # Response table — Family now shows the per-response family name
        self._raw_frame, _, self._raw_tbl = _table_section(
            "Responses",
            ["Date", "Provider", "Family", "Prompt", "Brands Mentioned", "Review", "Response Preview"],
            stretch_last=True,
        )
        self._raw_tbl.setColumnWidth(0, 120)
        self._raw_tbl.setColumnWidth(1, 90)
        self._raw_tbl.setColumnWidth(2, 150)
        self._raw_tbl.setColumnWidth(3, 170)
        self._raw_tbl.setColumnWidth(4, 150)
        self._raw_tbl.setColumnWidth(5, 90)
        self._raw_tbl.currentCellChanged.connect(lambda row, *_: self._on_raw_row_selected(row))

        self._raw_detail_frame, self._raw_detail_body = _section("Full Response")
        self._raw_detail_body.setReadOnly(True)

        raw_split = QSplitter(Qt.Vertical)
        raw_split.addWidget(self._raw_frame)
        raw_split.addWidget(self._raw_detail_frame)
        raw_split.setSizes([420, 200])

        # Review action bar — acts on the currently selected row above.
        review_bar = QHBoxLayout()
        review_bar.setSpacing(8)
        self._raw_flag_btn = QPushButton("🚩 Flag for Review")
        self._raw_reviewed_btn = QPushButton("✓ Mark Reviewed")
        self._raw_clear_review_btn = QPushButton("↺ Clear Review Status")
        self._raw_flag_btn.clicked.connect(self._flag_raw_response)
        self._raw_reviewed_btn.clicked.connect(self._mark_raw_response_reviewed)
        self._raw_clear_review_btn.clicked.connect(self._clear_raw_response_review)
        self._raw_flag_btn.setToolTip(
            "Flag this response if its brand/sentiment extraction looks wrong — "
            "builds a reviewable audit trail instead of silently trusting automated "
            "extraction forever."
        )
        self._raw_reviewed_btn.setToolTip("Mark this response as manually reviewed and confirmed correct.")
        self._raw_clear_review_btn.setToolTip("Clear this response's review status back to unreviewed.")
        for btn in (self._raw_flag_btn, self._raw_reviewed_btn, self._raw_clear_review_btn):
            btn.setEnabled(False)
            review_bar.addWidget(btn)
        review_bar.addStretch()
        review_bar_widget = QWidget()
        review_bar_widget.setLayout(review_bar)

        raw_lay.addWidget(raw_kpi_widget)
        raw_lay.addWidget(filter_widget)
        raw_lay.addWidget(raw_split, 1)
        raw_lay.addWidget(review_bar_widget)

        self._raw_page_rows: list = []  # current page (≤ RAW_PAGE_SIZE rows) for row-click detail
        self._RAW_PAGE_SIZE = 2000

        tabs.addTab(overview,      "Overview")
        tabs.addTab(brands_tab,    "Brands")
        tabs.addTab(features_tab,  "Features")
        tabs.addTab(channels_tab,  "Channels")
        tabs.addTab(raw_tab,       "Raw Data")

        self._ctrl_frame = ctrl_frame

        self._collapse_btn = QPushButton("▲  Hide Prompt Sets")
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setFixedHeight(28)
        self._collapse_btn.setStyleSheet(
            "QPushButton { text-align: left; font-size: 12px; font-weight: 600; "
            "color: #374151; background: #F3F4F6; border: 1px solid #D1D5DB; "
            "border-radius: 5px; padding: 4px 12px; }"
            "QPushButton:hover { background: #E5E7EB; color: #0B84FF; border-color: #0B84FF; }"
            "QPushButton:pressed { background: #D1D5DB; }"
        )
        self._collapse_btn.clicked.connect(self._toggle_ctrl_panel)
        self._collapse_btn.setToolTip("Show or hide the prompt family/scenario selection list")

        self._export_pdf_btn = QPushButton("Export PDF Report")
        self._export_pdf_btn.setFixedHeight(28)
        self._export_pdf_btn.setCursor(Qt.PointingHandCursor)
        self._export_pdf_btn.setStyleSheet(
            "QPushButton { font-size: 12px; font-weight: 600; color: white; "
            "background: #0B84FF; border: none; border-radius: 5px; padding: 4px 14px; }"
            "QPushButton:hover { background: #0056CC; }"
            "QPushButton:pressed { background: #003D99; }"
            "QPushButton:disabled { background: #9CA3AF; }"
        )
        self._export_pdf_btn.clicked.connect(self._export_pdf)
        self._export_pdf_btn.setToolTip("Generate a formatted PDF report from the current analytics")

        self._export_excel_btn = QPushButton("Export Excel")
        self._export_excel_btn.setFixedHeight(28)
        self._export_excel_btn.setCursor(Qt.PointingHandCursor)
        self._export_excel_btn.setStyleSheet(
            "QPushButton { font-size: 12px; font-weight: 600; color: #0B84FF; "
            "background: white; border: 1.5px solid #0B84FF; border-radius: 5px; padding: 4px 14px; }"
            "QPushButton:hover { background: #EFF6FF; }"
            "QPushButton:pressed { background: #DBEAFE; }"
            "QPushButton:disabled { color: #9CA3AF; border-color: #9CA3AF; }"
        )
        self._export_excel_btn.clicked.connect(self._export_excel)
        self._export_excel_btn.setToolTip("Export all analytics sheets and raw responses to .xlsx")

        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(8)
        toolbar_row.addWidget(self._collapse_btn)
        toolbar_row.addSpacing(4)
        toolbar_row.addWidget(self._run_btn)
        toolbar_row.addWidget(self._pause_btn)
        toolbar_row.addWidget(self._stop_btn)
        toolbar_row.addWidget(self._progress)
        toolbar_row.addWidget(self._status_lbl)
        toolbar_row.addWidget(self._count_lbl)
        toolbar_row.addStretch()
        toolbar_row.addWidget(self._export_excel_btn)
        toolbar_row.addWidget(self._export_pdf_btn)
        toolbar_widget = QWidget()
        toolbar_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_widget.setLayout(toolbar_row)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(toolbar_widget)
        root.addWidget(self._ctrl_frame)
        root.addWidget(kpi_widget)
        root.addWidget(tabs, 1)
        self.setLayout(root)

        self._rebuild_check_grid("")
        self._on_sets_changed()
        self.refresh()

    # ── Prompt set helpers ────────────────────────────────────────────────────

    def _on_sets_changed(self):
        prompts, _, _fam = self._get_selected_prompts()
        n_sets = sum(1 for cb in self._set_checks.values() if cb.isChecked())
        self._count_lbl.setText(f"{n_sets} set{'s' if n_sets != 1 else ''} · {len(prompts)} prompts")

    def _on_category_toggled(self, category_id: int, _state: int):
        checked = self._category_checks[category_id].isChecked()
        for family_name in self._category_families.get(category_id, []):
            cb = self._set_checks.get(family_name)
            if cb is not None:
                cb.setChecked(checked)

    def _select_all_sets(self):
        for cb in self._set_checks.values():
            cb.setChecked(True)

    def _clear_sets(self):
        for cb in self._set_checks.values():
            cb.setChecked(False)

    def _select_top_families(self, n: int = 20):
        top = set(self.service.prompt_library.list_families_by_influence()[:n])
        for name, cb in self._set_checks.items():
            cb.setChecked(name in top)

    def _filter_family_list(self, text: str):
        self._rebuild_check_grid(text)

    def _rebuild_check_grid(self, query: str):
        query = query.lower().strip()
        while self._ps_check_grid.count():
            self._ps_check_grid.takeAt(0)

        row = 0
        if self._cat_hdr is not None:
            self._cat_hdr.setText(f"CATEGORIES  ({len(self._categories)})")
            self._ps_check_grid.addWidget(self._cat_hdr, row, 0, 1, 2)
            row += 1
            for i, (cat_id, _name, _count) in enumerate(self._categories):
                self._ps_check_grid.addWidget(self._category_checks[cat_id], row + i // 2, i % 2)
            row += (len(self._categories) + 1) // 2

        vis_fams = [n for n in self._families_ordered if not query or query in n.lower()]
        fam_count = f"{len(vis_fams)}" + (f"/{len(self._families_ordered)}" if query else "")
        self._fam_hdr.setText(f"PROMPT FAMILIES  ({fam_count})")
        self._ps_check_grid.addWidget(self._fam_hdr, row, 0, 1, 2)
        row += 1
        for i, name in enumerate(vis_fams):
            self._ps_check_grid.addWidget(self._set_checks[name], row + i // 2, i % 2)
        if vis_fams:
            row += (len(vis_fams) + 1) // 2

        if self._scen_hdr is not None:
            vis_scens = [n for n in self._scenarios_ordered if not query or query in n.lower()]
            if vis_scens:
                self._scen_hdr.setText(f"SCENARIOS  ({len(vis_scens)})")
                self._ps_check_grid.addWidget(self._scen_hdr, row, 0, 1, 2)
                row += 1
                for i, name in enumerate(vis_scens):
                    self._ps_check_grid.addWidget(self._set_checks[name], row + i // 2, i % 2)
                row += (len(vis_scens) + 1) // 2

        self._ps_check_grid.setRowStretch(row, 1)
        self._ps_inner.adjustSize()

    def _toggle_ctrl_panel(self):
        visible = not self._ps_panel.isVisible()
        self._ps_panel.setVisible(visible)
        self._collapse_btn.setText("▲  Hide Prompt Sets" if visible else "▼  Show Prompt Sets")

    def _export_pdf(self):
        default_name = (
            f"Atlas_Visibility_Report_"
            f"{self.app.get_target_brand() or 'Report'}_"
            f"{__import__('datetime').date.today().isoformat()}.pdf"
        ).replace(" ", "_")
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        default_path = os.path.join(downloads, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", default_path,
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return

        self._export_pdf_btn.setEnabled(False)
        self._export_pdf_btn.setText("Generating…")

        def _generate():
            try:
                from backend.reports.pdf_report import VisibilityPDFReport
                analytics = self.service.analytics_summary()
                runs      = self.service.list_runs()
                stats     = self.service.repository.count_stats()
                rpt = VisibilityPDFReport(
                    analytics=analytics,
                    runs=runs,
                    stats=stats,
                    target_brand=self.app.get_target_brand(),
                )
                rpt.generate(path)
                return path, None
            except Exception as exc:
                return None, str(exc)

        def _done(result):
            out_path, err = result
            self._export_pdf_btn.setEnabled(True)
            self._export_pdf_btn.setText("Export PDF Report")
            if err:
                QMessageBox.critical(self, "Export Failed", f"Could not generate PDF:\n\n{err}")
            else:
                reply = QMessageBox.information(
                    self, "Report Ready",
                    f"PDF saved to:\n{out_path}",
                    QMessageBox.Open | QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                if reply == QMessageBox.Open:
                    os.startfile(out_path)

        worker = _PDFWorker(_generate)
        worker.finished.connect(_done)
        worker.start()
        self._pdf_worker = worker  # keep reference

    def _export_excel(self):
        default_name = (
            f"Atlas_Visibility_Data_"
            f"{self.app.get_target_brand() or 'Report'}_"
            f"{__import__('datetime').date.today().isoformat()}.xlsx"
        ).replace(" ", "_")
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        default_path = os.path.join(downloads, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel Report", default_path,
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if not path:
            return

        self._export_excel_btn.setEnabled(False)
        self._export_excel_btn.setText("Generating…")

        def _generate():
            try:
                from backend.reports.excel_report import VisibilityExcelReport
                analytics = self.service.analytics_summary()
                runs      = self.service.list_runs()
                stats     = self.service.repository.count_stats()
                raw       = self.service.repository.list_responses()
                rpt = VisibilityExcelReport(
                    analytics=analytics,
                    runs=runs,
                    stats=stats,
                    target_brand=self.app.get_target_brand(),
                    raw_responses=raw,
                )
                rpt.generate(path)
                return path, None
            except Exception as exc:
                return None, str(exc)

        def _done(result):
            out_path, err = result
            self._export_excel_btn.setEnabled(True)
            self._export_excel_btn.setText("Export Excel")
            if err:
                QMessageBox.critical(self, "Export Failed",
                                     f"Could not generate Excel file:\n\n{err}")
            else:
                reply = QMessageBox.information(
                    self, "Export Ready",
                    f"Excel file saved to:\n{out_path}",
                    QMessageBox.Open | QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                if reply == QMessageBox.Open:
                    os.startfile(out_path)

        worker = _PDFWorker(_generate)
        worker.finished.connect(_done)
        worker.start()
        self._excel_worker = worker  # keep reference

    def _get_selected_prompts(self) -> tuple[list, str, dict]:
        """Returns (prompts, label, prompt_families).
        label is comma-separated family names.
        prompt_families maps prompt_text → family_name.
        """
        selected = [name for name, cb in self._set_checks.items() if cb.isChecked()]
        if not selected:
            return [], "", {}
        prompts = []
        prompt_families: dict[str, str] = {}
        seen: set[str] = set()
        for name in selected:
            for p in self.service.prompt_library.get(name):
                if p not in seen:
                    seen.add(p)
                    prompts.append(p)
                    prompt_families[p] = name
        label = selected[0] if len(selected) == 1 else ", ".join(selected)
        return prompts, label, prompt_families

    def _checked_providers(self) -> list:
        return [k for k, cb in self._provider_checks.items() if cb.isChecked()]

    # ── Run / Pause / Stop ────────────────────────────────────────────────────

    def _start_run(self):
        providers = self._checked_providers()
        if not providers:
            QMessageBox.warning(self, "No Provider", "Check at least one AI provider to run against.")
            return

        prompts, label, prompt_families = self._get_selected_prompts()
        if not prompts:
            QMessageBox.warning(self, "No Prompts", "Select at least one prompt set.")
            return

        n_prompts = len(prompts)
        total = n_prompts * len(providers)

        if total > 30:
            msg = (
                f"<b>{total} API calls</b> will be made "
                f"({n_prompts} prompts × {len(providers)} provider{'s' if len(providers) > 1 else ''}).<br><br>"
                "Each call costs money. Large runs can take <b>10–90 minutes</b>.<br>"
                "Make sure you have API credits and budget for this run."
            )
            reply = QMessageBox.question(
                self, "Confirm Run", msg,
                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel,
            )
            if reply != QMessageBox.Ok:
                return

        self._run_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("Pause")
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, total)
        self._progress.setValue(0)
        self._status_lbl.setText("Starting…")

        self._worker = _RunWorker(self.service, prompts, label, providers, prompt_families)
        self._worker.progress.connect(self._on_progress)
        self._worker.run_done.connect(self._on_run_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error.connect(self._on_error)
        # #56: a long collection (hundreds+ of prompts) can outlast Windows'
        # idle-sleep timer if left unattended — confirmed this isn't
        # hypothetical, the v0.9.2 build hit the identical failure mode.
        # Released in _on_all_done(), which fires exactly once at the true
        # end of the worker's run() regardless of success/error/cancel — see
        # that method's comment for why no other release hook is needed.
        prevent_sleep()
        self._worker.start()

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._worker.is_paused:
            self._worker.resume()
            self._pause_btn.setText("Pause")
            self._status_lbl.setText("Resumed…")
        else:
            self._worker.pause()
            self._pause_btn.setText("Resume")
            self._status_lbl.setText("Paused — click Resume to continue.")

    def _stop_run(self):
        if self._worker:
            self._worker.cancel()
        self._status_lbl.setText("Stopping after current prompt…")
        self._stop_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int):
        self._progress.setValue(done)
        self._status_lbl.setText(f"{done}/{total} prompts")

    def _on_run_done(self, result: dict):
        run = result["run"]
        err = getattr(run, "error_count", 0)
        parts = [f"{run.response_count} ok"]
        if err:
            parts.append(f"{err} failed (not stored)")
        self._status_lbl.setText(
            f"{run.provider} — {', '.join(parts)} in {run.duration_seconds:.1f}s"
        )
        self.refresh()

    def _on_all_done(self):
        # #56: always fires exactly once here regardless of whether the run
        # finished normally, hit a per-provider error (those go through
        # _on_error but don't stop the ThreadPoolExecutor loop early), or was
        # cancelled via _stop_run — so this is the one correct place to
        # release the sleep-prevention requested in _start_run().
        allow_sleep()
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Pause")
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_lbl.setText("Done.")
        self.refresh()

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"Error: {msg}")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh_provider_status(self):
        """
        Re-check each provider's API key and update its status dot/tooltip.
        has_key was previously only computed once at page construction, so a
        key added in Settings after startup never changed the dot from red to
        green until the app was restarted (#47). Called from main_window's
        nav-change handler whenever this page becomes visible.
        """
        for key, dot in self._provider_dots.items():
            has_key = bool(self.app.provider_manager.get_provider_api_key(key))
            dot_tip = (
                "API key configured — ready to collect"
                if has_key else
                "No API key set — add one in Settings before running this provider"
            )
            dot.setStyleSheet(
                f"color: {'#16A34A' if has_key else '#DC2626'}; font-size: 14px; padding: 0 1px;"
            )
            dot.setToolTip(dot_tip)
            cb = self._provider_checks.get(key)
            if cb:
                cb.setToolTip(dot_tip)

    def refresh(self):
        summary = self.service.analytics_summary()
        runs = self.service.list_runs() or []

        brand_label = self.app.get_target_brand() or "Target Brand"
        score = summary["target_visibility_score"]
        total = summary["total_responses"]
        brand_counts = summary.get("brand_counts", {})

        # Score tile
        self._score_title.setText(f"{brand_label} Visibility Score")
        self._score_val.setText(f"{score}%")

        # Responses analyzed
        self._total_val.setText(str(total))

        # Brand Mention Rank — denominator is ALL tracked brands (#48), not just
        # brands with ≥1 mention. A brand with 0 mentions can only rank at or
        # below one with actual mentions, so the numeric rank is unaffected;
        # only the "of N" denominator changes, from a misleadingly small
        # mentioned-only count to the true size of the tracked competitive set.
        sorted_brands = sorted(brand_counts.items(), key=lambda x: -x[1])
        rank = next((i + 1 for i, (b, _) in enumerate(sorted_brands) if b == brand_label), None)
        total_tracked = summary.get("total_tracked_brands", len(sorted_brands))
        if rank:
            self._top_title.setText(f"Visibility Mention Rank  —  {brand_label}")
            self._top_val.setText(f"#{rank} of {total_tracked}")
        else:
            self._top_title.setText("Visibility Mention Rank")
            self._top_val.setText("Unranked")

        # Last Collection
        if runs:
            dt = runs[0][4]
            self._last_val.setText(f"{dt[:10]}\n{dt[11:16]}")
        else:
            self._last_val.setText("Never")

        # ── Brand Position Share → sortable table ─────────────────────────────
        pos_counts = summary.get("brand_position_counts", {})
        pos_shares = summary.get("brand_position_share", {})
        pos_rows = []
        for pos in sorted(pos_counts.keys()):
            for brand, count in sorted(pos_counts[pos].items(), key=lambda x: -x[1]):
                share = pos_shares.get(pos, {}).get(brand, 0)
                pos_rows.append([pos, brand, count, f"{share}%"])
        _set_tbl(self._pos_tbl, pos_rows)

        # ── Brand Mentions by Provider → sortable table ───────────────────────
        prov_brand = summary.get("provider_brand_counts", {})
        prov_rows = []
        for provider, brands in sorted(prov_brand.items()):
            for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                prov_rows.append([provider, brand, count])
        _set_tbl(self._brand_tbl, prov_rows)

        # ── Brand Sentiment & Recommendations → sortable table ────────────────
        negative_counts = summary.get("negative_brand_counts", {})
        negative_rates = summary.get("brand_negative_rate", {})
        recommended_counts = summary.get("recommended_brand_counts", {})
        recommended_rates = summary.get("brand_recommendation_rate", {})
        sentiment_rows = [
            [
                brand, count,
                recommended_counts.get(brand, 0), f"{recommended_rates.get(brand, 0)}%",
                negative_counts.get(brand, 0), f"{negative_rates.get(brand, 0)}%",
            ]
            for brand, count in sorted(brand_counts.items(), key=lambda x: -x[1])
        ]
        _set_tbl(self._sentiment_tbl, sentiment_rows)

        # ── Feature Mentions total ────────────────────────────────────────────
        feature_counts = summary.get("feature_counts", {})
        feat_rows = [
            [f, c]
            for f, c in sorted(feature_counts.items(), key=lambda x: -x[1])
        ]
        _set_tbl(self._feat_total_tbl, feat_rows)

        # ── Feature Mentions by Brand ─────────────────────────────────────────
        feat_brand = summary.get("feature_brand_counts", {})
        fb_rows = []
        for feature, brands in sorted(feat_brand.items()):
            for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                fb_rows.append([feature, brand, count])
        _set_tbl(self._feat_brand_tbl, fb_rows)

        # ── Recent Runs table ─────────────────────────────────────────────────
        # Columns: Date | Provider | Families | Results
        # Families: first name + "+N more" if multiple; full list as tooltip
        run_rows = []
        run_tips = []
        for r in runs[:25]:
            prompt_set = r[3] or ""
            err_count = r[9] if len(r) > 9 else 0
            ok_count = r[7]

            if ", " in prompt_set:
                parts = [p.strip() for p in prompt_set.split(",")]
                fam_display = f"{parts[0]}  +{len(parts) - 1} more"
                fam_tip = "\n".join(parts)
            else:
                fam_display = prompt_set
                fam_tip = ""

            results = f"{ok_count} ok"
            if err_count:
                results += f",  {err_count} failed"

            run_rows.append([r[4][:16], r[1], fam_display, results])
            run_tips.append(["", "", fam_tip, ""])
        _set_tbl(self._runs_tbl, run_rows, tooltips=run_tips)

        # ── Latest Run Responses ──────────────────────────────────────────────
        # Only successful responses are stored; show provider + error summary in header
        latest_id = runs[0][0] if runs else None
        resp_text = ""
        if latest_id:
            latest_run = runs[0]
            err_count = latest_run[9] if len(latest_run) > 9 else 0
            provider = latest_run[1]
            ok_count = latest_run[7]
            header_line = f"✓ {provider}  —  {ok_count} successful response(s)"
            if err_count:
                header_line += f"  |  {err_count} API error(s) filtered out"
            resp_text = header_line + "\n" + ("─" * 60) + "\n\n"

            for r in self.service.get_responses_for_run(latest_id):
                family = r[7] if len(r) > 7 and r[7] else ""
                family_str = f"  [{family}]" if family else ""
                resp_text += f"Prompt{family_str}: {r[4]}\nResponse: {r[5][:400]}…\n{'─'*60}\n\n"
        else:
            resp_text = "No responses available."
        self._responses_body.setPlainText(resp_text)

        # ── Channel Intelligence ──────────────────────────────────────────────
        channel_counts = summary.get("channel_counts", {})
        channel_brand_counts = summary.get("channel_brand_counts", {})
        ch_rows = []
        for ch, count in sorted(channel_counts.items(), key=lambda x: -x[1]):
            top = channel_brand_counts.get(ch, {})
            brand_str = ", ".join(
                f"{b} ({c})" for b, c in sorted(top.items(), key=lambda x: -x[1])[:4]
            )
            ch_rows.append([ch, count, brand_str])
        _set_tbl(self._channel_tbl, ch_rows)

        # ── Channel Gaps ──────────────────────────────────────────────────────
        gap_data = summary.get("firman_channel_gap", [])
        self._gap_title.setText(
            f"{brand_label} Channel Gaps  —  channels where competitors have stronger reach"
        )
        self._gap_tbl.setHorizontalHeaderLabels(
            ["Channel", brand_label, "Top Competitor", "Their Count"]
        )
        _set_tbl(self._gap_tbl, [
            [g["channel"], g["firman_count"] or 0, g["top_competitor"], g["top_competitor_count"]]
            for g in gap_data[:20]
        ])

        self._refresh_raw_data()

    # ── Raw Data tab ──────────────────────────────────────────────────────────

    def _refresh_raw_data(self):
        stats = self.service.repository.count_stats()
        self._raw_total_val.setText(str(stats["total"]))
        self._raw_prov_val.setText(str(stats["providers"]))
        self._raw_runs_val.setText(str(stats["runs"]))
        self._raw_fam_val.setText(str(stats["families"]))
        self._raw_flagged_val.setText(str(stats["flagged"]))

        # Rebuild provider filter dropdown without triggering a re-query
        current_prov = self._raw_prov_filter.currentText()
        self._raw_prov_filter.blockSignals(True)
        self._raw_prov_filter.clear()
        self._raw_prov_filter.addItem("All Providers")
        with self.service.repository.connect() as con:
            for (p,) in con.execute(
                "SELECT DISTINCT provider FROM visibility_responses WHERE provider != '' ORDER BY provider"
            ).fetchall():
                self._raw_prov_filter.addItem(p)
        idx = self._raw_prov_filter.findText(current_prov)
        self._raw_prov_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self._raw_prov_filter.blockSignals(False)

        self._filter_raw_data()

    _REVIEW_FILTER_VALUES = {
        "All": "", "Unreviewed": "unreviewed", "Flagged": "flagged", "Reviewed": "reviewed",
    }
    _REVIEW_DISPLAY = {"flagged": "🚩 Flagged", "reviewed": "✓ Reviewed"}

    def _filter_raw_data(self):
        search = self._raw_search.text().strip()
        prov   = self._raw_prov_filter.currentText()
        prov_filter = "" if prov == "All Providers" else prov
        review_filter = self._REVIEW_FILTER_VALUES.get(self._raw_review_filter.currentText(), "")

        total_matching = self.service.repository.count_responses_filtered(
            search=search, provider=prov_filter, review_status=review_filter
        )
        rows = self.service.repository.list_responses(
            limit=self._RAW_PAGE_SIZE, offset=0,
            search=search, provider=prov_filter, review_status=review_filter,
        )

        # Tuple: (id, run_id, provider, model, prompt, response, collected_at,
        #         family_display, review_status, review_note)
        self._raw_page_rows = [
            (
                r[0],
                (r[6] or "")[:16],
                r[2] or "",
                r[7] or "—",
                r[4] or "",
                r[5] or "",
                ", ".join(self.service.analytics.detect_mentioned_brands(r[5] or "")),
                r[8] or "",
                r[9] or "",
            )
            for r in rows
        ]

        showing = len(self._raw_page_rows)
        if total_matching > showing:
            self._raw_count_lbl.setText(f"Showing {showing:,} of {total_matching:,}")
        elif total_matching > 0:
            self._raw_count_lbl.setText(f"{total_matching:,} result{'s' if total_matching != 1 else ''}")
        else:
            self._raw_count_lbl.setText("No results")

        self._raw_tbl.setSortingEnabled(False)
        self._raw_tbl.setRowCount(showing)
        for row_idx, (_id, date, provider, family, prompt, response,
                       brands, review_status, _note) in enumerate(self._raw_page_rows):
            review_display = self._REVIEW_DISPLAY.get(review_status, "—")
            cells = (date, provider, family, prompt[:120], brands or "—", review_display, response[:120])
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._raw_tbl.setItem(row_idx, col, item)
        self._raw_tbl.setSortingEnabled(True)
        self._raw_detail_body.clear()
        self._on_raw_row_selected(-1)  # no selection after a re-filter — disable review buttons

    def _on_raw_row_selected(self, row_idx: int):
        valid = 0 <= row_idx < len(self._raw_page_rows)
        for btn in (self._raw_flag_btn, self._raw_reviewed_btn, self._raw_clear_review_btn):
            btn.setEnabled(valid)
        if not valid:
            return
        (_id, date, provider, family, prompt, response,
         brands, review_status, review_note) = self._raw_page_rows[row_idx]
        review_line = f"Review: {self._REVIEW_DISPLAY.get(review_status, 'Unreviewed')}"
        if review_note:
            review_line += f"  —  {review_note}"
        self._raw_detail_body.setPlainText(
            f"Provider: {provider}  |  Family: {family}  |  Date: {date}\n"
            f"Brands Mentioned: {brands or '—'}\n"
            f"{review_line}\n"
            f"{'─' * 60}\n"
            f"PROMPT:\n{prompt}\n\n"
            f"{'─' * 60}\n"
            f"RESPONSE:\n{response}"
        )

    def _current_raw_response_id(self):
        row_idx = self._raw_tbl.currentRow()
        if not (0 <= row_idx < len(self._raw_page_rows)):
            return None
        return self._raw_page_rows[row_idx][0]

    def _flag_raw_response(self):
        response_id = self._current_raw_response_id()
        if response_id is None:
            return
        note, ok = QInputDialog.getText(
            self, "Flag for Review",
            "What looks wrong with this response? (optional)",
        )
        if not ok:
            return
        self.service.repository.set_review_status(response_id, "flagged", note or "")
        self._filter_raw_data()
        self._refresh_raw_data_kpis_only()

    def _mark_raw_response_reviewed(self):
        response_id = self._current_raw_response_id()
        if response_id is None:
            return
        self.service.repository.set_review_status(response_id, "reviewed")
        self._filter_raw_data()
        self._refresh_raw_data_kpis_only()

    def _clear_raw_response_review(self):
        response_id = self._current_raw_response_id()
        if response_id is None:
            return
        self.service.repository.set_review_status(response_id, "")
        self._filter_raw_data()
        self._refresh_raw_data_kpis_only()

    def _refresh_raw_data_kpis_only(self):
        """Updates just the Flagged-for-Review KPI tile after a status change,
        without re-querying the provider-filter dropdown or resetting scroll
        position the way a full _refresh_raw_data() would."""
        stats = self.service.repository.count_stats()
        self._raw_flagged_val.setText(str(stats["flagged"]))
