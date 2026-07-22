import sys
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Frozen-aware (#37, same fix as desktop/main.py) — __file__-based relative
# resolution isn't reliably correct for PyInstaller-frozen modules.
if getattr(sys, "frozen", False):
    _IMAGES_DIR = Path(sys._MEIPASS) / "images"
else:
    _IMAGES_DIR = Path(__file__).resolve().parents[2] / "images"

from PySide6.QtWidgets import QPushButton

from app.atlas_application import AtlasApplication
from desktop.pages.home_page import HomePage
from desktop.theme.colors import NAVY, SLATE, STEEL, SILVER, LIGHT, PRIMARY
from desktop.updater import UpdateChecker, APP_VERSION

# Other pages are imported inside their lazy factories (_build_pages) — the
# import itself is part of the deferred cost (trends_page alone pulls in
# matplotlib), so it's paid on first visit, not at startup.


# (glyph name, label) — glyphs are painted line icons (desktop/widgets/
# nav_icons.py). The old emoji rendered full-color via Segoe UI Emoji,
# which fought the navy rail; the redesign uses one monochrome family.
_NAV_ITEMS = [
    ("home",   "Home"),
    ("eye",    "Visibility"),
    ("target", "Targeted Review"),
    ("trend",  "Trends"),
    ("bulb",   "Intelligence"),
    ("search", "Investigate"),
    ("book",   "Knowledge"),
    ("tag",    "Price Comparison"),
    ("gear",   "Settings"),
]

# Name -> row lookup, not hardcoded numbers — reordering _NAV_ITEMS has
# silently broken hardcoded row references twice before (Price Comparison's
# index shifted when Targeted Review was inserted, then again here when the
# whole nav was reordered to match the workflow sequence). Every row check
# in this file should go through this instead.
_NAV_ROW = {label: i for i, (_, label) in enumerate(_NAV_ITEMS)}


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
        knowledge_action.triggered.connect(
            lambda: self.nav.setCurrentRow(_NAV_ROW["Knowledge"]))
        logs_action = tools_menu.addAction("Open Logs Folder")
        logs_action.setToolTip(
            "Diagnostic logs from Visibility Collection runs (#75) — useful if a run "
            "silently stalls and you want to see exactly where it stopped."
        )
        logs_action.triggered.connect(self._open_logs_folder)

        help_menu = menu.addMenu("Help")
        guide_action = help_menu.addAction("Usage Guide")
        guide_action.triggered.connect(self._show_usage_guide)
        methodology_action = help_menu.addAction("Methodology")
        methodology_action.triggered.connect(self._show_methodology)
        update_action = help_menu.addAction("Check for Updates")
        update_action.triggered.connect(self._check_for_updates_manual)
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

    @staticmethod
    def _paint_wordmark(mark_only: bool = False) -> QPixmap:
        """The rail's brand row: a small primary-blue square mark plus a
        letter-spaced ATLAS wordmark in the heading face, painted on a
        transparent ground so it sits directly on the navy."""
        from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
        from desktop.theme.colors import LIGHT, PRIMARY
        w, h = (44, 46) if mark_only else (194, 46)
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        x = (w - 24) // 2 if mark_only else 14
        p.setBrush(QColor(PRIMARY))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(x, 11, 24, 24, 5, 5)
        f = QFont("Barlow Condensed", 12, QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(x, 11, 24, 24, Qt.AlignCenter, "A")
        if not mark_only:
            f2 = QFont("Barlow Condensed", 15, QFont.DemiBold)
            f2.setLetterSpacing(QFont.AbsoluteSpacing, 3)
            p.setFont(f2)
            p.setPen(QColor(LIGHT))
            p.drawText(x + 34, 0, w - x - 34, h,
                       Qt.AlignVCenter | Qt.AlignLeft, "ATLAS")
        p.end()
        return pm

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

        # Full sidebar brand mark (expanded mode) — painted, not the old
        # atlas_sidebar.png: that image bakes in a pure-black background,
        # which read as a heavy black box against the redesign's #16324D
        # navy rail (2026-07 spec: slim square mark + wordmark).
        self._logo_full = QLabel()
        self._logo_full.setStyleSheet("border: none; background: transparent;")
        self._logo_full.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._logo_full.setPixmap(self._paint_wordmark())
        self._nav_header_height = 62
        self._nav_header.setFixedHeight(self._nav_header_height)

        # Small icon logo (collapsed mode) — the same painted mark, sans text.
        self._logo_icon = QLabel()
        self._logo_icon.setAlignment(Qt.AlignCenter)
        self._logo_icon.setStyleSheet("border: none; background: transparent;")
        self._logo_icon.setPixmap(self._paint_wordmark(mark_only=True))
        self._logo_icon.setVisible(False)

        h_lay.addWidget(self._logo_full)
        h_lay.addWidget(self._logo_icon)
        self._nav_header.setLayout(h_lay)

        # ── Navigation list ───────────────────────────────────────────────────
        self.nav = QListWidget()
        self.nav.setObjectName("AtlasNav")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        from desktop.widgets.nav_icons import nav_icon
        for glyph, label in _NAV_ITEMS:
            self.nav.addItem(QListWidgetItem(nav_icon(glyph), f"  {label}"))
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
            # This middle segment is a PLAIN string — a single "}" here, not
            # the f-string-escaped "}}" (that doubled brace made the whole
            # sheet unparseable, so this button silently fell back to the
            # global style — caught by the user's v1.0 test pass, item 1.1).
            "font-size: 12px; font-weight: 600; padding: 4px 16px; text-align: left; }"
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
            for i in range(len(_NAV_ITEMS)):   # icon-only rows when collapsed
                item = self.nav.item(i)
                item.setText("")
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
                "font-size: 16px; font-weight: bold; padding: 4px 0px; text-align: center; }"
                f"QPushButton:hover {{ color: white; background: #2D3F55; }}"
            )
        else:
            for i, (_, label) in enumerate(_NAV_ITEMS):
                item = self.nav.item(i)
                item.setText(f"  {label}")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.nav.setIconSize(QSize(20, 20))
            self.nav.setStyleSheet("")
            self._nav_toggle_btn.setText("‹‹  Collapse")
            self._nav_toggle_btn.setToolTip("Collapse navigation")
            self._nav_toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {SLATE}; color: {SILVER}; "
                f"border: none; border-top: 1px solid {STEEL}; "
                "font-size: 12px; font-weight: 600; padding: 4px 16px; text-align: left; }"
                f"QPushButton:hover {{ color: white; background: #2D3F55; }}"
            )

    def changeEvent(self, event):
        """#34: minimizing mid-collection shows a compact always-on-top
        progress chip, so a long run stays observable while the user works
        in other apps. Normal minimize behavior otherwise — the chip only
        appears when the Visibility page has an actively running worker
        (a never-built lazy page can't have one)."""
        super().changeEvent(event)
        if event.type() != QEvent.WindowStateChange:
            return
        vis = getattr(self, "_built_pages", {}).get("Visibility")
        if vis is None:
            return
        if self.isMinimized():
            if getattr(vis, "has_active_run", False):
                vis.show_mini_progress(on_restore=self._restore_from_mini)
        else:
            vis.hide_mini_progress()

    def _restore_from_mini(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _build_pages(self) -> QWidget:
        wrapper = QWidget()
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.pages = QTabWidget()
        self.pages.tabBar().hide()

        # Lazy page construction (pre-v1.0 startup polish): every page used
        # to be built synchronously here before the window could appear, and
        # the heavy ones (Visibility, Trends) each scan the full response
        # history at construction — startup cost grew with every collection
        # ever run. Now only Home is built up front; each other page is
        # built on its first visit (_ensure_page), behind a brief wait
        # cursor. Side benefit: a page built later sees data added after
        # launch (e.g. brands Discovered mid-session) without a restart.
        def _lazy(module_name, class_name):
            def factory():
                import importlib
                module = importlib.import_module(f"desktop.pages.{module_name}")
                return getattr(module, class_name)(self.app)
            return factory

        self._page_factories = {
            "Home":             lambda: HomePage(self.app),
            "Visibility":       _lazy("visibility_page", "VisibilityPage"),
            "Targeted Review":  _lazy("targeted_review_page", "TargetedReviewPage"),
            "Trends":           _lazy("trends_page", "TrendsPage"),
            "Intelligence":     _lazy("intelligence_page", "IntelligencePage"),
            "Investigate":      _lazy("investigation_page", "InvestigationPage"),
            "Knowledge":        _lazy("knowledge_page", "KnowledgePage"),
            "Price Comparison": _lazy("price_comparison_page", "PriceComparisonPage"),
            "Settings":         _lazy("settings_page", "SettingsPage"),
        }
        self._built_pages: dict[str, QWidget] = {}

        # One empty container per nav row (order matches _NAV_ITEMS); the
        # real page is inserted into its container on first visit.
        for _, label in _NAV_ITEMS:
            container = QWidget()
            c_lay = QVBoxLayout(container)
            c_lay.setContentsMargins(0, 0, 0, 0)
            c_lay.setSpacing(0)
            self.pages.addTab(container, label)

        self.home_page = self._ensure_page("Home")

        lay.addWidget(self.pages)
        wrapper.setLayout(lay)
        return wrapper

    def _ensure_page(self, label: str) -> QWidget:
        """Build the page on first visit; return the existing one after."""
        if label in self._built_pages:
            return self._built_pages[label]
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            page = self._page_factories[label]()
            self._built_pages[label] = page
            container = self.pages.widget(_NAV_ROW[label])
            container.layout().addWidget(page)
        finally:
            QGuiApplication.restoreOverrideCursor()
        return page

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_nav_changed(self, row: int):
        label = _NAV_ITEMS[row][1]
        page = self._ensure_page(label)   # lazily built on first visit
        self.pages.setCurrentIndex(row)
        if label == "Home":
            page.refresh()
        elif label == "Visibility":
            page.refresh_provider_status()
        elif label == "Targeted Review":
            # Pick up brands added via Knowledge's Discover button since last visit.
            page.refresh_brand_list()
        elif label == "Price Comparison":
            page.refresh()

    # ── Update checker ────────────────────────────────────────────────────────

    def _start_update_check(self):
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str, url: str, notes: str):
        bar = self.statusBar()
        bar.clearMessage()

        msg = QLabel(f"  Update available:  Atlas AI v{version}  —  {notes[:80] + '…' if len(notes) > 80 else notes}  ")
        msg.setStyleSheet("color: #3E7BC2; font-weight: bold;")

        if url:
            btn = QPushButton(f"Download v{version}")
            btn.setStyleSheet(
                "QPushButton { background: #3E7BC2; color: white; border: none; "
                "border-radius: 4px; padding: 3px 10px; font-size: 11px; }"
                "QPushButton:hover { background: #295A94; }"
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

    # ── Manual "Check for Updates" (Help menu) ──────────────────────────────
    # Unlike the silent-unless-found automatic startup check, a user-triggered
    # check must give visible feedback in all three outcomes — found, already
    # current, or the check itself failed — not just the update-found case.

    def _check_for_updates_manual(self):
        self.statusBar().showMessage("Checking for updates…")
        self._manual_update_checker = UpdateChecker()
        self._manual_update_checker.update_available.connect(self._on_manual_update_available)
        self._manual_update_checker.up_to_date.connect(self._on_manual_up_to_date)
        self._manual_update_checker.check_failed.connect(self._on_manual_check_failed)
        self._manual_update_checker.start()

    def _on_manual_update_available(self, version: str, url: str, notes: str):
        self.statusBar().clearMessage()
        reply = QMessageBox.information(
            self, "Update Available",
            f"Atlas AI v{version} is available.\n\n{notes}",
            QMessageBox.Open | QMessageBox.Ok, QMessageBox.Ok,
        )
        if reply == QMessageBox.Open and url:
            self._open_download(url)

    def _on_manual_up_to_date(self, version: str):
        self.statusBar().clearMessage()
        QMessageBox.information(
            self, "Up to Date",
            f"You're running the latest version — Atlas AI v{version}.",
        )

    def _on_manual_check_failed(self, error: str):
        self.statusBar().clearMessage()
        QMessageBox.warning(
            self, "Update Check Failed",
            f"Couldn't check for updates:\n\n{error}\n\nTry again later.",
        )

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
        name_lbl.setStyleSheet("font-size: 26px; font-weight: 700; color: #2B323A; letter-spacing: 1px;")
        name_lbl.setAlignment(Qt.AlignCenter)

        ver_badge = QLabel(f"v{APP_VERSION}")
        ver_badge.setAlignment(Qt.AlignCenter)
        ver_badge.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #3E7BC2; "
            "background: #EFF6FF; border: 1px solid #BFDBFE; "
            "border-radius: 10px; padding: 2px 10px;"
        )
        ver_badge.setFixedHeight(22)

        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(ver_badge)

        tagline = QLabel("AI Intelligence Platform")
        tagline.setStyleSheet("font-size: 14px; color: #69727E; font-weight: 500;")
        tagline.setAlignment(Qt.AlignCenter)

        def _sep():
            s = QLabel()
            s.setFixedHeight(1)
            s.setStyleSheet("background: #E3E7ED; margin: 0px;")
            return s

        # Description — no hard-coded line breaks; word wrap alone decides
        # where lines break based on the dialog's actual width, so it wraps
        # evenly instead of double-wrapping mid-sentence.
        desc = QLabel(
            "Atlas tracks brand visibility across AI providers, measures your "
            "real footprint on YouTube, Reddit, editorial coverage, retail "
            "listings, and Google AI Overviews, and synthesizes it all into a "
            "strategic intelligence briefing — so you always know how your "
            "brand appears, and why, everywhere AI is shaping buying decisions."
        )
        desc.setStyleSheet("font-size: 13px; color: #2B323A; line-height: 1.5;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        # Copyright line — both dweeb.co and the (c) are real links, but
        # styled identically to the surrounding plain text (same gray, no
        # underline) so neither visually announces itself as clickable.
        # (c) opens the hidden easter egg; dweeb.co opens the real site.
        copy_lbl = QLabel(
            '<a href="egg" style="color:#8C96A2; text-decoration:none;">©</a>'
            ' 2026 '
            '<a href="https://dweeb.co" style="color:#8C96A2; text-decoration:none;">dweeb.co</a>'
        )
        copy_lbl.setStyleSheet("font-size: 12px; color: #8C96A2;")
        copy_lbl.linkActivated.connect(self._on_copyright_link)
        copy_lbl.setAlignment(Qt.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(110)
        close_btn.setStyleSheet(
            "QPushButton { background: #2B323A; color: white; border: none; "
            "border-radius: 5px; padding: 6px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #2B323A; }"
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

    def _on_copyright_link(self, href: str):
        if href == "egg":
            self._show_easter_egg()
        else:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(href))

    def _show_easter_egg(self):
        """Hidden behind the © in About Atlas — not linked from anywhere
        else, not mentioned anywhere in the UI. Find it or don't."""
        from desktop.widgets.blackout_brigade import BlackoutBrigadeDialog
        BlackoutBrigadeDialog(self, self.app.config_service).exec()

    def _show_methodology(self):
        """#102: one place stating exactly how every number in Atlas is
        computed — matching rules, sampling scope, estimates policy, and
        known limitations. A factual tool owes its users its methodology,
        especially once the database is shared with coworkers who weren't
        in the room when these choices were made."""
        sections = [
            ("Brand Mention Detection",
             "A response mentions a brand when any of the brand's detection terms "
             "(name + aliases from Knowledge) appears as a whole word — case-"
             "insensitive; plurals and possessives count (“Hondas”, “Honda's”) but "
             "substrings do not (“category” is not CAT — corrected July 2026 after "
             "substring matching was found inflating short-named brands). Each brand "
             "counts at most once per response, no matter how often it appears."),
            ("Visibility Score & Mention Rank",
             "Visibility Score = responses mentioning the target brand ÷ ALL stored "
             "responses × 100, over the full collection history. Mention Rank ranks "
             "every tracked brand by mention count; the “of N” denominator is the "
             "full tracked-brand list, including brands with zero mentions. Every "
             "KPI tile shows its sample size (n=) and as-of date; under 30 responses "
             "it is flagged as a small sample."),
            ("Sentiment & Recommendations",
             "Rule-based, sentence-level detection — deterministic, never AI-judged. "
             "Negative context uses cues like “lacks”/“unlike X” clamped at clause "
             "boundaries; recommendations require endorsement language "
             "(“I'd recommend…”), and a brand flagged negative in a response is "
             "never credited as recommended there. Known limits: double negatives "
             "(“not a bad choice”) and sentences naming 3+ brands can misattribute. "
             "Percentages are of each brand's OWN mentions, not of all responses."),
            ("Intelligence Engine",
             "DB Mode reuses stored Visibility responses (3 AI calls: portfolio "
             "inference, opportunities, executive briefing); Live Mode first "
             "collects 14 fresh prompts when stored data is insufficient. The "
             "briefing's cited counts come from the FULL stored history (scope-"
             "labeled in the data given to the model); the synthesis text reads a "
             "capped ~25-per-topic sample for token budget. After generation, every "
             "“X of Y” claim is mechanically checked against the exact data "
             "supplied — the badge on the briefing shows the result; unverified "
             "claims are flagged for review, never silently edited."),
            ("Targeted Review",
             "Platform numbers are COUNTED from real results, never platform "
             "estimates: YouTube metrics count title-filtered videos (brand word + "
             "generator term) within the top-100 search results — YouTube's own "
             "“total results” figure is an approximation capped at 1,000,000 and is "
             "not used. Reddit counts stop at the API's 100-result cap (shown as "
             "100+). Editorial coverage runs one site-restricted Google query per "
             "authority site. Retail numbers come from each listing's own structured "
             "data on user-saved product URLs. A gap requires a 1.5× lead (counts) "
             "or a 0.2-star spread / sub-4.0 rating; the Why/Tactics text is rule-"
             "based so the explanation layer cannot hallucinate."),
            ("Influencer Tracking",
             "Creator numbers come straight from each platform's official API for "
             "the specific channel/user you added: YouTube upload cadence and "
             "per-video view/like/comment counts from the channel's own uploads "
             "playlist; Reddit post cadence and scores from the user's public "
             "post history. Averages are over the lookback window (30 days) and "
             "only over posts actually returned — never extrapolated. No AI is "
             "involved anywhere in these numbers."),
            ("Price Comparison Matching",
             "The AI's ONLY role is nominating each brand's closest comparable "
             "model (matched on wattage, fuel type, start type, generator type) — "
             "a name, not a number. Every displayed price comes from a real "
             "source (manufacturer Shopify data, Google Shopping listings, or a "
             "URL you pasted); every spec comes from the manufacturer's own spec "
             "page; ratings come from the listing's structured data. Anything "
             "that cannot be confirmed displays as “—”, never estimated. The "
             "Data Status tab records whether each model was user-entered, "
             "AI-matched, or a top search result."),
            ("AI-Cited Sources",
             "Source URLs reported by the AI provider itself with each answer "
             "(currently Perplexity). Aggregated by domain on the Visibility → "
             "Channels tab — a direct measurement of which sites feed AI answers, "
             "not an inference."),
            ("Trends & Event Markers",
             "Each point is one collection run, scored independently. Dotted "
             "vertical markers flag moments the measurement itself changed — "
             "brands/aliases/prompts edited, or a provider's model version changing "
             "(detected automatically from run history) — so instrument changes "
             "aren't read as market changes. Comparable trends require a consistent "
             "panel: save one with the Saved Panel button on the Visibility page "
             "and re-run it on a regular cadence."),
            ("Data Safety",
             "A rotating backup of the database (newest 5) is taken at each app "
             "launch via SQLite's online backup API, stored in the backups folder "
             "next to the database. The Health Check card verifies database "
             "integrity (PRAGMA integrity_check) and backup freshness."),
        ]
        self._show_reference_dialog(
            "Methodology", "How every number in Atlas is computed.", sections)

    def _show_reference_dialog(self, title: str, subtitle: str, sections):
        """Shared scaffold for Usage Guide / Methodology style dialogs."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Atlas — {title}")
        dlg.setFixedSize(560, 620)

        outer = QVBoxLayout()
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background: #2B323A;")
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(32, 22, 32, 18)
        h_lay.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("font-size: 12px; color: #8C96A2;")
        h_lay.addWidget(title_lbl)
        h_lay.addWidget(sub_lbl)
        header.setLayout(h_lay)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: white;")

        body = QWidget()
        body.setStyleSheet("background: white;")
        b_lay = QVBoxLayout()
        b_lay.setContentsMargins(32, 20, 32, 20)
        b_lay.setSpacing(16)
        for sec_title, sec_text in sections:
            w = QWidget()
            lay = QVBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(3)
            t = QLabel(sec_title)
            t.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #2B323A;")
            d = QLabel(sec_text)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 12px; color: #69727E;")
            lay.addWidget(t)
            lay.addWidget(d)
            w.setLayout(lay)
            b_lay.addWidget(w)
        b_lay.addStretch()
        body.setLayout(b_lay)
        scroll.setWidget(body)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet(
            "QPushButton { background: #3E7BC2; color: white; border: none; "
            "font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #295A94; }"
        )
        close_btn.clicked.connect(dlg.accept)

        outer.addWidget(header)
        outer.addWidget(scroll, 1)
        outer.addWidget(close_btn)
        dlg.setLayout(outer)
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
        header.setStyleSheet("background: #2B323A;")
        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(32, 22, 32, 18)
        h_lay.setSpacing(2)
        title_lbl = QLabel("Usage Guide")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        sub_lbl = QLabel("What each page does and how they fit together.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #8C96A2;")
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
            t.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #2B323A;")
            d = QLabel(body_text)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 12px; color: #69727E; line-height: 1.4;")
            lay.addWidget(t)
            lay.addWidget(d)
            w.setLayout(lay)
            return w

        # Rendered as an HTML list — a numbered sequence buried inside one
        # paragraph was unreadable (user v1.0 test, item 11.1).
        b_lay.addWidget(_section(
            "Recommended Workflow",
            "<ol style='margin:0 0 0 18px; padding:0;'>"
            "<li><b>Settings</b> — set your Target Brand and add AI provider API keys.</li>"
            "<li><b>Knowledge</b> — confirm the brands, features, and prompt sets Atlas tracks.</li>"
            "<li><b>Visibility</b> — run a collection to gather AI responses (the raw data "
            "every other page builds on). Save a panel and re-run the same panel on a "
            "regular cadence.</li>"
            "<li><b>Targeted Review</b> — optional but recommended: collect real platform "
            "numbers (YouTube, Reddit, editorial, retail, AI Overviews) that feed the "
            "Intelligence briefing as ground truth.</li>"
            "<li><b>Trends</b> — review how visibility changes across runs (a view — "
            "nothing to run).</li>"
            "<li><b>Intelligence</b> — run last: it synthesizes everything collected "
            "above.</li>"
            "</ol>"
            "<p style='margin:6px 0 0 0;'><b>Investigate</b> and <b>Price Comparison</b> "
            "are independent — use them any time.</p>"
        ))

        # Same order as the left navigation.
        pages = [
            ("Home",
             "Dashboard snapshot — mention rate, responses stored, per-source Data "
             "Health freshness, and a Getting Started checklist that disappears once "
             "the required setup steps are complete."),
            ("Visibility",
             "The core data collection engine. Select prompt families and AI providers, "
             "then Run to query every selected provider with every selected prompt and "
             "store the responses. Use Saved Panel to pin a fixed prompt+provider "
             "selection so repeated runs stay comparable. Run this regularly — Trends "
             "and Intelligence both depend on this data existing."),
            ("Targeted Review",
             "Real platform numbers per brand — YouTube content volume and channel "
             "stats, Reddit conversation share, editorial coverage, Google AI Overview "
             "presence, Best Buy and retailer listings — with rule-based gap analysis "
             "(Gap → Why It Matters → Tactics). Find Socials discovers each brand's "
             "official channels from its website. The Influencers tab tracks specific "
             "named YouTube channels or Reddit users over time (posting cadence and "
             "engagement). Everything collected here feeds the Intelligence briefing "
             "as measured ground truth."),
            ("Trends",
             "Charts how visibility score, brand standing, provider performance, feature "
             "associations, and first-mention position change across multiple Visibility "
             "runs. Time-series charts need at least 2 days of collection history to "
             "render. Nothing to run here — just Refresh after a new collection."),
            ("Intelligence",
             "Run this last — synthesizes stored Visibility responses AND measured "
             "Targeted Review data into an executive briefing, consumer personas, "
             "buying-journey insights, and strategic opportunities. Every cited count "
             "in the briefing is mechanically verified after generation (see the badge). "
             "Export as PDF or Word."),
            ("Investigate",
             "Ask a natural-language business question (e.g. \"Why is Honda winning on "
             "Amazon reviews?\"). Atlas dispatches specialized AI agents to research it "
             "and returns a synthesized answer with ranked evidence and recommendations. "
             "Independent of the workflow — use any time."),
            ("Knowledge",
             "Manage the reference data Atlas uses for detection: Brands, Features, "
             "Personas, Scenarios, Stages, Prompt Families, and Prompts. \"Discover "
             "Brands\" queries your AI providers for competitor brands not yet tracked; "
             "newly added brands appear in Targeted Review automatically."),
            ("Price Comparison",
             "Give Atlas a brand + product model and it finds each competitor's closest "
             "comparable product — matched on wattage, fuel type, start type, and "
             "generator type — then shows an Amazon-style comparison table of confirmed "
             "prices, ratings, and specs. The AI only nominates candidate models; every "
             "displayed number is independently confirmed from manufacturer/retailer "
             "pages, or shown as \"—\"."),
            ("Settings",
             "Configure your Target Brand, active AI provider, per-provider API keys "
             "(use Test to verify a key works), and Platform Research credentials for "
             "Targeted Review. Run Health Check to verify the database and "
             "configuration are sound."),
        ]
        for name, desc in pages:
            b_lay.addWidget(_section(name, desc))

        b_lay.addStretch()
        body.setLayout(b_lay)
        scroll.setWidget(body)

        # ── Footer ─────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: #FAFAFA; border-top: 1px solid #E3E7ED;")
        f_lay = QHBoxLayout()
        f_lay.setContentsMargins(32, 12, 32, 12)
        f_lay.setAlignment(Qt.AlignCenter)
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(110)
        close_btn.setStyleSheet(
            "QPushButton { background: #2B323A; color: white; border: none; "
            "border-radius: 5px; padding: 6px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #2B323A; }"
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

    def _open_logs_folder(self):
        import os
        from backend.services.paths import get_logs_dir
        os.startfile(get_logs_dir())
