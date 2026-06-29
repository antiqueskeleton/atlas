from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWidgets import QPushButton

from app.atlas_application import AtlasApplication
from desktop.pages.home_page import HomePage
from desktop.pages.investigation_page import InvestigationPage
from desktop.pages.trends_page import TrendsPage
from desktop.pages.knowledge_page import KnowledgePage
from desktop.pages.intelligence_page import IntelligencePage
from desktop.pages.settings_page import SettingsPage
from desktop.pages.visibility_page import VisibilityPage
from desktop.theme.colors import NAVY, SLATE, STEEL, SILVER, LIGHT, PRIMARY, TEXT_MUTED
from desktop.updater import UpdateChecker, APP_VERSION


_NAV_ITEMS = [
    ("🏠", "Home"),
    ("🔍", "Investigate"),
    ("👁", "Visibility"),
    ("💡", "Intelligence"),
    ("📈", "Trends"),
    ("🧠", "Knowledge"),
    ("⚙", "Settings"),
]


class AtlasMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.app = AtlasApplication()

        self.setWindowTitle("Atlas — AI Intelligence Platform")
        self.resize(1340, 860)
        self.setMinimumSize(1100, 700)

        self._build_menu()
        self._build_layout()

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Atlas AI  v{APP_VERSION}  —  Ready.")

        self._start_update_check()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        file_menu.addAction("New Project")
        file_menu.addAction("Open Project")
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        tools_menu = menu.addMenu("Tools")
        import_action = tools_menu.addAction("Import Responses")
        import_action.triggered.connect(self._import_responses)
        tools_menu.addAction("Manage Knowledge")

        help_menu = menu.addMenu("Help")
        help_menu.addAction("About Atlas")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        root_widget = QWidget()
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_nav())
        root_layout.addWidget(self._build_pages())

        root_widget.setLayout(root_layout)
        self.setCentralWidget(root_widget)

    def _build_nav(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(210)
        panel.setStyleSheet(f"background: {NAVY};")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Brand header ──────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(76)
        header.setStyleSheet(
            f"background: {NAVY}; border-bottom: 1px solid {STEEL};"
        )
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(16, 14, 16, 12)
        h_lay.setSpacing(2)

        brand = QLabel("ATLAS")
        brand.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {PRIMARY}; "
            "letter-spacing: 4px; border: none; background: transparent;"
        )

        tagline = QLabel("AI INTELLIGENCE")
        tagline.setStyleSheet(
            f"font-size: 9px; color: {SILVER}; letter-spacing: 2px; "
            "border: none; background: transparent;"
        )

        h_lay.addWidget(brand)
        h_lay.addWidget(tagline)
        header.setLayout(h_lay)

        # ── Navigation list ───────────────────────────────────────────────────
        self.nav = QListWidget()
        self.nav.setObjectName("AtlasNav")
        for icon, label in _NAV_ITEMS:
            self.nav.addItem(f"  {icon}  {label}")
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        # ── Version footer ────────────────────────────────────────────────────
        version = QLabel("v 0.2  ·  Atlas AI")
        version.setStyleSheet(
            f"color: {STEEL}; font-size: 10px; padding: 10px 16px; "
            "border: none; background: transparent;"
        )
        version.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        layout.addWidget(header)
        layout.addWidget(self.nav)
        layout.addStretch()
        layout.addWidget(version)
        panel.setLayout(layout)
        return panel

    def _build_pages(self) -> QWidget:
        wrapper = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.pages = QTabWidget()
        self.pages.tabBar().hide()

        self.home_page       = HomePage(self.app)
        self.investigation_page = InvestigationPage(self.app)
        self.visibility_page = VisibilityPage(self.app)
        self.intelligence_page = IntelligencePage(self.app)

        self.pages.addTab(self.home_page,          "Home")
        self.pages.addTab(self.investigation_page,  "Investigate")
        self.pages.addTab(self.visibility_page,     "Visibility")
        self.pages.addTab(self.intelligence_page,   "Intelligence")
        self.pages.addTab(TrendsPage(self.app),     "Trends")
        self.pages.addTab(KnowledgePage(self.app),  "Knowledge")
        self.pages.addTab(SettingsPage(self.app),   "Settings")

        lay.addWidget(self.pages)
        wrapper.setLayout(lay)
        return wrapper

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_nav_changed(self, row: int):
        self.pages.setCurrentIndex(row)

    # ── Update checker ────────────────────────────────────────────────────────

    def _start_update_check(self):
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str, url: str, notes: str):
        bar = self.statusBar()
        bar.clearMessage()

        msg = QLabel(f"  Update available:  Atlas AI v{version}  —  {notes[:80] + '…' if len(notes) > 80 else notes}  ")
        msg.setStyleSheet("color: #0B84FF; font-weight: bold;")

        if url:
            btn = QPushButton(f"Download v{version}")
            btn.setStyleSheet(
                "QPushButton { background: #0B84FF; color: white; border: none; "
                "border-radius: 4px; padding: 3px 10px; font-size: 11px; }"
                "QPushButton:hover { background: #0056CC; }"
            )
            btn.clicked.connect(lambda: self._open_download(url))
            bar.addWidget(msg)
            bar.addWidget(btn)
        else:
            bar.showMessage(f"Update available: Atlas AI v{version} — check Firman portal.")

    def _open_download(self, url: str):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _import_responses(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import AI Responses", "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.home_page.run_analysis(file_path)
            self.statusBar().showMessage(f"Imported: {file_path}")
