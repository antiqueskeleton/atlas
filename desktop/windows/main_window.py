from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from app.atlas_application import AtlasApplication
from desktop.pages.home_page import HomePage
from desktop.pages.investigation_page import InvestigationPage
from desktop.pages.trends_page import TrendsPage
from desktop.pages.knowledge_page import KnowledgePage
from desktop.pages.intelligence_page import IntelligencePage
from desktop.pages.settings_page import SettingsPage
from desktop.pages.visibility_page import VisibilityPage


class AtlasMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        self.setWindowTitle("Atlas AI Intelligence Platform")
        self.resize(1300, 850)
        self.setMinimumSize(1100, 700)

        self.build_menu()
        self.build_layout()

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

        import_action = tools_menu.addAction("Import Responses")
        import_action.triggered.connect(self.import_responses)

        tools_menu.addAction("Manage Knowledge")

        help_menu = menu.addMenu("Help")
        help_menu.addAction("About Atlas")

    def build_layout(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        self.nav = QListWidget()
        self.nav.addItems([
            "🏠 Home",
            "🔍 Investigate",
            "👁 Visibility",
            "💡 Intelligence",
            "📈 Trends",
            "🧠 Knowledge",
            "⚙ Settings",
        ])
        self.nav.setFixedWidth(220)
        self.nav.setCurrentRow(0)

        self.pages = QTabWidget()
        self.pages.tabBar().hide()

        self.home_page = HomePage(self.app)
        self.investigation_page = InvestigationPage(self.app)
        self.visibility_page = VisibilityPage(self.app)
        self.intelligence_page = IntelligencePage(self.app)

        self.pages.addTab(self.home_page, "Home")
        self.pages.addTab(self.investigation_page, "Investigate")
        self.pages.addTab(self.visibility_page, "Visibility")
        self.pages.addTab(self.intelligence_page, "Intelligence")
        self.pages.addTab(TrendsPage(self.app), "Trends")
        self.pages.addTab(KnowledgePage(self.app), "Knowledge")
        self.pages.addTab(SettingsPage(self.app), "Settings")

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)

        main_layout.addWidget(self.nav)
        main_layout.addWidget(divider)
        main_layout.addWidget(self.pages)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def import_responses(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import AI Responses",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.home_page.run_analysis(file_path)
            self.statusBar().showMessage(f"Imported and analyzed: {file_path}")