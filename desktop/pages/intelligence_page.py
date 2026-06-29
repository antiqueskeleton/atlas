from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.intelligence.intelligence_service import IntelligenceService


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
    body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    layout.addWidget(lbl)
    layout.addWidget(body)
    frame.setLayout(layout)
    return frame, body


def _kpi(title, value="—", sub=""):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    layout = QVBoxLayout()
    layout.setSpacing(2)

    layout.addWidget(_lbl(title, "CardTitle"))
    val_lbl = _lbl(value, "CardValue")
    layout.addWidget(val_lbl)
    if sub:
        layout.addWidget(_lbl(sub, "CardSubtitle"))

    frame.setLayout(layout)
    return frame, val_lbl


def _lbl(text, obj=""):
    l = QLabel(text)
    if obj:
        l.setObjectName(obj)
    return l


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
        root.setSpacing(12)

        # Header
        title = QLabel("Intelligence Engine")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel(
            "Runs structured market research across AI providers and synthesizes brand "
            "positioning, consumer insights, and strategic opportunities."
        )
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")
        subtitle.setWordWrap(True)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        self.provider_select = QComboBox()
        self.provider_select.setFixedWidth(160)
        for key in self.app.provider_manager.list_providers():
            self.provider_select.addItem(key)

        self.run_btn = QPushButton("Run Intelligence Engine")
        self.run_btn.setFixedWidth(210)
        self.run_btn.clicked.connect(self._start_run)

        self.last_run_lbl = QLabel("No runs yet.")
        self.last_run_lbl.setStyleSheet("color:#6B7280;font-size:13px;")

        self._mode_lbl = QLabel()
        self._mode_lbl.setStyleSheet("font-size:12px;")
        self._update_mode_label()

        ctrl.addWidget(QLabel("Provider:"))
        ctrl.addWidget(self.provider_select)
        ctrl.addWidget(self.run_btn)
        ctrl.addWidget(self.last_run_lbl)
        ctrl.addStretch()
        ctrl.addWidget(self._mode_lbl)

        ctrl_widget = QWidget()
        ctrl_widget.setLayout(ctrl)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#6B7280;font-size:13px;")

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        brand = self.app.get_target_brand() or "Target Brand"
        self._kpi_brand_card, self._kpi_brand_val = _kpi(
            f"{brand} Mention Rate", "—%", "% of research responses"
        )
        self._kpi_top_card, self._kpi_top_val = _kpi(
            "Top Brand in Research", "—", "most mentioned across all responses"
        )
        self._kpi_prompts_card, self._kpi_prompts_val = _kpi(
            "Responses Used", "—", "for last synthesis run"
        )
        self._kpi_runs_card, self._kpi_runs_val = _kpi(
            "Runs Completed", "—", "intelligence engine runs"
        )

        kpi_row.addWidget(self._kpi_brand_card)
        kpi_row.addWidget(self._kpi_top_card)
        kpi_row.addWidget(self._kpi_prompts_card)
        kpi_row.addWidget(self._kpi_runs_card)

        kpi_widget = QWidget()
        kpi_widget.setLayout(kpi_row)

        # Left: tabbed research panels
        self.tabs = QTabWidget()

        self._product_frame, self._product_body = _section_card("Product Intelligence")
        self._persona_frame, self._persona_body = _section_card("Consumer Personas")
        self._journey_frame, self._journey_body = _section_card("Buying Journey")
        self._opp_frame, self._opp_body = _section_card("Opportunities")

        self.tabs.addTab(self._product_frame, "Product")
        self.tabs.addTab(self._persona_frame, "Personas")
        self.tabs.addTab(self._journey_frame, "Journey")
        self.tabs.addTab(self._opp_frame, "Opportunities")

        # Right: Executive Briefing (always visible)
        self._brief_frame, self._brief_body = _section_card("Executive Briefing")

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self.tabs)
        h_splitter.addWidget(self._brief_frame)
        h_splitter.setSizes([560, 440])
        h_splitter.setHandleWidth(6)

        # Assemble
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(ctrl_widget)
        root.addWidget(self.status_lbl)
        root.addWidget(kpi_widget)
        root.addWidget(h_splitter)

        self.setLayout(root)

    # ── Run ───────────────────────────────────────────────────────────────────

    def _start_run(self):
        self.run_btn.setEnabled(False)
        self.status_lbl.setText(
            "Running Intelligence Engine — this takes 1-3 minutes depending on provider…"
        )

        provider_name = self.provider_select.currentText()
        self._worker = _RunWorker(self.service, provider_name)
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
                self._mode_lbl.setText(f"Mode: DB  ({total} stored responses — 2 API calls)")
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
        self.status_lbl.setText(
            f"Complete — {result['provider']} · {dur:.0f}s · {mode_str} + 2 synthesis passes"
        )
        self._update_mode_label()
        self._load_latest()

    def _on_run_error(self, message: str):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Error: {message}")

    # ── Load ─────────────────────────────────────────────────────────────────

    def _load_latest(self):
        runs = self.service.list_runs()
        self._kpi_runs_val.setText(str(len(runs)))

        latest = self.service.get_latest_briefing()
        if not latest:
            placeholder = "No intelligence runs yet. Click 'Run Intelligence Engine' to start."
            for body in (
                self._product_body, self._persona_body,
                self._journey_body, self._opp_body, self._brief_body,
            ):
                body.setPlainText(placeholder)
            return

        run = latest["run"]
        briefing = latest["briefing"]
        results = latest["results"]

        # Last run label
        provider = run[1]
        started = run[4][:19].replace("T", " ")
        dur = f"{run[7]:.0f}s" if run[7] else ""
        self.last_run_lbl.setText(f"Last run: {started} · {provider} {dur}")
        self._kpi_prompts_val.setText(str(len(results)))

        # Group results by analyst
        by_analyst: dict[str, list[tuple[str, str]]] = {}
        for analyst_name, prompt, response, _ in results:
            by_analyst.setdefault(analyst_name, []).append((prompt, response))

        def render(pairs):
            return "\n\n".join(
                f"Q: {p}\n\n{r}" for p, r in pairs
            ) or "No data."

        self._product_body.setPlainText(
            render(by_analyst.get("Product Intelligence", []))
        )
        self._persona_body.setPlainText(
            render(by_analyst.get("Consumer Personas", []))
        )
        self._journey_body.setPlainText(
            render(by_analyst.get("Buying Journey", []))
        )

        if briefing:
            self._opp_body.setPlainText(briefing[3] or "No opportunity analysis available.")
            self._brief_body.setPlainText(briefing[4] or "No executive briefing available.")
        else:
            self._opp_body.setPlainText("No opportunity analysis available.")
            self._brief_body.setPlainText("No executive briefing available.")

        # KPIs from brand stats
        brand_stats = self._compute_brand_stats(results)
        counts = brand_stats.get("counts", {})
        total = brand_stats.get("total", 1)
        target = self.app.get_target_brand()

        target_count = counts.get(target, 0) if target else 0
        target_rate = round(target_count / total * 100) if total and target else 0
        self._kpi_brand_val.setText(f"{target_rate}%")

        top_brand = max(counts, key=counts.get) if counts else "—"
        self._kpi_top_val.setText(top_brand)

    def _compute_brand_stats(self, results):
        from collections import Counter
        from backend.services.paths import get_data_dir

        path = get_data_dir() / "brands.csv"
        brands = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                val = line.strip()
                if not val:
                    continue
                if "," in val:
                    val = val.split(",")[0].strip()
                if val.lower() not in ("brand", "brands", "name"):
                    brands.append(val)
        if not brands:
            brands = ["Firman", "Champion", "Westinghouse", "Honda", "Generac", "Yamaha"]

        counts: Counter = Counter()
        total = 0
        for _, _, response, _ in results:
            total += 1
            lower = response.lower()
            for brand in brands:
                if brand.lower() in lower:
                    counts[brand] += 1

        return {"counts": dict(counts), "total": total}
