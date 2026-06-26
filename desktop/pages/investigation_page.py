from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from desktop.widgets.result_panel import ResultPanel
from desktop.widgets.search_bar import SearchBar
from desktop.widgets.recommendation_card import RecommendationCard
from desktop.widgets.relationship_explorer import RelationshipExplorer


class InvestigationPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app

        layout = QVBoxLayout()

        title = QLabel("Investigation Workspace")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Ask Atlas a business question and review the evidence.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        self.search = SearchBar(
            placeholder="Example: Why isn't Firman recommended for home backup?",
            button_text="Investigate"
        )
        self.search.connect(self.run)

        self.insights = ResultPanel("Insights")
        self.relationships = ResultPanel("Relationships")
        self.recommendations = RecommendationCard()
        self.evidence = ResultPanel("Evidence Summary")

        content = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(self.insights)
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
        result = self.app.analyze()

        insights = result["insights"]
        relationships = result["relationships"]
        summary = result["summary"]

        self.insights.set_text(
            "\n".join(
                insight.description
                for insight in insights
            )
        )

        self.relationships.set_relationships(relationships)

        self.recommendations.set_recommendation(
            "Review feature gaps around Quiet Operation, RV Ready, and Dual Fuel positioning.",
            "Confidence: Medium"
        )

        self.evidence.set_text(
            f"Responses analyzed: {summary.evidence_count}\n"
            f"Brands found: {summary.finding_counts_by_type.get('brand', 0)}\n"
            f"Features found: {summary.finding_counts_by_type.get('feature', 0)}\n"
            f"Relationships found: {len(relationships)}"
        )