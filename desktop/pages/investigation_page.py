from PySide6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget

from backend.investigations.investigation_engine import InvestigationEngine
from desktop.widgets.result_panel import ResultPanel
from desktop.widgets.search_bar import SearchBar
from desktop.widgets.recommendation_card import RecommendationCard
from desktop.widgets.relationship_explorer import RelationshipExplorer


class InvestigationPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.engine = InvestigationEngine(self.app)

        layout = QVBoxLayout()

        title = QLabel("Investigation Workspace")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Ask Atlas a business question and review the evidence.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        self.search = SearchBar(
            placeholder="Example: Why didn't Firman win against Champion?",
            button_text="Investigate"
        )
        self.search.connect(self.run)

        self.summary = ResultPanel("Executive Summary")
        self.relationships = RelationshipExplorer()
        self.recommendations = RecommendationCard()
        self.evidence = ResultPanel("Evidence Summary")

        content = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(self.summary)
        left.addWidget(self.recommendations)

        right = QVBoxLayout()
        right.addWidget(self.relationships)
        right.addWidget(self.evidence)

        content.addLayout(left)
        content.addLayout(right)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(15)
        layout.addWidget(self.search)
        layout.addSpacing(20)
        layout.addLayout(content)
        layout.addStretch()

        self.setLayout(layout)

    def run(self):
        question = self.search.text()

        investigation = self.engine.investigate(question)

        analysis = investigation["analysis"]

        if analysis is None:
            self.summary.set_text("No active dataset is available. Import a dataset first.")
            return

        summary = analysis["summary"]
        relationships = analysis["relationships"]

        self.summary.set_text(investigation["summary"])

        self.relationships.set_relationships(relationships)

        self.recommendations.set_recommendation(
            "Improve messaging around features where competitors have stronger AI associations.",
            "Confidence: Medium"
        )

        self.evidence.set_text(
            f"Responses analyzed: {summary.evidence_count}\n"
            f"Brands found: {summary.finding_counts_by_type.get('brand', 0)}\n"
            f"Features found: {summary.finding_counts_by_type.get('feature', 0)}\n"
            f"Relationships found: {len(relationships)}"
        )