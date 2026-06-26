from PySide6.QtWidgets import QLabel, QPushButton, QGridLayout, QVBoxLayout, QWidget

from app.atlas_application import AtlasApplication
from desktop.widgets.stat_card import StatCard
from desktop.widgets.activity_feed import ActivityFeed


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        layout = QVBoxLayout()

        title = QLabel("Good Morning")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Here's what Atlas knows about your market today.")
        subtitle.setStyleSheet("font-size: 15px; color: #6B7280;")

        self.dataset_card = StatCard("Active Dataset", "-", "No dataset loaded")
        self.visibility_card = StatCard("AI Visibility Score", "71", "Sample score")
        self.responses_card = StatCard("Responses Loaded", "-", "Ready to analyze")
        self.brands_card = StatCard("Brands Found", "-", "")
        self.features_card = StatCard("Features Found", "-", "")
        self.relationships_card = StatCard("Relationships", "-", "")

        self.activity_feed = ActivityFeed("Recent Activity")
        self.activity_feed.set_items([
            "Atlas workspace opened",
            "Evidence service ready",
            "Analyst registry loaded",
        ])

        grid = QGridLayout()
        grid.addWidget(self.dataset_card, 0, 0)
        grid.addWidget(self.visibility_card, 0, 1)
        grid.addWidget(self.responses_card, 0, 2)
        grid.addWidget(self.brands_card, 1, 0)
        grid.addWidget(self.features_card, 1, 1)
        grid.addWidget(self.relationships_card, 1, 2)

        button = QPushButton("Analyze Dataset")
        button.clicked.connect(self.run_analysis)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addLayout(grid)

        layout.addSpacing(20)
        layout.addWidget(self.activity_feed)

        layout.addSpacing(20)
        layout.addWidget(button)

        layout.addStretch()

        self.setLayout(layout)

    def run_analysis(self, response_file=None):
        result = self.app.analyze(response_file)

        dataset = result["dataset"]
        summary = result["summary"]

        self.dataset_card.set_value(dataset.name)
        self.dataset_card.set_subtitle(f"{dataset.source} • {dataset.status}")

        self.responses_card.set_value(summary.evidence_count)
        self.brands_card.set_value(summary.finding_counts_by_type.get("brand", 0))
        self.features_card.set_value(summary.finding_counts_by_type.get("feature", 0))
        self.relationships_card.set_value(len(result["relationships"]))

        self.activity_feed.set_items([
            f"Loaded dataset: {dataset.name}",
            f"Analyzed {summary.evidence_count} responses",
            f"Generated {len(result['relationships'])} relationships",
        ])