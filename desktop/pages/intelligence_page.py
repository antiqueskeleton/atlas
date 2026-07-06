from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.intelligence.intelligence_service import IntelligenceService
from backend.intelligence.opportunity_ranking import rank_opportunities
from backend.reports.briefing_sections import split_briefing_sections
from backend.visibility.brand_matcher import resolve_target_brand
from desktop.widgets.stat_card import StatCard


class _RunWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, service, provider_name):
        super().__init__()
        self.service = service
        self.provider_name = provider_name

    def run(self):
        try:
            result = self.service.run(provider_name=self.provider_name)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


def _section_card(title: str):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    layout = QVBoxLayout()
    layout.setSpacing(6)

    lbl = QLabel(title)
    lbl.setObjectName("CardTitle")

    body = QTextEdit()
    body.setReadOnly(True)
    body.setFrameShape(QFrame.NoFrame)
    body.document().setDocumentMargin(10)
    body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    layout.addWidget(lbl)
    layout.addWidget(body)
    frame.setLayout(layout)
    return frame, body


def _boost_markdown_spacing(text_edit: QTextEdit):
    """
    Qt's Markdown-to-richtext conversion (QTextEdit.setMarkdown()) gives
    every heading and thematic-break ("---") block 0pt top/bottom margin —
    so a heading sits flush against the paragraph right before it and the
    whole document reads as one dense, run-together block, no matter how
    much whitespace is in the source markdown. Call this right after
    setMarkdown() to widen those margins so headings, dividers, and list
    items all get visible breathing room.
    """
    doc = text_edit.document()
    block = doc.begin()
    while block.isValid():
        bf = block.blockFormat()
        level = bf.headingLevel()
        is_rule = bf.hasProperty(QTextFormat.BlockTrailingHorizontalRulerWidth)
        changed = False
        if level > 0:
            bf.setTopMargin(22 if level == 1 else 16 if level <= 3 else 12)
            bf.setBottomMargin(8)
            changed = True
        elif is_rule:
            bf.setTopMargin(14)
            bf.setBottomMargin(14)
            changed = True
        elif bf.bottomMargin():
            # Regular paragraph / list item — widen Qt's default 6pt margin.
            bf.setBottomMargin(10)
            changed = True
        if changed:
            QTextCursor(block).setBlockFormat(bf)
        block = block.next()


class IntelligencePage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.service = IntelligenceService(
            self.app.provider_manager,
            target_brand=self.app.get_target_brand(),
        )
        self._worker = None
        self._build_ui()
        self._load_latest()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(8)
        root.setContentsMargins(24, 14, 24, 12)

        # ── Header ────────────────────────────────────────────────────────────
        title = QLabel("Intelligence Engine")
        title.setStyleSheet("font-size:24px; font-weight:bold;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        subtitle = QLabel(
            "Synthesizes stored AI responses into brand positioning, consumer insights, "
            "and strategic opportunities."
        )
        subtitle.setStyleSheet("font-size:13px; color:#6B7280;")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ── Toolbar: Run button + status + Mode badge + Export buttons, all in
        # one row (mirrors the Visibility page's toolbar pattern — previously
        # split across two rows per #38, but that left a nearly-empty second
        # row and a large dead gap in the first). ───────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(12)
        ctrl.setContentsMargins(0, 0, 0, 0)

        self.run_btn = QPushButton("Run Intelligence Analysis")
        self.run_btn.setFixedWidth(210)
        self.run_btn.clicked.connect(self._start_run)
        self.run_btn.setToolTip(
            "Synthesize stored Visibility responses into a briefing, personas, "
            "buying-journey insights, and strategic opportunities"
        )

        self.last_run_lbl = QLabel("No runs yet.")
        self.last_run_lbl.setStyleSheet("color:#6B7280; font-size:12px;")

        self._mode_lbl = QLabel()
        self._mode_lbl.setStyleSheet("font-size:12px;")
        self._mode_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._update_mode_label()

        _export_btn_style = (
            "QPushButton { font-size: 11px; font-weight: 600; color: #0B84FF; "
            "background: white; border: 1.5px solid #0B84FF; border-radius: 5px; padding: 3px 10px; }"
            "QPushButton:hover { background: #EFF6FF; }"
            "QPushButton:pressed { background: #DBEAFE; }"
            "QPushButton:disabled { color: #9CA3AF; border-color: #9CA3AF; }"
        )
        self._export_pdf_btn = QPushButton("Export PDF")
        self._export_pdf_btn.setFixedHeight(26)
        self._export_pdf_btn.setCursor(Qt.PointingHandCursor)
        self._export_pdf_btn.setStyleSheet(_export_btn_style)
        self._export_pdf_btn.clicked.connect(self._export_pdf)
        self._export_pdf_btn.setToolTip("Export the latest briefing as a formatted PDF")

        self._export_docx_btn = QPushButton("Export Word")
        self._export_docx_btn.setFixedHeight(26)
        self._export_docx_btn.setCursor(Qt.PointingHandCursor)
        self._export_docx_btn.setStyleSheet(_export_btn_style)
        self._export_docx_btn.clicked.connect(self._export_docx)
        self._export_docx_btn.setToolTip("Export the latest briefing as an editable Word document")

        self._export_tab_btn = QPushButton("Export Tab (Full)")
        self._export_tab_btn.setFixedHeight(26)
        self._export_tab_btn.setCursor(Qt.PointingHandCursor)
        self._export_tab_btn.setStyleSheet(_export_btn_style)
        self._export_tab_btn.clicked.connect(self._export_current_tab_full)
        self._export_tab_btn.setToolTip(
            "Export the currently selected tab's complete results, with no "
            "10-item cap — unlike Export PDF/Word above, which condense to "
            "keep the main report a manageable length"
        )

        ctrl.addWidget(self.run_btn)
        ctrl.addWidget(self.last_run_lbl)
        ctrl.addStretch()
        ctrl.addWidget(self._mode_lbl)
        ctrl.addSpacing(8)
        ctrl.addWidget(self._export_tab_btn)
        ctrl.addWidget(self._export_docx_btn)
        ctrl.addWidget(self._export_pdf_btn)

        ctrl_widget = QWidget()
        ctrl_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ctrl_widget.setLayout(ctrl)

        # Status label — single compact line below controls
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#6B7280; font-size:12px;")
        self.status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.status_lbl.setFixedHeight(18)

        # ── KPI row ───────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        kpi_row.setContentsMargins(0, 0, 0, 0)

        brand = self.app.get_target_brand() or "Target Brand"
        self._kpi_brand_card = StatCard(
            f"{brand} Mention Rate", "—%", "in latest intelligence analysis",
            info=(
                f"% of responses in your MOST RECENT Intelligence Analysis run — the "
                f"classified sample actually used to generate that briefing (capped at 25 "
                f"per topic bucket, not the full database) — that mention {brand}. Different "
                f"from Visibility Score on the Visibility page, which uses your entire "
                f"collection history."
            ),
            expanding=True, spacing=2, always_show_subtitle=False,
        )
        self._kpi_brand_val = self._kpi_brand_card.value
        self._kpi_top_card = StatCard(
            "Intelligence Mention Rank", "—", "in latest intelligence analysis",
            info=(
                f"{brand}'s rank among all tracked brands by mention count, computed from "
                f"the same latest-run sample as Mention Rate above — not the full database."
            ),
            expanding=True, spacing=2, always_show_subtitle=False,
        )
        self._kpi_top_val = self._kpi_top_card.value
        self._kpi_prompts_card = StatCard(
            "Responses Analyzed", "—", "total stored in database",
            info=(
                "Total responses in your FULL Visibility database — this is NOT the number "
                "actually used to generate the current briefing above (that's a smaller, "
                "capped, classified sample — see Mention Rate). This tile just shows how "
                "large your overall data reservoir is."
            ),
            expanding=True, spacing=2, always_show_subtitle=False,
        )
        self._kpi_prompts_val = self._kpi_prompts_card.value

        kpi_row.addWidget(self._kpi_brand_card)
        kpi_row.addWidget(self._kpi_top_card)
        kpi_row.addWidget(self._kpi_prompts_card)

        kpi_widget = QWidget()
        kpi_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        kpi_widget.setLayout(kpi_row)

        # ── Research panels + Executive Briefing ──────────────────────────────
        self.tabs = QTabWidget()

        self._product_frame, self._product_body = _section_card("Product Intelligence")
        self._persona_frame, self._persona_body = _section_card("Consumer Personas")
        self._journey_frame, self._journey_body = _section_card("Buying Journey")

        # Opportunities tab — scroll area of individual cards
        self._opp_tab = QWidget()
        opp_tab_lay = QVBoxLayout()
        opp_tab_lay.setContentsMargins(0, 0, 0, 0)
        opp_tab_lay.setSpacing(0)
        self._opp_scroll = QScrollArea()
        self._opp_scroll.setWidgetResizable(True)
        self._opp_scroll.setFrameShape(QFrame.NoFrame)
        self._opp_container = QWidget()
        self._opp_cards_layout = QVBoxLayout()
        self._opp_cards_layout.setSpacing(8)
        self._opp_cards_layout.setContentsMargins(8, 8, 8, 8)
        self._opp_cards_layout.addStretch()
        self._opp_container.setLayout(self._opp_cards_layout)
        self._opp_scroll.setWidget(self._opp_container)
        opp_tab_lay.addWidget(self._opp_scroll)
        self._opp_tab.setLayout(opp_tab_lay)

        self.tabs.addTab(self._product_frame, "Product")
        self.tabs.addTab(self._persona_frame, "Personas")
        self.tabs.addTab(self._journey_frame, "Journey")
        self.tabs.addTab(self._opp_tab, "Opportunities")

        self._brief_frame, self._brief_body = _section_card("Executive Briefing")

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self.tabs)
        h_splitter.addWidget(self._brief_frame)
        h_splitter.setSizes([560, 440])
        h_splitter.setHandleWidth(6)

        # ── Assemble — splitter gets all remaining vertical space ──────────────
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(ctrl_widget)
        root.addWidget(self.status_lbl)
        root.addWidget(kpi_widget)
        root.addWidget(h_splitter, stretch=1)

        self.setLayout(root)

    # ── Run ───────────────────────────────────────────────────────────────────

    def _start_run(self):
        self.run_btn.setEnabled(False)
        self.status_lbl.setText(
            "Running analysis — classifying stored responses and generating briefing…"
        )
        # Clear panels so user sees fresh generation, not stale data
        for body in (self._product_body, self._persona_body, self._journey_body):
            body.setPlainText("Analyzing stored responses…")
        self._render_opportunities([], placeholder="Identifying strategic opportunities…")
        self._brief_body.setPlainText("Generating executive briefing from current analysis…")

        self._worker = _RunWorker(self.service, None)  # uses active provider from Settings
        self._worker.finished.connect(self._on_run_finished)
        self._worker.error.connect(self._on_run_error)
        self._worker.start()

    def _update_mode_label(self):
        counts = self.service.db_response_counts()
        total = counts.get("total", 0)
        if total == 0:
            self._mode_lbl.setText("Mode: Live  (no DB data yet)")
            self._mode_lbl.setStyleSheet("font-size:12px; color:#6B7280;")
        else:
            from backend.intelligence.intelligence_service import _MIN_PER_BUCKET
            buckets_ok = all(
                counts.get(k, 0) >= _MIN_PER_BUCKET
                for k in ("Product Intelligence", "Consumer Personas", "Buying Journey")
            )
            if buckets_ok:
                self._mode_lbl.setText(f"Mode: DB  ({total} stored responses — 3 API calls)")
                self._mode_lbl.setStyleSheet("font-size:12px; color:#16A34A; font-weight:bold;")
            else:
                self._mode_lbl.setText(f"Mode: Live  (DB has {total} responses but missing buckets)")
                self._mode_lbl.setStyleSheet("font-size:12px; color:#F59E0B;")

    def _on_run_finished(self, result: dict):
        self.run_btn.setEnabled(True)
        dur = result.get("duration_seconds", 0)
        source = result.get("source", "live")
        used = result.get("responses_used", 0)
        mode_str = f"DB ({used} responses)" if source == "db" else f"Live ({used} prompts)"
        errors = result.get("error_count", 0)
        error_str = f" · {errors} prompt(s) failed and were excluded" if errors else ""
        self.status_lbl.setText(
            f"Complete — {result['provider']} · {dur:.0f}s · {mode_str} + 3 synthesis passes{error_str}"
        )
        self._update_mode_label()
        self._load_latest()

    def _on_run_error(self, message: str):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Error: {message}")

    # ── Export ───────────────────────────────────────────────────────────────

    def _get_report_data(self):
        """Return (run, briefing, results, opportunities) for the latest run, or None."""
        latest = self.service.get_latest_briefing()
        if not latest:
            QMessageBox.information(
                self, "No Data",
                "Run Intelligence Analysis first to generate data for export."
            )
            return None
        run      = latest["run"]
        briefing = latest["briefing"]
        results  = latest["results"]
        run_id   = run[0]
        opps     = self.service.repository.get_opportunities_for_run(run_id)
        return run, briefing, results, opps

    def _export_pdf(self):
        data = self._get_report_data()
        if not data:
            return

        brand = self.app.get_target_brand() or "Report"
        ts    = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M")
        default = f"Atlas_Intelligence_Report_{brand}_{ts}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", default, "PDF Files (*.pdf)"
        )
        if not path:
            return

        self._export_pdf_btn.setEnabled(False)
        self._export_pdf_btn.setText("Generating…")

        run, briefing, results, opps = data

        def _generate():
            try:
                from backend.reports.intelligence_pdf_report import IntelligencePDFReport
                rpt = IntelligencePDFReport(
                    run=run, briefing=briefing, results=results,
                    opportunities=opps, target_brand=brand,
                )
                rpt.generate(path)
                return path, None
            except Exception as exc:
                return None, str(exc)

        def _done(result):
            out_path, err = result
            self._export_pdf_btn.setEnabled(True)
            self._export_pdf_btn.setText("Export PDF")
            if err:
                QMessageBox.critical(self, "Export Failed",
                                     f"Could not generate PDF:\n\n{err}")
            else:
                reply = QMessageBox.information(
                    self, "Report Ready",
                    f"PDF saved to:\n{out_path}",
                    QMessageBox.Open | QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                if reply == QMessageBox.Open:
                    import os, subprocess
                    if os.name == 'nt':
                        os.startfile(out_path)

        from PySide6.QtCore import QThread, Signal as _Signal

        class _W(QThread):
            finished = _Signal(tuple)
            def run(self_):
                self_.finished.emit(_generate())

        self._pdf_worker = _W()
        self._pdf_worker.finished.connect(_done)
        self._pdf_worker.start()

    def _export_docx(self):
        data = self._get_report_data()
        if not data:
            return

        brand = self.app.get_target_brand() or "Report"
        ts    = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M")
        default = f"Atlas_Intelligence_Report_{brand}_{ts}.docx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Word Document", default,
            "Word Documents (*.docx)"
        )
        if not path:
            return

        self._export_docx_btn.setEnabled(False)
        self._export_docx_btn.setText("Generating…")

        run, briefing, results, opps = data

        def _generate():
            try:
                from backend.reports.intelligence_docx_report import IntelligenceDocxReport
                rpt = IntelligenceDocxReport(
                    run=run, briefing=briefing, results=results,
                    opportunities=opps, target_brand=brand,
                )
                rpt.generate(path)
                return path, None
            except Exception as exc:
                return None, str(exc)

        def _done(result):
            out_path, err = result
            self._export_docx_btn.setEnabled(True)
            self._export_docx_btn.setText("Export Word")
            if err:
                QMessageBox.critical(self, "Export Failed",
                                     f"Could not generate Word document:\n\n{err}")
            else:
                reply = QMessageBox.information(
                    self, "Export Ready",
                    f"Word document saved to:\n{out_path}",
                    QMessageBox.Open | QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                if reply == QMessageBox.Open:
                    import os
                    if os.name == 'nt':
                        os.startfile(out_path)

        from PySide6.QtCore import QThread, Signal as _Signal

        class _W(QThread):
            finished = _Signal(tuple)
            def run(self_):
                self_.finished.emit(_generate())

        self._docx_worker = _W()
        self._docx_worker.finished.connect(_done)
        self._docx_worker.start()

    # Tab index -> (analyst section name, display name), matching the
    # addTab() order above. Opportunities (index 3) is handled separately
    # since it isn't an analyst section.
    _TAB_SECTIONS = {
        0: ("Product Intelligence", "Product"),
        1: ("Consumer Personas", "Personas"),
        2: ("Buying Journey", "Journey"),
    }

    def _export_current_tab_full(self):
        """
        Export just the currently selected tab's complete results, with no
        top-N cap — unlike Export PDF/Word, which deliberately condense to
        keep the main report readable (#81). Reuses IntelligencePDFReport/
        IntelligenceDocxReport's full_export flag rather than a separate
        rendering path: constructing them with only this one tab's data
        (empty everything else) naturally produces a document containing
        just that section, in full.
        """
        tab_idx = self.tabs.currentIndex()
        latest = self.service.get_latest_briefing()
        if not latest:
            QMessageBox.information(
                self, "No Data",
                "Run Intelligence Analysis first to generate data for export."
            )
            return
        run = latest["run"]
        brand = self.app.get_target_brand() or "Report"

        if tab_idx in self._TAB_SECTIONS:
            section_name, display_name = self._TAB_SECTIONS[tab_idx]
            results = [r for r in latest["results"] if r[0] == section_name]
            opps = []
            if not results:
                QMessageBox.information(
                    self, "No Data", f"No {display_name} responses to export yet."
                )
                return
        else:
            display_name = "Opportunities"
            results = []
            opps = self.service.repository.get_all_opportunities()
            if not opps:
                QMessageBox.information(self, "No Data", "No opportunities to export yet.")
                return

        ts = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M")
        default = f"Atlas_Intelligence_{display_name}_Full_{brand}_{ts}.pdf"
        path, chosen_filter = QFileDialog.getSaveFileName(
            self, f"Export {display_name} (Full)", default,
            "PDF Files (*.pdf);;Word Documents (*.docx)"
        )
        if not path:
            return

        self._export_tab_btn.setEnabled(False)
        self._export_tab_btn.setText("Generating…")
        is_docx = path.lower().endswith(".docx")

        def _generate():
            try:
                if is_docx:
                    from backend.reports.intelligence_docx_report import IntelligenceDocxReport
                    rpt = IntelligenceDocxReport(
                        run=run, briefing=(), results=results, opportunities=opps,
                        target_brand=brand, full_export=True,
                    )
                else:
                    from backend.reports.intelligence_pdf_report import IntelligencePDFReport
                    rpt = IntelligencePDFReport(
                        run=run, briefing=(), results=results, opportunities=opps,
                        target_brand=brand, full_export=True,
                    )
                rpt.generate(path)
                return path, None
            except Exception as exc:
                return None, str(exc)

        def _done(result):
            out_path, err = result
            self._export_tab_btn.setEnabled(True)
            self._export_tab_btn.setText("Export Tab (Full)")
            if err:
                QMessageBox.critical(self, "Export Failed", f"Could not generate export:\n\n{err}")
            else:
                reply = QMessageBox.information(
                    self, "Export Ready", f"Saved to:\n{out_path}",
                    QMessageBox.Open | QMessageBox.Ok, QMessageBox.Ok,
                )
                if reply == QMessageBox.Open:
                    import os
                    if os.name == 'nt':
                        os.startfile(out_path)

        from PySide6.QtCore import QThread, Signal as _Signal

        class _W(QThread):
            finished = _Signal(tuple)
            def run(self_):
                self_.finished.emit(_generate())

        self._tab_export_worker = _W()
        self._tab_export_worker.finished.connect(_done)
        self._tab_export_worker.start()

    # ── Load ─────────────────────────────────────────────────────────────────

    def _load_latest(self):
        runs = self.service.list_runs()
        self._kpi_prompts_val.setText(str(self.service.total_response_count()))

        latest = self.service.get_latest_briefing()
        if not latest:
            placeholder = "No intelligence runs yet. Click 'Run Intelligence Analysis' to start."
            for body in (self._product_body, self._persona_body, self._journey_body, self._brief_body):
                body.setPlainText(placeholder)
            self._render_opportunities([], placeholder=placeholder)
            return

        run = latest["run"]
        briefing = latest["briefing"]
        results = latest["results"]

        # Last run label — also shows runs completed count
        provider = run[1]
        started = run[4][:19].replace("T", " ")
        dur = f"{run[7]:.0f}s" if run[7] else ""
        n_runs = len(runs)
        self.last_run_lbl.setText(
            f"Runs Completed: {n_runs}  ·  Last run: {started} · {provider} {dur}"
        )

        # Group results by analyst
        by_analyst: dict[str, list[tuple[str, str]]] = {}
        for analyst_name, prompt, response, _ in results:
            by_analyst.setdefault(analyst_name, []).append((prompt, response))

        def render(pairs):
            # AI responses are markdown (headers/bold/bullets/tables) — render
            # it as such instead of dumping the raw ##/**/| syntax as plain
            # text. "# Q: ..." uses the biggest heading level so each question
            # stands out above the response's own internal ##/### structure;
            # "---" between pairs gives a clear divider between Q&A blocks.
            if not pairs:
                return "No data."
            return "\n\n---\n\n".join(f"# Q: {p}\n\n{r}" for p, r in pairs)

        self._product_body.setMarkdown(
            render(by_analyst.get("Product Intelligence", []))
        )
        _boost_markdown_spacing(self._product_body)
        self._persona_body.setMarkdown(
            render(by_analyst.get("Consumer Personas", []))
        )
        _boost_markdown_spacing(self._persona_body)
        self._journey_body.setMarkdown(
            render(by_analyst.get("Buying Journey", []))
        )
        _boost_markdown_spacing(self._journey_body)

        briefing_text = (briefing[4] if briefing else "") or "No executive briefing available."
        self._brief_body.setMarkdown(self._format_briefing(briefing_text))
        _boost_markdown_spacing(self._brief_body)

        opp_rows = self.service.repository.get_all_opportunities()
        self._render_opportunities(opp_rows)

        # KPIs from brand stats
        brand_stats = self._compute_brand_stats(results)
        counts = brand_stats.get("counts", {})
        total = brand_stats.get("total", 1)
        target = resolve_target_brand(
            self.app.get_target_brand(), brand_stats.get("known_brands", [])
        )

        target_count = counts.get(target, 0) if target else 0
        target_rate = round(target_count / total * 100) if total and target else 0
        self._kpi_brand_val.setText(f"{target_rate}%")

        sorted_brands = sorted(counts.items(), key=lambda x: -x[1])
        rank = next((i + 1 for i, (b, _) in enumerate(sorted_brands) if b == target), None)
        total_tracked = brand_stats.get("total_tracked_brands", len(sorted_brands))
        if rank and target:
            self._kpi_top_val.setText(f"#{rank} of {total_tracked}")
        else:
            self._kpi_top_val.setText("Unranked")

    _STATUS_CYCLE = ["new", "in_progress", "done"]
    _STATUS_LABELS = {"new": "New", "in_progress": "In Progress", "done": "Done"}
    _STATUS_COLORS = {"new": "#6B7280", "in_progress": "#F59E0B", "done": "#16A34A"}

    @staticmethod
    def _format_briefing(text: str) -> str:
        """
        The briefing prompt deliberately forbids markdown and instead uses
        plain "SECTION NAME\\nBody text" sections (see briefing_sections.py)
        — but with no visual distinction between a section's header and its
        body, the whole briefing still read as one dense wall of text.
        Reuses the same setMarkdown() rendering already proven for the
        Product/Personas/Journey tabs: turn each detected header into a
        real markdown heading so it renders bigger/bolder, purely for
        on-screen display — the underlying data/text is unchanged. A "---"
        between sections (same divider the Q&A panels use between pairs)
        gives each section a visible break instead of running straight into
        the next header.
        """
        sections = split_briefing_sections(text)
        if not sections:
            return text
        return "\n\n---\n\n".join(
            f"#### {header}\n\n{body}" if header else body
            for header, body in sections
        )

    def _render_opportunities(self, opp_rows, placeholder=None):
        # Clear existing cards (all items except the trailing stretch)
        while self._opp_cards_layout.count() > 1:
            item = self._opp_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not opp_rows:
            msg = placeholder or "No opportunities yet. Run Intelligence Analysis to generate."
            lbl = QLabel(msg)
            lbl.setStyleSheet("color:#6B7280; padding:16px;")
            lbl.setWordWrap(True)
            self._opp_cards_layout.insertWidget(0, lbl)
            return

        # Priority order, not recency order — get_all_opportunities() sorts
        # by created_date DESC (needed so a status change survives future
        # runs, per #39), but that made the displayed "#N" look like a
        # priority ranking when it never was one. Ranks opportunities citing
        # a concrete "X of Y" evidence count (e.g. "0 of 84 responses") above
        # purely qualitative ones — see opportunity_ranking.py.
        opp_rows = rank_opportunities(opp_rows)

        for idx, (opp_id, title, evidence, description, status, *rest) in enumerate(opp_rows):
            status = status or "new"
            created_date = rest[0] if rest else ""
            card = QFrame()
            card.setObjectName("StatCard")
            card_lay = QVBoxLayout()
            card_lay.setSpacing(6)

            # Title + status button row
            title_row = QHBoxLayout()
            title_lbl = QLabel(f"{idx + 1}. {title}")
            title_lbl.setStyleSheet("font-weight:bold; font-size:13px;")
            title_lbl.setWordWrap(True)
            title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            color = self._STATUS_COLORS.get(status, "#6B7280")
            status_btn = QPushButton(self._STATUS_LABELS.get(status, "New"))
            status_btn.setFixedSize(96, 24)
            status_btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color:white; border:none; "
                f"border-radius:4px; font-size:11px; }}"
                f"QPushButton:hover {{ background:{color}; opacity:0.85; }}"
            )

            def _make_toggle(oid, btn, cur):
                def _toggle():
                    nxt = self._STATUS_CYCLE[(self._STATUS_CYCLE.index(cur) + 1) % 3]
                    self.service.repository.update_opportunity_status(oid, nxt)
                    # Cross-run view (#39): re-render from ALL runs, not just the
                    # latest, so toggling one card's status doesn't make every
                    # older run's opportunities disappear.
                    self._render_opportunities(self.service.repository.get_all_opportunities())
                return _toggle

            status_btn.clicked.connect(_make_toggle(opp_id, status_btn, status))
            title_row.addWidget(title_lbl)
            title_row.addWidget(status_btn)
            card_lay.addLayout(title_row)

            if created_date:
                date_lbl = QLabel(f"From run: {created_date[:10]}")
                date_lbl.setStyleSheet("font-size:10px; color:#9CA3AF;")
                card_lay.addWidget(date_lbl)

            if evidence:
                ev_hdr = QLabel("Evidence")
                ev_hdr.setStyleSheet("font-size:11px; color:#6B7280; font-weight:bold;")
                ev_body = QLabel(evidence)
                ev_body.setWordWrap(True)
                ev_body.setStyleSheet("font-size:12px; color:#374151;")
                card_lay.addWidget(ev_hdr)
                card_lay.addWidget(ev_body)

            if description:
                ac_hdr = QLabel("Action")
                ac_hdr.setStyleSheet("font-size:11px; color:#6B7280; font-weight:bold;")
                ac_body = QLabel(description)
                ac_body.setWordWrap(True)
                ac_body.setStyleSheet("font-size:12px; color:#374151;")
                card_lay.addWidget(ac_hdr)
                card_lay.addWidget(ac_body)

            card.setLayout(card_lay)
            self._opp_cards_layout.insertWidget(self._opp_cards_layout.count() - 1, card)

    def _compute_brand_stats(self, results):
        from collections import Counter
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        brand_terms = KnowledgeRepository().get_brand_detection_terms()
        if not brand_terms:
            defaults = ["Firman", "Westinghouse", "Honda", "Generac", "Yamaha", "DuroMax"]
            brand_terms = {b: [b.lower()] for b in defaults}

        counts: Counter = Counter()
        total = 0
        for _, _, response, _ in results:
            total += 1
            lower = response.lower()
            for brand, terms in brand_terms.items():
                if any(t in lower for t in terms):
                    counts[brand] += 1
        return {
            "counts": dict(counts),
            "total": total,
            # #48: total TRACKED brands, not just ones with ≥1 mention — same
            # fix as visibility_page.py's Mention Rank denominator.
            "total_tracked_brands": len(brand_terms),
            "known_brands": list(brand_terms.keys()),
        }
