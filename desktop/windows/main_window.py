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
        self._nav_collapsed = False
        self._nav_panel = QWidget()
        self._nav_panel.setFixedWidth(210)
        self._nav_panel.setStyleSheet(f"background: {NAVY};")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Brand header ──────────────────────────────────────────────────────
        self._nav_header = QWidget()
        self._nav_header.setStyleSheet(
            f"background: {NAVY}; border-bottom: 1px solid {STEEL};"
        )
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(8, 8, 8, 8)
        h_lay.setSpacing(0)

        # Full sidebar logo (expanded mode)
        self._logo_full = QLabel()
        self._logo_full.setStyleSheet("border: none; background: transparent;")
        self._logo_full.setAlignment(Qt.AlignCenter)
        logo_pix = QPixmap(str(_IMAGES_DIR / "atlas_sidebar.png"))
        if not logo_pix.isNull():
            scaled = logo_pix.scaledToWidth(194, Qt.SmoothTransformation)
            self._logo_full.setPixmap(scaled)
            self._nav_header_height = scaled.height() + 16
        else:
            self._logo_full.setText("ATLAS")
            self._logo_full.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {PRIMARY}; "
                "letter-spacing: 4px; border: none; background: transparent;"
            )
            self._nav_header_height = 76
        self._nav_header.setFixedHeight(self._nav_header_height)

        # Small icon logo (collapsed mode)
        self._logo_icon = QLabel()
        self._logo_icon.setAlignment(Qt.AlignCenter)
        self._logo_icon.setStyleSheet("border: none; background: transparent;")
        icon_pix = QPixmap(str(_IMAGES_DIR / "atlas_icon.png"))
        if not icon_pix.isNull():
            self._logo_icon.setPixmap(icon_pix.scaledToWidth(38, Qt.SmoothTransformation))
        else:
            self._logo_icon.setText("A")
            self._logo_icon.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {PRIMARY}; "
                "border: none; background: transparent;"
            )
        self._logo_icon.setVisible(False)

        h_lay.addWidget(self._logo_full)
        h_lay.addWidget(self._logo_icon)
        self._nav_header.setLayout(h_lay)

        # ── Navigation list ───────────────────────────────────────────────────
        self.nav = QListWidget()
        self.nav.setObjectName("AtlasNav")
        for icon, label in _NAV_ITEMS:
            self.nav.addItem(f"  {icon}  {label}")
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        # ── Version footer ────────────────────────────────────────────────────
        self._nav_version = QLabel("v 0.7  ·  Atlas AI")
        self._nav_version.setStyleSheet(
            f"color: {STEEL}; font-size: 10px; padding: 10px 16px; "
            "border: none; background: transparent;"
        )
        self._nav_version.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        # ── Collapse toggle button ────────────────────────────────────────────
        self._nav_toggle_btn = QPushButton("«  Collapse")
        self._nav_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._nav_toggle_btn.setToolTip("Collapse navigation")
        self._nav_toggle_btn.setFixedHeight(34)
        self._nav_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {STEEL}; border: none; "
            "font-size: 12px; padding: 4px 16px; text-align: left; }}"
            f"QPushButton:hover {{ color: {PRIMARY}; background: {SLATE}; }}"
        )
        self._nav_toggle_btn.clicked.connect(self._toggle_nav)

        layout.addWidget(self._nav_header)
        layout.addWidget(self.nav)
        layout.addStretch()
        layout.addWidget(self._nav_version)
        layout.addWidget(self._nav_toggle_btn)
        self._nav_panel.setLayout(layout)
        return self._nav_panel

    def _toggle_nav(self):
        self._nav_collapsed = not self._nav_collapsed
        c = self._nav_collapsed

        self._nav_panel.setFixedWidth(64 if c else 210)
        self._logo_full.setVisible(not c)
        self._logo_icon.setVisible(c)
        self._nav_header.setFixedHeight(56 if c else self._nav_header_height)
        self._nav_version.setVisible(not c)

        if c:
            for i, (icon, _) in enumerate(_NAV_ITEMS):
                item = self.nav.item(i)
                item.setText(icon)
                item.setTextAlignment(Qt.AlignCenter)
            self.nav.setStyleSheet(f"""
                QListWidget#AtlasNav {{
                    background: {NAVY};
                    border: none;
                    outline: none;
                    padding: 6px 0;
                }}
                QListWidget#AtlasNav::item {{
                    color: {SILVER};
                    padding: 14px 0px;
                    border-radius: 6px;
                    margin: 2px 4px;
                    font-size: 22px;
                }}
                QListWidget#AtlasNav::item:hover {{
                    background: {SLATE};
                    color: {LIGHT};
                }}
                QListWidget#AtlasNav::item:selected {{
                    background: {PRIMARY};
                    color: white;
                }}
            """)
            self._nav_toggle_btn.setText("»")
            self._nav_toggle_btn.setToolTip("Expand navigation")
            self._nav_toggle_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {STEEL}; border: none; "
                "font-size: 16px; font-weight: bold; padding: 4px 0px; text-align: center; }}"
                f"QPushButton:hover {{ color: {PRIMARY}; background: {SLATE}; }}"
            )
        else:
            for i, (icon, label) in enumerate(_NAV_ITEMS):
                item = self.nav.item(i)
                item.setText(f"  {icon}  {label}")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.nav.setStyleSheet("")
            self._nav_toggle_btn.setText("«  Collapse")
            self._nav_toggle_btn.setToolTip("Collapse navigation")
            self._nav_toggle_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {STEEL}; border: none; "
                "font-size: 12px; padding: 4px 16px; text-align: left; }}"
                f"QPushButton:hover {{ color: {PRIMARY}; background: {SLATE}; }}"
            )

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
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("About Atlas")
        dlg.setFixedWidth(420)

        lay = QVBoxLayout()
        lay.setSpacing(0)
        lay.setContentsMargins(32, 28, 32, 24)

        # App name + version badge row
        name_lbl = QLabel("Atlas AI")
        name_lbl.setStyleSheet("font-size: 26px; font-weight: 700; color: #111827; letter-spacing: 1px;")
        name_lbl.setAlignment(Qt.AlignCenter)

        ver_badge = QLabel(f"v{APP_VERSION}")
        ver_badge.setAlignment(Qt.AlignCenter)
        ver_badge.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #0B84FF; "
            "background: #EFF6FF; border: 1px solid #BFDBFE; "
            "border-radius: 10px; padding: 2px 10px;"
        )
        ver_badge.setFixedHeight(22)

        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(ver_badge)

        tagline = QLabel("AI Intelligence Platform")
        tagline.setStyleSheet("font-size: 13px; color: #6B7280; font-weight: 500;")
        tagline.setAlignment(Qt.AlignCenter)

        def _sep():
            s = QLabel()
            s.setFixedHeight(1)
            s.setStyleSheet("background: #E5E7EB; margin: 0px;")
            return s

        # Description
        desc = QLabel(
            "Atlas tracks brand visibility, market perception, and competitive\n"
            "positioning across AI providers — so you always know how your\n"
            "brand appears in the answers people are reading."
        )
        desc.setStyleSheet("font-size: 12px; color: #374151; line-height: 1.5;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        # Built by
        built_lbl = QLabel("Built by  <a href='https://dweeb.co' style='color:#0B84FF;'>dweeb.co</a>")
        built_lbl.setStyleSheet("font-size: 12px; color: #6B7280;")
        built_lbl.setAlignment(Qt.AlignCenter)
        built_lbl.setOpenExternalLinks(True)

        # Copyright
        copy_lbl = QLabel("© 2026 dweeb.co  ·  All rights reserved.")
        copy_lbl.setStyleSheet("font-size: 10px; color: #9CA3AF;")
        copy_lbl.setAlignment(Qt.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(110)
        close_btn.setStyleSheet(
            "QPushButton { background: #111827; color: white; border: none; "
            "border-radius: 5px; padding: 6px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #374151; }"
        )
        close_btn.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(close_btn)

        lay.addWidget(name_lbl)
        lay.addSpacing(6)
        lay.addLayout(badge_row)
        lay.addSpacing(4)
        lay.addWidget(tagline)
        lay.addSpacing(16)
        lay.addWidget(_sep())
        lay.addSpacing(14)
        lay.addWidget(desc)
        lay.addSpacing(14)
        lay.addWidget(_sep())
        lay.addSpacing(10)
        lay.addWidget(built_lbl)
        lay.addSpacing(4)
        lay.addWidget(copy_lbl)
        lay.addSpacing(16)
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
