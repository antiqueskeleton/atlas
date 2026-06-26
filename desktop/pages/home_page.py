from PySide6.QtWidgets import QLabel, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout, QWidget

from app.atlas_application import AtlasApplication
from desktop.widgets.stat_card import StatCard
from desktop.widgets.activity_feed import ActivityFeed
from desktop.widgets.dataset_card import DatasetCard
from desktop.widgets.dataset_list import DatasetList


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        root_layout = QHBoxLayout()

        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()

        title = QLabel("Good Morning")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Here's what Atlas knows about your market today.")
        subtitle.setStyleSheet("font-size: 15px; color: #6B7280;")

        self.dataset_list = DatasetList()
        self.current_dataset = DatasetCard()

        import_hint = QLabel("Import a response dataset to begin analysis.")
        import_hint.setStyleSheet("font-size: 13px; color: #6B7280;")

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

        button = QPushButton("Analyze Dataset")
        button.clicked.connect(self.run_analysis)

        left_panel.addWidget(QLabel("<h2>Datasets</h2>"))
        left_panel.addWidget(import_hint)
        left_panel.addSpacing(10)
        left_panel.addWidget(self.dataset_list)
        left_panel.addSpacing(10)
        left_panel.addWidget(button)
        left_panel.addStretch()

        grid = QGridLayout()
        grid.addWidget(self.current_dataset, 0, 0)
        grid.addWidget(self.visibility_card, 0, 1)
        grid.addWidget(self.responses_card, 0, 2)
        grid.addWidget(self.brands_card, 1, 0)
        grid.addWidget(self.features_card, 1, 1)
        grid.addWidget(self.relationships_card, 1, 2)

        right_panel.addWidget(title)
        right_panel.addWidget(subtitle)
        right_panel.addSpacing(20)
        right_panel.addLayout(grid)
        right_panel.addSpacing(20)
        right_panel.addWidget(self.activity_feed)
        right_panel.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(300)

        right_container = QWidget()
        right_container.setLayout(right_panel)

        root_layout.addWidget(left_container)
        root_layout.addWidget(right_container)

        self.setLayout(root_layout)

    def run_analysis(self, response_file=None):
        result = self.app.analyze(response_file)

        dataset = result["dataset"]
        summary = result["summary"]

        self.current_dataset.set_dataset(dataset)
        self.dataset_list.set_datasets(result["datasets"])

        self.responses_card.set_value(summary.evidence_count)
        self.brands_card.set_value(summary.finding_counts_by_type.get("brand", 0))
        self.features_card.set_value(summary.finding_counts_by_type.get("feature", 0))
        self.relationships_card.set_value(len(result["relationships"]))

        self.activity_feed.set_items([
            f"Loaded dataset: {dataset.name}",
            f"Analyzed {summary.evidence_count} responses",
            f"Generated {len(result['relationships'])} relationships",
        ])