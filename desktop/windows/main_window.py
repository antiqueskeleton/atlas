from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
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

_IMAGES_DIR = Path(__file__).resolve().parents[2] / "images"

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
        file_menu.addAction("Exit", self.close)

        tools_menu = menu.addMenu("Tools")
        import_action = tools_menu.addAction("Import Responses")
        import_action.triggered.connect(self._import_responses)
        knowledge_action = tools_menu.addAction("Manage Knowledge")
        knowledge_action.triggered.connect(lambda: self.nav.setCurrentRow(5))

        help_menu = menu.addMenu("Help")
        about_action = help_menu.addAction("About Atlas")
        about_action.triggered.connect(self._show_about)

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
        header.setStyleSheet(
            f"background: {NAVY}; border-bottom: 1px solid {STEEL};"
        )
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(8, 8, 8, 8)
        h_lay.setSpacing(0)

        logo_lbl = QLabel()
        logo_lbl.setStyleSheet("border: none; background: transparent;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_pix = QPixmap(str(_IMAGES_DIR / "atlas_sidebar.png"))
        if not logo_pix.isNull():
            scaled = logo_pix.scaledToWidth(194, Qt.SmoothTransformation)
            logo_lbl.setPixmap(scaled)
            header.setFixedHeight(scaled.height() + 16)
        else:
            logo_lbl.setText("ATLAS")
            logo_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {PRIMARY}; "
                "letter-spacing: 4px; border: none; background: transparent;"
            )
            header.setFixedHeight(76)

        h_lay.addWidget(logo_lbl)
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
        if row == 0:
            self.home_page.refresh()

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

    def _show_about(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("About Atlas")
        dlg.setFixedWidth(380)

        lay = QVBoxLayout()
        lay.setSpacing(10)
        lay.setContentsMargins(28, 24, 28, 20)

        name = QLabel("Atlas AI")
        name.setStyleSheet("font-size: 22px; font-weight: bold;")
        name.setAlignment(Qt.AlignCenter)

        version = QLabel(f"Version {APP_VERSION}")
        version.setStyleSheet("font-size: 13px; color: #6B7280;")
        version.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "AI Intelligence Platform\n"
            "Firman Power Equipment\n\n"
            "Tracks brand visibility, market perception, and\n"
            "competitive positioning across AI providers."
        )
        desc.setStyleSheet("font-size: 12px; color: #374151;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E5E7EB;")

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dlg.accept)

        btn_row = QVBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(close_btn)

        lay.addWidget(name)
        lay.addWidget(version)
        lay.addSpacing(6)
        lay.addWidget(desc)
        lay.addSpacing(6)
        lay.addWidget(sep)
        lay.addSpacing(4)
        lay.addLayout(btn_row)

        dlg.setLayout(lay)
        dlg.exec()

    def _import_responses(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Import Responses",
            "AI responses are now collected directly through the Visibility page.\n\n"
            "Navigate to Visibility → select a prompt set → Run to collect and store responses.",
        )
