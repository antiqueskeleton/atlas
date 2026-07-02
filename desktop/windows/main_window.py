from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
from desktop.pages.comp_shopping_page import CompShoppingPage
from desktop.pages.knowledge_page import KnowledgePage
from desktop.pages.intelligence_page import IntelligencePage
from desktop.pages.settings_page import SettingsPage
from desktop.pages.visibility_page import VisibilityPage
from desktop.theme.colors import NAVY, SLATE, STEEL, SILVER, LIGHT, PRIMARY, TEXT_MUTED
from desktop.updater import UpdateChecker, APP_VERSION


_NAV_ITEMS = [
    ("🏠", "Home",         "nav_home.png"),
    ("🔍", "Investigate",  "nav_investigate.png"),
    ("👁",  "Visibility",  "nav_visibility.png"),
    ("💡", "Intelligence", "nav_intelligence.png"),
    ("📈", "Trends",       "nav_trends.png"),
    ("🛒", "Comp Shop",    "nav_comp.png"),
    ("🧠", "Knowledge",    "nav_knowledge.png"),
    ("⚙",  "Settings",    "nav_settings.png"),
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
        guide_action = help_menu.addAction("Usage Guide")
        guide_action.triggered.connect(self._show_usage_guide)
        help_menu.addSeparator()
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
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for emoji, label, icon_file in _NAV_ITEMS:
            icon_path = _IMAGES_DIR / icon_file
            if icon_path.exists():
                item = QListWidgetItem(QIcon(str(icon_path)), f"  {label}")
            else:
                item = QListWidgetItem(f"  {emoji}  {label}")
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        # ── Collapse toggle button ────────────────────────────────────────────
        self._nav_toggle_btn = QPushButton("‹‹  Collapse")
        self._nav_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._nav_toggle_btn.setToolTip("Collapse navigation")
        self._nav_toggle_btn.setFixedHeight(40)
        self._nav_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: {SLATE}; color: {SILVER}; "
            f"border: none; border-top: 1px solid {STEEL}; "
            "font-size: 12px; font-weight: 600; padding: 4px 16px; text-align: left; }}"
            f"QPushButton:hover {{ color: white; background: #2D3F55; }}"
        )
        self._nav_toggle_btn.clicked.connect(self._toggle_nav)

        layout.addWidget(self._nav_header)
        layout.addWidget(self.nav, 1)
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

        if c:
            for i, (emoji, _, icon_file) in enumerate(_NAV_ITEMS):
                item = self.nav.item(i)
                if (_IMAGES_DIR / icon_file).exists():
                    item.setText("")
                else:
                    item.setText(emoji)
                item.setTextAlignment(Qt.AlignCenter)
            self.nav.setIconSize(QSize(30, 30))
            self.nav.setStyleSheet(f"""
                QListWidget#AtlasNav {{
                    background: {NAVY};
                    border: none;
                    outline: none;
                    padding: 6px 0;
                }}
                QListWidget#AtlasNav::item {{
                    color: {SILVER};
                    padding: 12px 0px;
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
            self._nav_toggle_btn.setText("››")
            self._nav_toggle_btn.setToolTip("Expand navigation")
            self._nav_toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {SLATE}; color: {SILVER}; "
                f"border: none; border-top: 1px solid {STEEL}; "
                "font-size: 16px; font-weight: bold; padding: 4px 0px; text-align: center; }}"
                f"QPushButton:hover {{ color: white; background: #2D3F55; }}"
            )
        else:
            for i, (emoji, label, icon_file) in enumerate(_NAV_ITEMS):
                item = self.nav.item(i)
                if (_IMAGES_DIR / icon_file).exists():
                    item.setText(f"  {label}")
                else:
                    item.setText(f"  {emoji}  {label}")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.nav.setIconSize(QSize(20, 20))
            self.nav.setStyleSheet("")
            self._nav_toggle_btn.setText("‹‹  Collapse")
            self._nav_toggle_btn.setToolTip("Collapse navigation")
            self._nav_toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {SLATE}; color: {SILVER}; "
                f"border: none; border-top: 1px solid {STEEL}; "
                "font-size: 12px; font-weight: 600; padding: 4px 16px; text-align: left; }}"
                f"QPushButton:hover {{ color: white; background: #2D3F55; }}"
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
        self.comp_shopping_page = CompShoppingPage(self.app)
        self.pages.addTab(self.comp_shopping_page,  "Comp Shop")
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
        elif row == 5:   # Comp Shop
            self.comp_shopping_page.refresh()

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
        tagline.setStyleSheet("font-size: 14px; color: #6B7280; font-weight: 500;")
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
        desc.setStyleSheet("font-size: 13px; color: #374151; line-height: 1.5;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        # Copyright with dweeb.co as link
        copy_lbl = QLabel("© 2026 <a href='https://dweeb.co' style='color:#0B84FF;'>dweeb.co</a>")
        copy_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        copy_lbl.setAlignment(Qt.AlignCenter)
        copy_lbl.setOpenExternalLinks(True)

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
        lay.addSpacing(12)
        lay.addWidget(copy_lbl)
        lay.addSpacing(16)
        lay.addLayout(btn_row)

        dlg.setLayout(lay)
        dlg.exec()

    def _show_usage_guide(self):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget,
        )
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("Atlas — Usage Guide")
        dlg.setFixedSize(560, 620)

        outer = QVBoxLayout()
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Header ─────────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background: #111827;")
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(32, 22, 32, 18)
        h_lay.setSpacing(2)
        title_lbl = QLabel("Usage Guide")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        sub_lbl = QLabel("What each page does and how they fit together.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        h_lay.addWidget(title_lbl)
        h_lay.addWidget(sub_lbl)
        header.setLayout(h_lay)

        # ── Scrollable body ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: white;")

        body = QWidget()
        body.setStyleSheet("background: white;")
        b_lay = QVBoxLayout()
        b_lay.setContentsMargins(32, 20, 32, 20)
        b_lay.setSpacing(16)

        def _section(title: str, body_text: str) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(3)
            t = QLabel(title)
            t.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #111827;")
            d = QLabel(body_text)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 12px; color: #4B5563; line-height: 1.4;")
            lay.addWidget(t)
            lay.addWidget(d)
            w.setLayout(lay)
            return w

        b_lay.addWidget(_section(
            "Recommended Workflow",
            "1. Settings — set your Target Brand and add AI provider API keys.  "
            "2. Visibility — run a collection to gather AI responses (this is the raw data "
            "every other page builds on).  3. Trends &amp; Intelligence — analyze that data over "
            "time and generate briefings.  4. Investigate — ask specific follow-up questions."
        ))

        pages = [
            ("Home",
             "Dashboard snapshot — mention rate, responses stored, run counts, and a recent "
             "activity feed. No actions here, just a quick status check."),
            ("Investigate",
             "Ask a natural-language business question (e.g. \"Why is Honda winning on Amazon "
             "reviews?\"). Atlas dispatches specialized AI agents to research it and returns a "
             "synthesized answer with ranked evidence and recommendations."),
            ("Visibility",
             "The core data collection engine. Select prompt families and AI providers, then "
             "Run Visibility Collection to query every selected provider with every selected "
             "prompt and store the responses. Run this regularly — Trends and Intelligence both "
             "depend on this data existing."),
            ("Intelligence",
             "Synthesizes stored Visibility responses into an executive briefing, consumer "
             "personas, buying-journey insights, and strategic opportunities. Requires Visibility "
             "data first. Export the result as PDF or Word."),
            ("Trends",
             "Charts how visibility score, brand standing, provider performance, feature "
             "associations, and first-mention position change across multiple Visibility runs. "
             "Time-series charts need at least 2 days of collection history to render."),
            ("Comp Shop",
             "Currently being rebuilt (Coming Soon) — will compare pricing and specs across "
             "brands using an AI-assisted product catalog."),
            ("Knowledge",
             "Manage the reference data Atlas uses for detection: Brands, Features, Personas, "
             "Scenarios, Stages, Prompt Families, and Prompts. \"Discover Brands\" scans AI "
             "responses for newly-mentioned competitor brands not yet tracked."),
            ("Settings",
             "Configure your Target Brand, active AI provider, and per-provider API keys (use "
             "Test to verify a key works). Run Health Check to verify the database and "
             "configuration are sound."),
        ]
        for name, desc in pages:
            b_lay.addWidget(_section(name, desc))

        b_lay.addStretch()
        body.setLayout(b_lay)
        scroll.setWidget(body)

        # ── Footer ─────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: #FAFAFA; border-top: 1px solid #E5E7EB;")
        f_lay = QHBoxLayout()
        f_lay.setContentsMargins(32, 12, 32, 12)
        f_lay.setAlignment(Qt.AlignCenter)
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(110)
        close_btn.setStyleSheet(
            "QPushButton { background: #111827; color: white; border: none; "
            "border-radius: 5px; padding: 6px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #374151; }"
        )
        close_btn.clicked.connect(dlg.accept)
        f_lay.addWidget(close_btn)
        footer.setLayout(f_lay)

        outer.addWidget(header)
        outer.addWidget(scroll, 1)
        outer.addWidget(footer)
        dlg.setLayout(outer)
        dlg.exec()

    def _import_responses(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Import Responses",
            "AI responses are now collected directly through the Visibility page.\n\n"
            "Navigate to Visibility → select a prompt set → Run to collect and store responses.",
        )
