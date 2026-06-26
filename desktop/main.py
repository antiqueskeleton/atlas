import sys

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication


class ExecutivePage(QWidget):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        layout = QVBoxLayout()

        self.responses = QLabel("Responses Loaded: -")
        self.brands = QLabel("Brands Found: -")
        self.features = QLabel("Features Found: -")
        self.relationships = QLabel("Relationships: -")

        self.button = QPushButton("Analyze Dataset")
        self.button.clicked.connect(self.run_analysis)

        layout.addWidget(QLabel("<h1>Atlas Executive Dashboard</h1>"))
        layout.addWidget(self.responses)
        layout.addWidget(self.brands)
        layout.addWidget(self.features)
        layout.addWidget(self.relationships)
        layout.addSpacing(20)
        layout.addWidget(self.button)
        layout.addStretch()

        self.setLayout(layout)

    def run_analysis(self):

        result = self.app.analyze()

        summary = result["summary"]

        self.responses.setText(
            f"Responses Loaded: {summary.evidence_count}"
        )

        self.brands.setText(
            f"Brands Found: {summary.finding_counts_by_type.get('brand',0)}"
        )

        self.features.setText(
            f"Features Found: {summary.finding_counts_by_type.get('feature',0)}"
        )

        self.relationships.setText(
            f"Relationships: {len(result['relationships'])}"
        )


class AtlasMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Atlas AI Intelligence Platform")
        self.resize(1200, 800)

        tabs = QTabWidget()

        tabs.addTab(ExecutivePage(), "🏠 Executive")
        tabs.addTab(QWidget(), "🔍 Investigations")
        tabs.addTab(QWidget(), "📈 Trends")
        tabs.addTab(QWidget(), "🧠 Knowledge")
        tabs.addTab(QWidget(), "📂 Projects")

        self.setCentralWidget(tabs)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")


def main():

    app = QApplication(sys.argv)

    window = AtlasMainWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()