import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
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

    def __init__(self, service: VisibilityService, prompts: list, label: str, providers: list):
        super().__init__()
        self.service = service
        self.prompts = prompts
        self.label = label
        self.providers = providers
        self._cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # start in running state
        self._total_prompts = len(prompts)

    def cancel(self):
        self._cancelled = True
        self._pause_event.set()  # unblock if currently paused

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def run(self):
        offset = 0
        total = self._total_prompts * len(self.providers)

        for provider_name in self.providers:
            if self._cancelled:
                break

            def _cb(done, _of_run, _off=offset, _tot=total):
                self.progress.emit(_off + done, _tot)

            try:
                result = self.service.run(
                    prompts=self.prompts,
                    prompt_set=self.label,
                    provider_name=provider_name,
                    progress_callback=_cb,
                    cancelled=lambda: self._cancelled,
                    paused=lambda: not self._pause_event.is_set(),
                )
                self.run_done.emit(result)
            except Exception as exc:
                self.error.emit(f"{provider_name}: {exc}")

            offset += self._total_prompts

        self.all_done.emit()


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


def _set_tbl(tbl: QTableWidget, rows: list[list]):
    tbl.setSortingEnabled(False)
    tbl.setRowCount(len(rows))
    for r, cells in enumerate(rows):
        for c, val in enumerate(cells):
            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, val)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
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

        # ── Row 1: Prompt set multi-select ────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        lbl_ps = QLabel("Prompt Sets:")
        lbl_ps.setFixedWidth(88)
        lbl_ps.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        ps_inner = QWidget()
        ps_lay = QVBoxLayout()
        ps_lay.setSpacing(3)
        ps_lay.setContentsMargins(6, 4, 6, 4)

        self._set_checks: dict[str, QCheckBox] = {}
        all_sets = [s for s in self.service.prompt_library.list_sets() if s != "All Prompts"]
        for set_name in all_sets:
            n = self.service.prompt_library.count(set_name)
            cb = QCheckBox(f"{set_name}  ({n})")
            cb.stateChanged.connect(self._on_sets_changed)
            self._set_checks[set_name] = cb
            ps_lay.addWidget(cb)
        ps_lay.addStretch()
        ps_inner.setLayout(ps_lay)

        ps_scroll = QScrollArea()
        ps_scroll.setWidget(ps_inner)
        ps_scroll.setWidgetResizable(True)
        ps_scroll.setFixedHeight(96)
        ps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ps_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #D1D5DB; border-radius: 4px; background: transparent; }"
        )

        btn_all = QPushButton("All")
        btn_all.setFixedWidth(42)
        btn_all.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        btn_all.clicked.connect(self._select_all_sets)

        btn_none = QPushButton("None")
        btn_none.setFixedWidth(42)
        btn_none.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        btn_none.clicked.connect(self._clear_sets)

        self._count_lbl = QLabel("0 prompts selected")
        self._count_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")

        ps_ctrl = QVBoxLayout()
        ps_ctrl.setSpacing(4)
        ps_ctrl.addWidget(btn_all)
        ps_ctrl.addWidget(btn_none)
        ps_ctrl.addSpacing(4)
        ps_ctrl.addWidget(self._count_lbl)
        ps_ctrl.addStretch()

        row1.addWidget(lbl_ps)
        row1.addWidget(ps_scroll, 1)
        row1.addLayout(ps_ctrl)

        # ── Row 2: Provider checkboxes with connection status ─────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl_prov = QLabel("Providers:")
        lbl_prov.setFixedWidth(88)
        row2.addWidget(lbl_prov)

        self._provider_checks: dict[str, QCheckBox] = {}
        provider_keys = [k for k in self.app.provider_manager.list_providers() if k != "mock"]
        for key in provider_keys:
            has_key = bool(self.app.provider_manager.get_provider_api_key(key))

            cb = QCheckBox()
            cb.setChecked(has_key)
            self._provider_checks[key] = cb

            dot = QLabel("⬤")
            dot.setFixedWidth(16)
            dot.setStyleSheet(
                f"color: {'#16A34A' if has_key else '#DC2626'}; font-size: 14px; padding: 0 1px;"
            )

            name_lbl = QLabel(key.capitalize())
            name_lbl.setStyleSheet("font-size: 12px;")
            name_lbl.setCursor(Qt.PointingHandCursor)
            name_lbl.mousePressEvent = lambda _e, c=cb: c.setChecked(not c.isChecked())

            row2.addWidget(cb)
            row2.addWidget(dot)
            row2.addWidget(name_lbl)
            row2.addSpacing(10)

        row2.addStretch()

        # ── Row 3: Run / Pause / Stop + progress ──────────────────────────────
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

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setFixedWidth(70)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._toggle_pause)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedWidth(70)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_run)

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
            "Brand Mention Rank", "—", "target brand vs competitors"
        )
        self._last_card, _, self._last_val = _stat_card(
            "Last Collection", "—", "most recent visibility run"
        )
        self._last_val.setStyleSheet("font-size: 14px; font-weight: 600;")
        for card in (self._score_card, self._total_card, self._top_card, self._last_card):
            kpi_row.addWidget(card)

        kpi_widget = QWidget()
        kpi_widget.setLayout(kpi_row)

        # ── Content panels ────────────────────────────────────────────────────
        self._pos_frame,       self._pos_body       = _section("Brand Position Share")
        self._brand_frame,     self._brand_body     = _section("Brand Mentions by Provider")
        self._feature_frame,   self._feature_body   = _section("Feature Mentions")
        self._runs_frame, _,   self._runs_tbl       = _table_section(
            "Recent Runs", ["Date", "Provider", "Prompt Set", "Responses"]
        )
        self._runs_tbl.setColumnWidth(0, 130)
        self._runs_tbl.setColumnWidth(1, 90)
        self._runs_tbl.setColumnWidth(3, 80)

        self._responses_frame, self._responses_body = _section("Latest Run Responses")

        left_split = QSplitter(Qt.Vertical)
        left_split.addWidget(self._pos_frame)
        left_split.addWidget(self._brand_frame)
        left_split.setSizes([300, 300])

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(self._feature_frame)
        right_split.addWidget(self._runs_frame)
        right_split.addWidget(self._responses_frame)
        right_split.setSizes([180, 200, 220])

        h_split = QSplitter(Qt.Horizontal)
        h_split.addWidget(left_split)
        h_split.addWidget(right_split)
        h_split.setSizes([580, 420])
        h_split.setHandleWidth(6)

        # ── Channel intelligence row ──────────────────────────────────────────
        ch_lay = QHBoxLayout()
        ch_lay.setSpacing(10)
        ch_lay.setContentsMargins(0, 0, 0, 0)

        self._channel_frame, _, self._channel_tbl = _table_section(
            "Channel Intelligence", ["Channel", "Mentions", "Top Brands"]
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

        ch_lay.addWidget(self._channel_frame, 1)
        ch_lay.addWidget(self._gap_frame, 1)

        ch_widget = QWidget()
        ch_widget.setLayout(ch_lay)
        ch_widget.setMinimumHeight(230)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(ctrl_frame)
        root.addWidget(kpi_widget)
        root.addWidget(h_split, 1)
        root.addWidget(ch_widget)
        self.setLayout(root)

        self._on_sets_changed()
        self.refresh()

    # ── Prompt set helpers ────────────────────────────────────────────────────

    def _on_sets_changed(self):
        prompts, _ = self._get_selected_prompts()
        n = len(prompts)
        self._count_lbl.setText(f"{n} prompt{'s' if n != 1 else ''} selected")

    def _select_all_sets(self):
        for cb in self._set_checks.values():
            cb.setChecked(True)

    def _clear_sets(self):
        for cb in self._set_checks.values():
            cb.setChecked(False)

    def _get_selected_prompts(self) -> tuple:
        selected = [name for name, cb in self._set_checks.items() if cb.isChecked()]
        if not selected:
            return [], ""
        prompts = []
        seen = set()
        for name in selected:
            for p in self.service.prompt_library.get(name):
                if p not in seen:
                    seen.add(p)
                    prompts.append(p)
        label = selected[0] if len(selected) == 1 else f"Custom ({len(selected)} sets)"
        return prompts, label

    def _checked_providers(self) -> list:
        return [k for k, cb in self._provider_checks.items() if cb.isChecked()]

    # ── Run / Pause / Stop ────────────────────────────────────────────────────

    def _start_run(self):
        providers = self._checked_providers()
        if not providers:
            QMessageBox.warning(self, "No Provider", "Check at least one AI provider to run against.")
            return

        prompts, label = self._get_selected_prompts()
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

        self._worker = _RunWorker(self.service, prompts, label, providers)
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
        self._status_lbl.setText(
            f"{run.provider} — {run.response_count} responses in {run.duration_seconds:.1f}s"
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
            self._top_title.setText(f"{brand_label} Mention Rank")
            self._top_val.setText(f"#{rank} of {len(sorted_brands)}")
        else:
            self._top_title.setText("Brand Mention Rank")
            self._top_val.setText("Unranked")

        # Last Collection — two compact lines so it fits the tile at smaller font
        if runs:
            dt = runs[0][4]
            self._last_val.setText(f"{dt[:10]}\n{dt[11:16]}")
        else:
            self._last_val.setText("Never")

        # Brand Position Share
        pos_text = "Factual mention order — not a recommendation rank.\n\n"
        pos_counts = summary.get("brand_position_counts", {})
        pos_shares = summary.get("brand_position_share", {})
        if pos_counts:
            for pos in sorted(pos_counts.keys()):
                pos_text += f"Position {pos}:\n"
                for brand, count in pos_counts[pos].items():
                    share = pos_shares.get(pos, {}).get(brand, 0)
                    pos_text += f"  • {brand}: {count} ({share}%)\n"
                pos_text += "\n"
        else:
            pos_text += "No data yet. Run a visibility collection first."
        self._pos_body.setPlainText(pos_text)

        # Brand Mentions by Provider
        prov_brand = summary.get("provider_brand_counts", {})
        prov_text = ""
        if prov_brand:
            for provider, brands in prov_brand.items():
                prov_text += f"{provider}:\n"
                for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                    prov_text += f"  • {brand}: {count}\n"
                prov_text += "\n"
        else:
            prov_text = "No provider brand data yet."
        self._brand_body.setPlainText(prov_text)

        # Feature Mentions
        feature_counts = summary.get("feature_counts", {})
        feat_text = "\n".join(
            f"• {f}: {c}"
            for f, c in sorted(feature_counts.items(), key=lambda x: -x[1])
        ) if feature_counts else "No feature data yet."
        self._feature_body.setPlainText(feat_text)

        # Recent Runs table
        run_rows = [
            [r[4][:16], r[1], r[3], r[7]]
            for r in runs[:25]
        ]
        _set_tbl(self._runs_tbl, run_rows)

        # Latest Run Responses
        latest_id = runs[0][0] if runs else None
        resp_text = ""
        if latest_id:
            for r in self.service.get_responses_for_run(latest_id):
                resp_text += f"Prompt: {r[4]}\nResponse: {r[5][:400]}…\n{'─'*60}\n\n"
        else:
            resp_text = "No responses available."
        self._responses_body.setPlainText(resp_text)

        # Channel Intelligence table
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

        # Channel Gaps table
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
