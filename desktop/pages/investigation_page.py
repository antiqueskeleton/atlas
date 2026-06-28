from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QScrollArea,
)

from backend.investigations.investigation_engine import InvestigationEngine
from desktop.widgets.result_panel import ResultPanel
from desktop.widgets.search_bar import SearchBar
from desktop.widgets.recommendation_card import RecommendationCard
from desktop.widgets.relationship_explorer import RelationshipExplorer
from desktop.widgets.intent_panel import IntentPanel
from desktop.widgets.ai_reasoning_panel import AIReasoningPanel
from desktop.widgets.provider_card import ProviderCard
from desktop.widgets.scrollable_card import ScrollableCard


class InvestigationPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.engine = InvestigationEngine(self.app)

        root_layout = QVBoxLayout()

        title = QLabel("Investigation Workspace")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Ask Atlas a business question and review the evidence.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        self.search = SearchBar(
            placeholder="Example: Why did Firman lose to Champion for home backup?",
            button_text="Investigate"
        )
        self.search.connect(self.run)

        self.intent = IntentPanel()
        self.summary = ScrollableCard("Executive Summary")
        self.ai_reasoning = AIReasoningPanel()
        self.recommendations = RecommendationCard()

        self.provider_card = ProviderCard()
        self.relationships = RelationshipExplorer()
        self.evidence = ScrollableCard("Evidence Summary")

        content_widget = QWidget()
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(self.intent)
        left.addWidget(self.summary)
        left.addWidget(self.ai_reasoning)
        left.addWidget(self.recommendations)
        left.addStretch()

        right = QVBoxLayout()
        right.setSpacing(16)
        right.addWidget(self.provider_card)
        right.addWidget(self.relationships)
        right.addWidget(self.evidence)
        right.addStretch()

        left_container = QWidget()
        left_container.setLayout(left)

        right_container = QWidget()
        right_container.setLayout(right)

        content_layout.addWidget(left_container, 3)
        content_layout.addWidget(right_container, 2)

        content_widget.setLayout(content_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)
        root_layout.addSpacing(12)
        root_layout.addWidget(self.search)
        root_layout.addSpacing(12)
        root_layout.addWidget(scroll)

        self.setLayout(root_layout)

    def run(self):
        question = self.search.text()

        investigation = self.engine.investigate(question)

        self.intent.set_request(investigation["request"])
        self.provider_card.set_provider(investigation["provider"])

        analysis = investigation["analysis"]

        if analysis is None:
            self.summary.set_text("No active dataset is available. Import a dataset first.")
            return

        summary = analysis["summary"]
        relationships = analysis["relationships"]

        self.summary.set_text(investigation["summary"])
        self.ai_reasoning.set_reasoning(investigation["ai_reasoning"])
        self.relationships.set_relationships(relationships)

        recommendation = investigation["recommendation"]
        self.recommendations.set_recommendation(
            recommendation["text"],
            f"Confidence: {recommendation['confidence']}"
        )

        ranked_evidence = investigation["ranked_evidence"]

        evidence_text = "\n\n".join(
            f"{item.source.upper()} | {item.prompt}\n{item.text[:300]}..."
            for item in ranked_evidence
        )

        if not evidence_text:
            evidence_text = (
                f"Responses analyzed: {summary.evidence_count}\n"
                f"Brands found: {summary.finding_counts_by_type.get('brand', 0)}\n"
                f"Features found: {summary.finding_counts_by_type.get('feature', 0)}\n"
                f"Relationships found: {len(relationships)}"
            )

        self.evidence.set_text(evidence_text)