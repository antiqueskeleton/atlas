from PySide6.QtWidgets import QLabel, QPushButton, QGridLayout, QVBoxLayout, QWidget

from app.atlas_application import AtlasApplication
from desktop.widgets.stat_card import StatCard


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        layout = QVBoxLayout()

        title = QLabel("Good Morning")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Here's what Atlas knows about your market today.")
        subtitle.setStyleSheet("font-size: 15px; color: #6B7280;")

        self.visibility_card = StatCard("AI Visibility Score", "71", "Sample score")
        self.responses_card = StatCard("Responses Loaded", "-", "Ready to analyze")
        self.brands_card = StatCard("Brands Found", "-", "")
        self.features_card = StatCard("Features Found", "-", "")
        self.relationships_card = StatCard("Relationships", "-", "")

        grid = QGridLayout()
        grid.addWidget(self.visibility_card, 0, 0)
        grid.addWidget(self.responses_card, 0, 1)
        grid.addWidget(self.brands_card, 0, 2)
        grid.addWidget(self.features_card, 1, 0)
        grid.addWidget(self.relationships_card, 1, 1)

        button = QPushButton("Analyze Dataset")
        button.clicked.connect(self.run_analysis)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addLayout(grid)
        layout.addSpacing(20)
        layout.addWidget(button)
        layout.addStretch()

        self.setLayout(layout)

    def run_analysis(self):
        result = self.app.analyze()
        summary = result["summary"]

        self.responses_card.set_value(summary.evidence_count)
        self.brands_card.set_value(summary.finding_counts_by_type.get("brand", 0))
        self.features_card.set_value(summary.finding_counts_by_type.get("feature", 0))
        self.relationships_card.set_value(len(result["relationships"]))