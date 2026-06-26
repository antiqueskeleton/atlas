from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from desktop.widgets.result_panel import ResultPanel
from desktop.widgets.search_bar import SearchBar


class InvestigationPage(QWidget):

    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        layout = QVBoxLayout()

        title = QLabel("Investigation Workspace")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel(
            "Ask Atlas a business question."
        )
        subtitle.setStyleSheet(
            "font-size:15px;color:#6B7280;"
        )

        self.search = SearchBar(
            placeholder="Example: Why isn't Firman recommended for home backup?",
            button_text="Run Investigation"
        )
        self.search.connect(self.run)

        self.insights = ResultPanel("Insights")

        self.relationships = ResultPanel("Relationships")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(15)
        layout.addWidget(self.search)
        layout.addSpacing(20)
        layout.addWidget(self.insights)
        layout.addWidget(self.relationships)
        layout.addStretch()

        self.setLayout(layout)

    def run(self):

        result = self.app.analyze()

        insights = result["insights"]

        relationships = result["relationships"]

        self.insights.set_text(

            "\n".join(
                insight.description
                for insight in insights
            )

        )

        self.relationships.set_text(

            "\n".join(
                f"{r.source} → {r.target}"
                for r in relationships[:15]
            )

        )