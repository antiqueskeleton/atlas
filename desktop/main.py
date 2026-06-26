import sys

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QFrame,
)

from app.atlas_application import AtlasApplication


class ExecutivePage(QWidget):
    def __init__(self):
        super().__init__()
        self.app = AtlasApplication()

        layout = QVBoxLayout()

        title = QLabel("Executive Intelligence")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")

        self.responses = QLabel("Responses Loaded: -")
        self.brands = QLabel("Brands Found: -")
        self.features = QLabel("Features Found: -")
        self.relationships = QLabel("Relationships: -")

        self.button = QPushButton("Analyze Dataset")
        self.button.clicked.connect(self.run_analysis)

        layout.addWidget(title)
        layout.addSpacing(10)
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

        self.responses.setText(f"Responses Loaded: {summary.evidence_count}")
        self.brands.setText(f"Brands Found: {summary.finding_counts_by_type.get('brand', 0)}")
        self.features.setText(f"Features Found: {summary.finding_counts_by_type.get('feature', 0)}")
        self.relationships.setText(f"Relationships: {len(result['relationships'])}")


class PlaceholderPage(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()

        layout = QVBoxLayout()

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 26px; font-weight: bold;")

        body = QLabel(subtitle)
        body.setStyleSheet("font-size: 15px;")

        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch()

        self.setLayout(layout)


class AtlasMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Atlas AI Intelligence Platform")
        self.resize(1300, 850)

        self.build_menu()

        main_widget = QWidget()
        main_layout = QHBoxLayout()

        self.nav = QListWidget()
        self.nav.addItems([
            "🏠 Executive",
            "🔍 Investigations",
            "📈 Trends",
            "🧠 Knowledge",
            "📂 Projects",
        ])
        self.nav.setFixedWidth(220)
        self.nav.setCurrentRow(0)

        self.pages = QTabWidget()
        self.pages.tabBar().hide()

        self.pages.addTab(ExecutivePage(), "Executive")
        self.pages.addTab(
            PlaceholderPage(
                "Investigations",
                "Ask Atlas why a brand, feature, or competitor is winning."
            ),
            "Investigations"
        )
        self.pages.addTab(
            PlaceholderPage(
                "Trends",
                "Track changes in AI recommendations over time."
            ),
            "Trends"
        )
        self.pages.addTab(
            PlaceholderPage(
                "Knowledge",
                "Manage brands, features, products, personas, and market questions."
            ),
            "Knowledge"
        )
        self.pages.addTab(
            PlaceholderPage(
                "Projects",
                "Open, save, and manage Atlas intelligence projects."
            ),
            "Projects"
        )

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)

        main_layout.addWidget(self.nav)
        main_layout.addWidget(divider)
        main_layout.addWidget(self.pages)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    def build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        file_menu.addAction("New Project")
        file_menu.addAction("Open Project")
        file_menu.addAction("Save Project")
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        investigation_menu = menu.addMenu("Investigation")
        investigation_menu.addAction("New Investigation")
        investigation_menu.addAction("Run Analysis")

        tools_menu = menu.addMenu("Tools")
        tools_menu.addAction("Import Responses")
        tools_menu.addAction("Manage Knowledge")

        help_menu = menu.addMenu("Help")
        help_menu.addAction("About Atlas")


def main():
    app = QApplication(sys.argv)
    window = AtlasMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()