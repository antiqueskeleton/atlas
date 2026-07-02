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

from backend.visibility.visibility_service import VisibilityService


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

def _stat_card(title, value, subtitle=""):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lay = QVBoxLayout()
    lay.setSpacing(2)
    lay.setContentsMargins(14, 12, 14, 12)

    t = QLabel(title);  t.setObjectName("CardTitle")
    v = QLabel(value);  v.setObjectName("CardValue")
    lay.addWidget(t)
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

        lbl_ps = QLabel("Prompt Sets:")
        lbl_ps.setFixedWidth(88)
        lbl_ps.setAlignment(Qt.AlignTop | Qt.AlignLeft)

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
        ps_scroll.setFixedHeight(340)
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

        self._count_lbl = QLabel("0 sets\n0 prompts")
        self._count_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._count_lbl.setFixedWidth(72)

        ps_ctrl = QVBoxLayout()
        ps_ctrl.setSpacing(4)
        ps_ctrl.setAlignment(Qt.AlignTop)
        ps_ctrl.addWidget(btn_all)
        ps_ctrl.addWidget(btn_none)
        ps_ctrl.addWidget(btn_top)
        ps_ctrl.addSpacing(6)
        ps_ctrl.addWidget(self._count_lbl)
        ps_ctrl.addStretch()

        row1.addWidget(lbl_ps)
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

        # ── Row 3: Run / Pause / Stop ─────────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(10)

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
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: 1px solid #D1D5DB; border-radius: 6px; text-align: center; font-size: 10px; }"
            "QProgressBar::chunk { background: #0B84FF; border-radius: 5px; }"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")

        row3.addWidget(self._run_btn)
        row3.addWidget(self._pause_btn)
        row3.addWidget(self._stop_btn)
        row3.addWidget(self._progress)
        row3.addWidget(self._status_lbl)
        row3.addStretch()

        ctrl_lay.addLayout(row1)
        ctrl_lay.addLayout(row2)
        ctrl_lay.addLayout(row3)
        ctrl_frame.setLayout(ctrl_lay)

        # ── KPI cards ─────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        brand_label = self.app.get_target_brand() or "Target Brand"
        self._score_card, self._score_title, self._score_val = _stat_card(
            f"{brand_label} Visibility Score", "—%", f"% of responses mentioning {brand_label}"
        )
        self._total_card, _, self._total_val = _stat_card(
            "Responses Analyzed", "—", "across all collected runs"
        )
        self._top_card, self._top_title, self._top_val = _stat_card(
            "Visibility Mention Rank", "—", "across all visibility collection responses"
        )
        self._last_card, _, self._last_val = _stat_card(
            "Last Collection", "—", "most recent visibility run"
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

        self._brand_frame, _, self._brand_tbl = _table_section(
            "Brand Mentions by Provider",
            ["Provider", "Brand", "Mentions"],
            stretch_last=False,
        )
        self._brand_tbl.setColumnWidth(0, 110)
        self._brand_tbl.setColumnWidth(2, 80)
        self._brand_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self._sentiment_frame, _, self._sentiment_tbl = _table_section(
            "Brand Sentiment",
            ["Brand", "Mentions", "Negative", "Negative %"],
            stretch_last=False,
        )
        self._sentiment_tbl.setColumnWidth(1, 80)
        self._sentiment_tbl.setColumnWidth(2, 80)
        self._sentiment_tbl.setColumnWidth(3, 90)
        self._sentiment_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._sentiment_tbl.setToolTip(
            "Negative = responses where this brand was mentioned in an unfavorable or "
            "comparative-losing context (e.g. \"unlike Firman, Honda includes...\"). "
            "Negative % is of that brand's OWN mentions, not of all responses."
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
        for card in (self._raw_total_card, self._raw_prov_card,
                     self._raw_runs_card, self._raw_fam_card):
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
        self._raw_count_lbl = QLabel("")
        self._raw_count_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._raw_count_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._raw_search, 1)
        filter_row.addWidget(prov_lbl)
        filter_row.addWidget(self._raw_prov_filter)
        filter_row.addWidget(self._raw_count_lbl)
        filter_widget = QWidget()
        filter_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_widget.setLayout(filter_row)

        # Response table — Family now shows the per-response family name
        self._raw_frame, _, self._raw_tbl = _table_section(
            "Responses", ["Date", "Provider", "Family", "Prompt", "Response Preview"],
            stretch_last=True,
        )
        self._raw_tbl.setColumnWidth(0, 130)
        self._raw_tbl.setColumnWidth(1, 100)
        self._raw_tbl.setColumnWidth(2, 200)
        self._raw_tbl.setColumnWidth(3, 220)
        self._raw_tbl.currentCellChanged.connect(lambda row, *_: self._on_raw_row_selected(row))

        self._raw_detail_frame, self._raw_detail_body = _section("Full Response")
        self._raw_detail_body.setReadOnly(True)

        raw_split = QSplitter(Qt.Vertical)
        raw_split.addWidget(self._raw_frame)
        raw_split.addWidget(self._raw_detail_frame)
        raw_split.setSizes([420, 200])

        raw_lay.addWidget(raw_kpi_widget)
        raw_lay.addWidget(filter_widget)
        raw_lay.addWidget(raw_split, 1)

        self._raw_page_rows: list = []  # current page (≤ RAW_PAGE_SIZE rows) for row-click detail
        self._RAW_PAGE_SIZE = 2000

        tabs.addTab(overview,      "Overview")
        tabs.addTab(brands_tab,    "Brands")
        tabs.addTab(features_tab,  "Features")
        tabs.addTab(channels_tab,  "Channels")
        tabs.addTab(raw_tab,       "Raw Data")

        self._ctrl_frame = ctrl_frame

        self._collapse_btn = QPushButton("▲  Hide Controls")
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
        self._collapse_btn.setToolTip("Show or hide the prompt/provider selection panel")

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
        toolbar_row.addWidget(self._collapse_btn, 1)
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
        self._count_lbl.setText(f"{n_sets} set{'s' if n_sets != 1 else ''}\n{len(prompts)} prompts")

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
        visible = not self._ctrl_frame.isVisible()
        self._ctrl_frame.setVisible(visible)
        self._collapse_btn.setText("▲  Hide Controls" if visible else "▼  Show Controls")

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

        # Brand Mention Rank
        sorted_brands = sorted(brand_counts.items(), key=lambda x: -x[1])
        rank = next((i + 1 for i, (b, _) in enumerate(sorted_brands) if b == brand_label), None)
        if rank:
            self._top_title.setText(f"Visibility Mention Rank  —  {brand_label}")
            self._top_val.setText(f"#{rank} of {len(sorted_brands)}")
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

        # ── Brand Sentiment → sortable table ───────────────────────────────────
        negative_counts = summary.get("negative_brand_counts", {})
        negative_rates = summary.get("brand_negative_rate", {})
        sentiment_rows = [
            [brand, count, negative_counts.get(brand, 0), f"{negative_rates.get(brand, 0)}%"]
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

    def _filter_raw_data(self):
        search = self._raw_search.text().strip()
        prov   = self._raw_prov_filter.currentText()
        prov_filter = "" if prov == "All Providers" else prov

        total_matching = self.service.repository.count_responses_filtered(
            search=search, provider=prov_filter
        )
        rows = self.service.repository.list_responses(
            limit=self._RAW_PAGE_SIZE, offset=0,
            search=search, provider=prov_filter,
        )

        # Tuple: (id, run_id, provider, model, prompt, response, collected_at, family_display)
        self._raw_page_rows = [
            (
                (r[6] or "")[:16],
                r[2] or "",
                r[7] or "—",
                r[4] or "",
                r[5] or "",
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
        for row_idx, (date, provider, family, prompt, response) in enumerate(self._raw_page_rows):
            for col, val in enumerate((date, provider, family, prompt[:120], response[:120])):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._raw_tbl.setItem(row_idx, col, item)
        self._raw_tbl.setSortingEnabled(True)
        self._raw_detail_body.clear()

    def _on_raw_row_selected(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self._raw_page_rows):
            return
        date, provider, family, prompt, response = self._raw_page_rows[row_idx]
        self._raw_detail_body.setPlainText(
            f"Provider: {provider}  |  Family: {family}  |  Date: {date}\n"
            f"{'─' * 60}\n"
            f"PROMPT:\n{prompt}\n\n"
            f"{'─' * 60}\n"
            f"RESPONSE:\n{response}"
        )
