from backend.models.ai_reasoning import AIReasoning
from backend.investigations.investigation_engine import InvestigationEngine
from desktop.widgets.ai_reasoning_panel import AIReasoningPanel
from desktop.widgets.evidence_viewer import EvidenceViewer
from desktop.widgets.executive_consensus_panel import ExecutiveConsensusPanel
from desktop.widgets.intent_panel import IntentPanel
from desktop.widgets.investigation_plan_panel import InvestigationPlanPanel
from desktop.widgets.prompt_panel import PromptPanel
from desktop.widgets.provider_card import ProviderCard
from desktop.widgets.recommendation_card import RecommendationCard
from desktop.widgets.relationship_explorer import RelationshipExplorer
from desktop.widgets.scrollable_card import ScrollableCard
from desktop.widgets.search_bar import SearchBar
from desktop.widgets.task_results_panel import TaskResultsPanel

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class _InvestigationWorker(QThread):
    progress = Signal(str, int, int)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, engine, question, provider_name=None):
        super().__init__()
        self.engine = engine
        self.question = question
        self.provider_name = provider_name

    def run(self):
        try:
            if self.provider_name:
                pm = self.engine.provider_manager
                if self.provider_name != getattr(pm, "active_provider_name", None):
                    pm.set_active_provider(self.provider_name)
            result = self.engine.investigate(
                self.question,
                progress_callback=lambda step, cur, total: self.progress.emit(step, cur, total),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


def _stub_reasoning(msg: str) -> AIReasoning:
    return AIReasoning(executive_summary=msg, confidence="Low", provider="—")


class InvestigationPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.engine = InvestigationEngine(self.app)
        self._worker = None
        self._ranked_evidence = []
        self._evidence_idx = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(24, 14, 24, 12)
        root.setSpacing(6)

        title = QLabel("Investigation Workspace")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        subtitle = QLabel(
            "Ask a one-off strategic question, any time — specialist AI agents "
            "analyze whatever Visibility data is already stored. No separate "
            "collection or report needs to run first."
        )
        subtitle.setStyleSheet("font-size:13px;color:#6B7280;")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.search = SearchBar(
            placeholder="Example: Why is Firman losing to Generac in home standby searches?",
            button_text="Investigate",
        )
        self.search.connect(self.run)
        self.search.input.returnPressed.connect(self.run)

        # ── Controls bar ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 2, 0, 2)
        ctrl.setSpacing(10)

        prov_lbl = QLabel("Provider:")
        prov_lbl.setStyleSheet("font-size:12px; color:#6B7280;")
        prov_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._provider_combo = QComboBox()
        self._provider_combo.setFixedWidth(160)
        self._provider_combo.setStyleSheet("font-size:12px;")
        self._provider_combo.setToolTip("Which AI provider's agents analyze this question")
        self._populate_providers()

        self._status_lbl = QLabel("Enter a question above to begin.")
        self._status_lbl.setStyleSheet("font-size:12px; color:#6B7280;")
        self._status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        ctrl.addWidget(prov_lbl)
        ctrl.addWidget(self._provider_combo)
        ctrl.addSpacing(12)
        ctrl.addWidget(self._status_lbl)

        ctrl_widget = QWidget()
        ctrl_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ctrl_widget.setLayout(ctrl)

        # ── Shared widgets ────────────────────────────────────────────────────
        self.intent = IntentPanel()
        self.plan_panel = InvestigationPlanPanel()
        self.summary = ScrollableCard("Executive Summary")
        self.ai_reasoning = AIReasoningPanel()
        self.task_results = TaskResultsPanel()
        self.recommendations = RecommendationCard()
        self.executive_consensus = ExecutiveConsensusPanel()
        self.provider_card = ProviderCard()
        self.relationships = RelationshipExplorer()
        self.evidence = ScrollableCard("Evidence Summary")
        self.evidence_viewer = EvidenceViewer()
        self.prompt_panel = PromptPanel()

        # Evidence navigation row
        ev_nav = QHBoxLayout()
        ev_nav.setContentsMargins(0, 4, 0, 0)
        ev_nav.setSpacing(6)
        self._ev_prev_btn = QPushButton("← Prev")
        self._ev_prev_btn.setFixedWidth(70)
        self._ev_prev_btn.setEnabled(False)
        self._ev_prev_btn.clicked.connect(self._prev_evidence)
        self._ev_prev_btn.setToolTip("Previous evidence source, ranked by relevance")
        self._ev_next_btn = QPushButton("Next →")
        self._ev_next_btn.setFixedWidth(70)
        self._ev_next_btn.setEnabled(False)
        self._ev_next_btn.clicked.connect(self._next_evidence)
        self._ev_next_btn.setToolTip("Next evidence source, ranked by relevance")
        self._ev_idx_lbl = QLabel("")
        self._ev_idx_lbl.setStyleSheet("font-size:11px; color:#6B7280;")
        self._ev_idx_lbl.setAlignment(Qt.AlignCenter)
        ev_nav.addWidget(self._ev_prev_btn)
        ev_nav.addWidget(self._ev_idx_lbl, stretch=1)
        ev_nav.addWidget(self._ev_next_btn)
        ev_nav_widget = QWidget()
        ev_nav_widget.setLayout(ev_nav)
        ev_nav_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ── Tab: Summary ──────────────────────────────────────────────────────
        # Executive Summary + Recommendations share the top row (the summary
        # is usually only a couple of lines, so a full-width pane wasted the
        # space — user layout suggestion, v1.0 test item 9.1); AI Reasoning
        # and Executive Consensus split the bottom row with the extra room.
        summary_tab = QWidget()
        sum_lay = QVBoxLayout(summary_tab)
        sum_lay.setContentsMargins(0, 6, 0, 0)
        sum_lay.setSpacing(0)

        top_pair = QSplitter(Qt.Horizontal)
        top_pair.addWidget(self.summary)
        top_pair.addWidget(self.recommendations)
        top_pair.setSizes([560, 340])

        bottom_row = QSplitter(Qt.Horizontal)
        bottom_row.addWidget(self.ai_reasoning)
        bottom_row.addWidget(self.executive_consensus)
        bottom_row.setSizes([450, 450])

        sum_splitter = QSplitter(Qt.Vertical)
        sum_splitter.addWidget(top_pair)
        sum_splitter.addWidget(bottom_row)
        # Summary + Recommendations are short (a few lines); the reading
        # happens in AI Reasoning + Consensus below — give the bottom row
        # roughly 2/3 of the height (user v1.0 re-test, item 9.1).
        sum_splitter.setSizes([215, 445])
        sum_lay.addWidget(sum_splitter, 1)

        # ── Tab: Agents ───────────────────────────────────────────────────────
        agents_tab = QWidget()
        ag_lay = QVBoxLayout(agents_tab)
        ag_lay.setContentsMargins(0, 6, 0, 0)
        ag_lay.addWidget(self.task_results, 1)

        # ── Tab: Evidence ─────────────────────────────────────────────────────
        evidence_tab = QWidget()
        ev_lay = QVBoxLayout(evidence_tab)
        ev_lay.setContentsMargins(0, 6, 0, 0)
        ev_lay.setSpacing(0)

        ev_viewer_wrap = QWidget()
        ev_vw_lay = QVBoxLayout(ev_viewer_wrap)
        ev_vw_lay.setContentsMargins(0, 0, 0, 0)
        ev_vw_lay.setSpacing(0)
        ev_vw_lay.addWidget(self.evidence_viewer, 1)
        ev_vw_lay.addWidget(ev_nav_widget)

        # Side by side, not stacked — both panes get full height (user
        # layout suggestion, v1.0 test item 9.1).
        ev_splitter = QSplitter(Qt.Horizontal)
        ev_splitter.addWidget(ev_viewer_wrap)
        ev_splitter.addWidget(self.evidence)
        ev_splitter.setSizes([560, 380])
        ev_lay.addWidget(ev_splitter, 1)

        # ── Tab: Plan & Details ───────────────────────────────────────────────
        plan_tab = QWidget()
        plan_lay = QVBoxLayout(plan_tab)
        plan_lay.setContentsMargins(0, 6, 0, 0)
        plan_lay.setSpacing(0)

        top_row = QSplitter(Qt.Horizontal)
        top_row.addWidget(self.intent)
        top_row.addWidget(self.provider_card)
        top_row.setSizes([700, 200])

        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.addWidget(top_row)
        detail_splitter.addWidget(self.plan_panel)
        detail_splitter.addWidget(self.relationships)
        detail_splitter.addWidget(self.prompt_panel)
        detail_splitter.setSizes([130, 200, 200, 120])
        plan_lay.addWidget(detail_splitter, 1)

        # ── Assemble tabs ─────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; padding-top: 4px; }"
            "QTabBar::tab { padding: 7px 22px; font-size: 13px; font-weight: 500;"
            "  border: none; border-bottom: 2px solid transparent;"
            "  background: transparent; color: #6B7280; margin-right: 4px; }"
            "QTabBar::tab:hover { color: #111827; }"
            "QTabBar::tab:selected { color: #0B84FF; border-bottom: 2px solid #0B84FF; }"
        )
        self._tabs.addTab(summary_tab, "Summary")
        self._tabs.addTab(agents_tab, "Agents")
        self._tabs.addTab(evidence_tab, "Evidence")
        self._tabs.addTab(plan_tab, "Plan & Details")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(4)
        root.addWidget(self.search)
        root.addWidget(ctrl_widget)
        root.addWidget(self._tabs, stretch=1)
        self.setLayout(root)

    # ── Providers ─────────────────────────────────────────────────────────────

    def _populate_providers(self):
        self._provider_combo.clear()
        self._provider_combo.addItem("— Active Provider —", None)
        names = sorted(n for n in self.app.provider_manager.list_providers()
                       if n != "mock")
        for name in names:
            self._provider_combo.addItem(name, name)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        question = self.search.text().strip()
        if not question:
            return
        if self._worker and self._worker.isRunning():
            return

        self.search.button.setEnabled(False)
        self._status_lbl.setText("Starting investigation…")
        self._ev_prev_btn.setEnabled(False)
        self._ev_next_btn.setEnabled(False)
        self._ev_idx_lbl.setText("")
        self._ranked_evidence = []
        self._evidence_idx = 0

        provider_name = self._provider_combo.currentData()

        self._worker = _InvestigationWorker(self.engine, question, provider_name)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, step: str, current: int, total: int):
        self._status_lbl.setText(f"{step}  ({current}/{total})")

    def _on_error(self, message: str):
        self.search.button.setEnabled(True)
        self._status_lbl.setText(f"Error: {message}")

    def _on_finished(self, investigation: dict):
        self.search.button.setEnabled(True)
        self._tabs.setCurrentIndex(0)
        provider = investigation.get("provider", "")
        n_tasks = len(investigation.get("task_results", []))
        self._status_lbl.setText(f"Complete · {provider} · {n_tasks} agents ran")

        self.intent.set_request(investigation["request"])
        self.plan_panel.set_plan(investigation["plan"])
        self.provider_card.set_provider(provider)

        analysis = investigation["analysis"]

        if analysis is None:
            msg = (
                "No visibility data found in the database. "
                "Run a Visibility collection first to populate Atlas with AI responses."
            )
            self.summary.set_text(msg)
            self.ai_reasoning.set_reasoning(_stub_reasoning(msg))
            self.task_results.set_results([])
            self.executive_consensus.set_consensus(None)
            self.evidence_viewer.clear()
            return

        self.summary.set_text(investigation["summary"])
        self.ai_reasoning.set_reasoning(investigation["ai_reasoning"])
        self.task_results.set_results(investigation["task_results"])
        self.executive_consensus.set_consensus(investigation["executive_consensus"])

        self.prompt_panel.set_prompt(self.engine.ai_service.last_prompt)
        self.relationships.set_relationships(analysis["relationships"])

        recommendation = investigation["recommendation"]
        self.recommendations.set_recommendation(
            recommendation["text"],
            f"Confidence: {recommendation['confidence']}",
        )

        # Evidence navigation
        self._ranked_evidence = investigation["ranked_evidence"]
        self._evidence_idx = 0
        self._update_evidence_display()

        # Evidence summary panel (full ranked list as text)
        summary_obj = analysis["summary"]
        ranked = self._ranked_evidence
        if ranked:
            evidence_text = "\n\n".join(
                f"{item.source.upper()} | {item.prompt}\n{item.text[:300]}…"
                for item in ranked
            )
        else:
            evidence_text = (
                f"Responses analyzed: {summary_obj.evidence_count}\n"
                f"Brands found: {summary_obj.finding_counts_by_type.get('brand', 0)}\n"
                f"Features found: {summary_obj.finding_counts_by_type.get('feature', 0)}\n"
                f"Relationships found: {len(analysis['relationships'])}"
            )
        self.evidence.set_text(evidence_text)

    # ── Evidence navigation ────────────────────────────────────────────────────

    def _update_evidence_display(self):
        items = self._ranked_evidence
        n = len(items)
        if not items:
            self.evidence_viewer.clear()
            self._ev_idx_lbl.setText("No matching evidence")
            self._ev_prev_btn.setEnabled(False)
            self._ev_next_btn.setEnabled(False)
            return
        self.evidence_viewer.set_evidence(items[self._evidence_idx])
        self._ev_idx_lbl.setText(f"{self._evidence_idx + 1} of {n}")
        self._ev_prev_btn.setEnabled(self._evidence_idx > 0)
        self._ev_next_btn.setEnabled(self._evidence_idx < n - 1)

    def _prev_evidence(self):
        if self._evidence_idx > 0:
            self._evidence_idx -= 1
            self._update_evidence_display()

    def _next_evidence(self):
        if self._evidence_idx < len(self._ranked_evidence) - 1:
            self._evidence_idx += 1
            self._update_evidence_display()
