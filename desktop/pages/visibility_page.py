from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QScrollArea,
)

from backend.visibility.visibility_service import VisibilityService


# ── Worker thread ─────────────────────────────────────────────────────────────

class _RunWorker(QThread):
    progress = Signal(int, int)       # completed, total
    run_done = Signal(dict)           # result dict for one provider
    all_done = Signal()
    error    = Signal(str)

    def __init__(self, service: VisibilityService, prompt_set: str, providers: list[str]):
        super().__init__()
        self.service = service
        self.prompt_set = prompt_set
        self.providers = providers
        self._cancelled = False
        self._total_prompts = service.prompt_library.count(prompt_set)

    def cancel(self):
        self._cancelled = True

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
                    prompt_set=self.prompt_set,
                    provider_name=provider_name,
                    progress_callback=_cb,
                    cancelled=lambda: self._cancelled,
                )
                self.run_done.emit(result)
            except Exception as exc:
                self.error.emit(f"{provider_name}: {exc}")

            offset += self._total_prompts

        self.all_done.emit()


# ── Stat card helpers ─────────────────────────────────────────────────────────

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
    return frame, v


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

        # Row 1: Prompt set picker
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        lbl_ps = QLabel("Prompt Set:")
        lbl_ps.setFixedWidth(88)
        self.prompt_set = QComboBox()
        self.prompt_set.setMinimumWidth(260)
        self.prompt_set.addItems(self.service.prompt_library.list_sets())
        self.prompt_set.currentTextChanged.connect(self._on_set_changed)

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")

        row1.addWidget(lbl_ps)
        row1.addWidget(self.prompt_set)
        row1.addWidget(self._count_lbl)
        row1.addStretch()

        # Row 2: Provider checkboxes
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl_prov = QLabel("Providers:")
        lbl_prov.setFixedWidth(88)
        row2.addWidget(lbl_prov)

        self._provider_checks: dict[str, QCheckBox] = {}
        provider_keys = [k for k in self.app.provider_manager.list_providers() if k != "mock"]
        for key in provider_keys:
            cb = QCheckBox(key.capitalize())
            cb.setChecked(False)
            self._provider_checks[key] = cb
            row2.addWidget(cb)

        # Default: activate whichever provider is currently active
        active = self.app.provider_manager.active_provider_name
        if active in self._provider_checks:
            self._provider_checks[active].setChecked(True)

        row2.addStretch()

        # Row 3: Run controls + progress
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
        self._score_card, self._score_val = _stat_card(
            f"{brand_label} Visibility Score", "—%", f"% of responses mentioning {brand_label}"
        )
        self._total_card, self._total_val = _stat_card("Total Responses", "—", "across all runs")
        self._top_card,   self._top_val   = _stat_card("Top Mentioned Brand", "—", "most frequent in responses")
        self._runs_card,  self._runs_val  = _stat_card("Runs Completed", "—", "visibility collection runs")
        for card in (self._score_card, self._total_card, self._top_card, self._runs_card):
            kpi_row.addWidget(card)

        kpi_widget = QWidget()
        kpi_widget.setLayout(kpi_row)

        # ── Content panels ────────────────────────────────────────────────────
        self._pos_frame,       self._pos_body       = _section("Brand Position Share")
        self._brand_frame,     self._brand_body     = _section("Brand Mentions by Provider")
        self._feature_frame,   self._feature_body   = _section("Feature Mentions")
        self._runs_frame,      self._runs_body      = _section("Recent Runs")
        self._responses_frame, self._responses_body = _section("Latest Run Responses")

        left_split = QSplitter(Qt.Vertical)
        left_split.addWidget(self._pos_frame)
        left_split.addWidget(self._brand_frame)
        left_split.setSizes([300, 300])

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(self._feature_frame)
        right_split.addWidget(self._runs_frame)
        right_split.addWidget(self._responses_frame)
        right_split.setSizes([200, 160, 240])

        h_split = QSplitter(Qt.Horizontal)
        h_split.addWidget(left_split)
        h_split.addWidget(right_split)
        h_split.setSizes([580, 420])
        h_split.setHandleWidth(6)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(ctrl_frame)
        root.addWidget(kpi_widget)
        root.addWidget(h_split)
        self.setLayout(root)

        self._on_set_changed(self.prompt_set.currentText())
        self.refresh()

    # ── Prompt set helpers ────────────────────────────────────────────────────

    def _on_set_changed(self, name: str):
        n = self.service.prompt_library.count(name)
        self._count_lbl.setText(f"({n} prompts)")

    def _checked_providers(self) -> list[str]:
        return [k for k, cb in self._provider_checks.items() if cb.isChecked()]

    # ── Run / stop ────────────────────────────────────────────────────────────

    def _start_run(self):
        providers = self._checked_providers()
        if not providers:
            QMessageBox.warning(self, "No Provider", "Check at least one AI provider to run against.")
            return

        prompt_set = self.prompt_set.currentText()
        n_prompts = self.service.prompt_library.count(prompt_set)
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
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, total)
        self._progress.setValue(0)
        self._status_lbl.setText("Starting…")

        self._worker = _RunWorker(self.service, prompt_set, providers)
        self._worker.progress.connect(self._on_progress)
        self._worker.run_done.connect(self._on_run_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_run(self):
        if self._worker:
            self._worker.cancel()
        self._status_lbl.setText("Stopping after current prompt…")
        self._stop_btn.setEnabled(False)

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

        score = summary["target_visibility_score"]
        total = summary["total_responses"]
        brand_counts = summary.get("brand_counts", {})
        top_brand = max(brand_counts, key=brand_counts.get) if brand_counts else "—"

        self._score_val.setText(f"{score}%")
        self._total_val.setText(str(total))
        self._top_val.setText(top_brand)
        self._runs_val.setText(str(len(runs)))

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

        # Recent Runs
        runs_text = ""
        if runs:
            for run in runs[:20]:
                runs_text += f"{run[4][:16]}  {run[1]:<14}  {run[3]:<28}  {run[7]} resp\n"
        else:
            runs_text = "No visibility runs yet."
        self._runs_body.setPlainText(runs_text)

        # Latest Run Responses
        latest_id = runs[0][0] if runs else None
        resp_text = ""
        if latest_id:
            for r in self.service.get_responses_for_run(latest_id):
                resp_text += f"Prompt: {r[4]}\nResponse: {r[5][:400]}…\n{'─'*60}\n\n"
        else:
            resp_text = "No responses available."
        self._responses_body.setPlainText(resp_text)
