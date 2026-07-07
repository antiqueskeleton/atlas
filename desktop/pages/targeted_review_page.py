"""
Targeted Review page (#25): per-platform competitive investigation that
explains WHY channel gaps exist and HOW to close them — with real platform
numbers (YouTube video volume, Reddit conversation share, retailer review
depth), not inferences from AI response text like the rest of Atlas.

Every finding follows the feature's defining pattern:
Gap → Why It Matters for AI Visibility → Specific Tactics to Close It.
"""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.knowledge.knowledge_repository import KnowledgeRepository
from backend.targeted_review.targeted_review_service import PLATFORMS, TargetedReviewService
from backend.visibility.brand_matcher import resolve_target_brand
from desktop.widgets.info_icon import info_icon

_COLLECT_BTN_STYLE = (
    "QPushButton { background: #0B84FF; color: white; border: none; "
    "border-radius: 5px; padding: 6px 14px; font-size: 12px; font-weight: bold; }"
    "QPushButton:hover { background: #0056CC; }"
    "QPushButton:disabled { background: #9CA3AF; }"
)

_GAP_BADGE = (
    "background: #DC2626; color: white; border-radius: 4px; "
    "font-size: 10px; font-weight: bold; padding: 2px 8px;"
)
_STRENGTH_BADGE = (
    "background: #16A34A; color: white; border-radius: 4px; "
    "font-size: 10px; font-weight: bold; padding: 2px 8px;"
)

# Table columns per platform: (header, metric key or callable, tooltip)
_TABLE_COLUMNS = {
    "youtube": [
        ("Relevant (top-100)", "relevant_results_top100",
         "How many of the top-100 YouTube search results for \"[brand] portable "
         "generator\" are actually about this brand's generators — each title "
         "must mention the brand AND a generator-market term. Counted from real "
         "results, never YouTube's inflated totals estimate."),
        ("Fresh (12 mo)", "recent_relevant_365d",
         "Relevant videos published in the trailing year, same top-100 counted "
         "sample — content freshness."),
        ("Top-10 Views", "top_videos_total_views",
         "Combined view count of the brand's top-10 RELEVANT videos (filtered, "
         "so an ambiguous brand name's off-topic viral videos don't count)."),
        ("Ch. Subs", lambda m: (f"{m['channel_subscribers']:,}"
                                if m.get("channel_subscribers") is not None else None),
         "Official channel subscribers — needs the brand's channel URL, "
         "discovered via the Find Socials button (scrapes each brand's "
         "website for its social links). Costs ~3 quota units per brand."),
    ],
    "reddit": [
        ("Posts (1 yr)", "posts_last_year",
         "Posts matching \"[brand] generator\" in the last year. 100 means "
         "100+ — Reddit caps one search request at 100 results."),
        ("Upvotes", "total_score", "Combined upvote score across those posts."),
        ("Comments", "total_comments", "Combined comment count across those posts."),
        ("Top Subreddits",
         lambda m: ", ".join(f"r/{s}" for s, _ in (m.get("top_subreddits") or [])[:3]),
         "Where this brand's conversation actually happens."),
    ],
    "editorial": [
        ("Sites Covering", lambda m: (
            f"{m['sites_with_coverage']} of {m.get('sites_checked', 0)}"
            if m.get("sites_with_coverage") is not None else None),
         "How many of the tracked authority review sites (Consumer Reports, "
         "Wirecutter, CNET, Popular Mechanics, Bob Vila, Forbes) have any "
         "coverage of this brand."),
        ("Articles (est.)", "total_results",
         "Google's estimated article count across all tracked editorial "
         "sites — directional, not exact."),
        ("Strongest Site", lambda m: m.get("strongest_site") or None,
         "The tracked editorial site with the most coverage of this brand."),
    ],
    "retail": [
        ("Listings", lambda m: m.get("listings_ok"),
         "Saved product listings that could be read this collection."),
        ("Total Reviews", "total_reviews",
         "Combined review count across the brand's saved listings."),
        ("Avg Rating", lambda m: (f"{m['avg_rating']:.2f} ★"
                                  if m.get("avg_rating") is not None else None),
         "Average star rating, weighted by each listing's review count."),
    ],
}



# Drill-down detail specs (#103): the collection already stores per-brand
# detail (top videos, top posts, per-site coverage, per-listing results)
# that the summary table can't show — double-clicking a brand row opens it.
# platform -> list of (metrics_key, section title, columns) sections shown
# in the double-click drill-down dialog, in order.
_DETAIL_SPECS = {
    "youtube": [("top_videos", "Top relevant videos", [
        ("Title", lambda v: v.get("title", "")),
        ("Channel", lambda v: v.get("channel", "")),
        ("Views", lambda v: f"{v.get('views', 0):,}"),
        ("Comments", lambda v: f"{v.get('comments', 0):,}"),
        ("Published", lambda v: v.get("published", "")),
    ]), ("top_comments", "Owner voice — top comments on those videos", [
        ("Comment", lambda v: v.get("text", "")),
        ("Video", lambda v: v.get("video", "")),
        ("Likes", lambda v: f"{v.get('likes', 0):,}"),
        ("Signal", lambda v: v.get("signal", "")),
    ])],
    "reddit": [("top_posts", "Top posts (last year)", [
        ("Title", lambda v: v.get("title", "")),
        ("Subreddit", lambda v: f"r/{v.get('subreddit', '')}"),
        ("Score", lambda v: f"{v.get('score', 0):,}"),
        ("Comments", lambda v: f"{v.get('comments', 0):,}"),
        ("Date", lambda v: v.get("created", "")),
    ])],
    "editorial": [("per_site", "Coverage by authority site", [
        ("Site", lambda v: v.get("site", "")),
        ("Articles (est.)", lambda v: f"{v.get('results', 0):,}"),
        ("Top article", lambda v: v.get("top_title", "")),
        ("URL", lambda v: v.get("top_url", "")),
    ])],
    "retail": [("listings", "Saved listings", [
        ("Retailer", lambda v: v.get("retailer", "")),
        ("Product", lambda v: v.get("title", "")),
        ("Rating", lambda v: "" if v.get("rating") is None else f"{v['rating']} ★"),
        ("Reviews", lambda v: "" if v.get("review_count") is None else f"{v['review_count']:,}"),
        ("Status", lambda v: v.get("error") or "OK"),
    ])],
}


class _CollectWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(list)
    fail = Signal(str)

    def __init__(self, service, platform_key, brands):
        super().__init__()
        self._service = service
        self._platform_key = platform_key
        self._brands = brands

    def run(self):
        try:
            findings = self._service.collect_platform(
                self._platform_key, self._brands,
                progress_cb=lambda done, total, label: self.progress.emit(done, total, label),
            )
            self.done.emit(findings)
        except Exception as exc:
            self.fail.emit(str(exc))


class TargetedReviewPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.service = TargetedReviewService(
            app.config_service, target_brand=app.get_target_brand()
        )
        self._workers: list[_CollectWorker] = []
        self._brand_checks: dict[str, QCheckBox] = {}
        # per-platform widget registries, filled by _build_platform_tab
        self._tables: dict[str, QTableWidget] = {}
        self._findings_layouts: dict[str, QVBoxLayout] = {}
        self._collect_btns: dict[str, QPushButton] = {}
        self._status_lbls: dict[str, QLabel] = {}

        self._build_ui()
        for key in PLATFORMS:
            self._refresh_platform(key)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(8)
        root.setContentsMargins(24, 14, 24, 12)

        title = QLabel("Targeted Review")
        title.setStyleSheet("font-size:24px; font-weight:bold;")

        subtitle = QLabel(
            "Real platform numbers — YouTube content volume, Reddit conversation "
            "share, retailer review depth — that explain WHY AI models see some "
            "brands more than others, and what would close each gap."
        )
        subtitle.setStyleSheet("font-size:13px; color:#6B7280;")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self._build_brand_panel())

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; padding-top: 8px; }
            QTabBar::tab {
                padding: 7px 20px; font-size: 12px; font-weight: 500;
                border: none; border-bottom: 2px solid transparent;
                background: transparent; color: #6B7280; margin-right: 4px;
            }
            QTabBar::tab:hover { color: #111827; }
            QTabBar::tab:selected { color: #0B84FF; border-bottom: 2px solid #0B84FF; }
        """)
        self.tabs.addTab(self._build_platform_tab("youtube"), "YouTube")
        self.tabs.addTab(self._build_platform_tab("reddit"), "Reddit")
        self.tabs.addTab(self._build_platform_tab("editorial"), "Editorial")
        self.tabs.addTab(self._build_platform_tab("retail"), "Retail Listings")
        root.addWidget(self.tabs, 1)

        self.setLayout(root)

    def _build_brand_panel(self) -> QWidget:
        """Checkbox grid of tracked brands — which brands each collection
        run researches. Target brand is pre-checked; competitors are opt-in
        because every checked brand costs real API quota per platform."""
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(8, 6, 8, 6)

        target = self.app.get_target_brand()
        brands = [row[1] for row in KnowledgeRepository().list_brands() if row[4]]
        resolved_target = resolve_target_brand(target, brands)

        for i, name in enumerate(brands):
            cb = QCheckBox(name)
            cb.setStyleSheet("font-size: 12px;")
            if name == resolved_target:
                cb.setChecked(True)
                cb.setStyleSheet("font-size: 12px; font-weight: bold; color: #0B84FF;")
            self._brand_checks[name] = cb
            grid.addWidget(cb, i // 5, i % 5)

        inner = QWidget()
        inner.setLayout(grid)
        inner.setStyleSheet("background: white;")

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(96)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #D1D5DB; border-radius: 4px; background: white; }"
        )

        btn_top = QPushButton("Top AI-Mentioned")
        btn_none = QPushButton("None")
        for b in (btn_top, btn_none):
            b.setFixedWidth(120)
            b.setStyleSheet("font-size: 11px; padding: 3px 4px;")
        btn_top.clicked.connect(self._select_top_mentioned)
        btn_top.setToolTip(
            "Check the target brand plus the 5 competitors AI models mention "
            "most in your collected Visibility data — the brands most worth "
            "benchmarking against."
        )
        btn_none.clicked.connect(self._clear_brands)
        btn_none.setToolTip("Uncheck every brand except the target brand")

        btn_socials = QPushButton("Find Socials")
        btn_socials.setFixedWidth(120)
        btn_socials.setStyleSheet("font-size: 11px; padding: 3px 4px;")
        btn_socials.clicked.connect(self._discover_socials)
        btn_socials.setToolTip(
            "Scrape each checked brand's manufacturer website (from Knowledge) "
            "for its official social links — most importantly the YouTube "
            "channel, which unlocks cheap channel metrics (subscribers, upload "
            "cadence) on the next YouTube collection."
        )
        self._socials_btn = btn_socials

        ctrl = QVBoxLayout()
        ctrl.setSpacing(4)
        ctrl.setAlignment(Qt.AlignTop)
        ctrl.addWidget(btn_top)
        ctrl.addWidget(btn_none)
        ctrl.addWidget(btn_socials)
        ctrl.addStretch()

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(4)
        hdr = QLabel("Brands to research:")
        hdr.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151;")
        hdr_row.addWidget(hdr)
        hdr_row.addWidget(info_icon(
            "Each checked brand costs one set of platform requests per "
            "collection (YouTube: ~401 quota units of the 10,000/day free "
            "tier; Reddit: one search; Editorial: 6 of Google Custom "
            "Search's 100 free queries/day). Target + top 5 competitors is "
            "the intended working set."
        ))
        hdr_row.addStretch()

        panel_lay = QVBoxLayout()
        panel_lay.setSpacing(4)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.addLayout(hdr_row)
        body_row = QHBoxLayout()
        body_row.setSpacing(6)
        body_row.addWidget(scroll, 1)
        body_row.addLayout(ctrl)
        panel_lay.addLayout(body_row)

        panel = QWidget()
        panel.setLayout(panel_lay)
        return panel

    def _build_platform_tab(self, key: str) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(6)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        collect_btn = QPushButton(f"Collect {PLATFORMS[key].platform_name} Data")
        collect_btn.setStyleSheet(_COLLECT_BTN_STYLE)
        collect_btn.setCursor(Qt.PointingHandCursor)
        collect_btn.clicked.connect(lambda _=False, k=key: self._start_collect(k))
        self._collect_btns[key] = collect_btn

        status = QLabel("")
        status.setStyleSheet("color: #6B7280; font-size: 12px;")
        self._status_lbls[key] = status

        toolbar.addWidget(collect_btn)
        toolbar.addWidget(status, 1)
        lay.addLayout(toolbar)

        # ── Retail extra: saved product-URL manager ───────────────────────────
        if key == "retail":
            lay.addWidget(self._build_url_manager())

        # ── Metrics table + findings cards ────────────────────────────────────
        headers = ["Brand"] + [c[0] for c in _TABLE_COLUMNS[key]] + ["Status"]
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col, (_, _, tip) in enumerate(_TABLE_COLUMNS[key], start=1):
            table.horizontalHeaderItem(col).setToolTip(tip)
        table.cellDoubleClicked.connect(
            lambda row, _col, k=key: self._show_brand_detail(k, row))
        table.setToolTip("Double-click a brand row for its collected detail "
                         "(top videos / posts / sites / listings).")
        self._tables[key] = table

        table_frame = QFrame()
        table_frame.setObjectName("StatCard")
        tf_lay = QVBoxLayout(table_frame)
        tf_lay.setSpacing(6)
        tf_lbl = QLabel("Platform Numbers")
        tf_lbl.setObjectName("CardTitle")
        tf_lay.addWidget(tf_lbl)
        tf_lay.addWidget(table)

        findings_layout = QVBoxLayout()
        findings_layout.setSpacing(8)
        findings_layout.setContentsMargins(8, 8, 8, 8)
        findings_layout.addStretch()
        self._findings_layouts[key] = findings_layout

        findings_container = QWidget()
        findings_container.setLayout(findings_layout)
        findings_scroll = QScrollArea()
        findings_scroll.setWidget(findings_container)
        findings_scroll.setWidgetResizable(True)
        findings_scroll.setFrameShape(QFrame.NoFrame)
        # No horizontal scrolling — forces the cards' word-wrapped labels to
        # actually wrap to the pane width instead of stretching past it.
        findings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        findings_frame = QFrame()
        findings_frame.setObjectName("StatCard")
        ff_lay = QVBoxLayout(findings_frame)
        ff_lay.setSpacing(6)
        ff_lbl = QLabel("Gap Analysis — why it matters, what to do")
        ff_lbl.setObjectName("CardTitle")
        ff_lay.addWidget(ff_lbl)
        ff_lay.addWidget(findings_scroll)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(table_frame)
        split.addWidget(findings_frame)
        split.setSizes([520, 480])
        lay.addWidget(split, 1)
        return tab

    def _build_url_manager(self) -> QWidget:
        """Retail listings work from user-pasted product URLs, not search —
        Amazon's Product Advertising API needs an affiliate sales history the
        brand doesn't have, so curated URLs are the honest data path."""
        frame = QFrame()
        frame.setObjectName("StatCard")
        lay = QVBoxLayout(frame)
        lay.setSpacing(6)

        hdr = QLabel("Saved Product Listings")
        hdr.setObjectName("CardTitle")
        lay.addWidget(hdr)

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self._url_brand_combo = QComboBox()
        self._url_brand_combo.setFixedWidth(170)
        for row in KnowledgeRepository().list_brands():
            if row[4]:
                self._url_brand_combo.addItem(row[1])
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "Paste a product page URL — Amazon or Walmart "
            "(Lowe's and Home Depot block automated access)"
        )
        add_btn = QPushButton("Add")
        add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._add_url)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setFixedWidth(120)
        remove_btn.clicked.connect(self._remove_url)
        add_row.addWidget(self._url_brand_combo)
        add_row.addWidget(self._url_input, 1)
        add_row.addWidget(add_btn)
        add_row.addWidget(remove_btn)
        lay.addLayout(add_row)

        self._url_table = QTableWidget(0, 4)
        self._url_table.setHorizontalHeaderLabels(["Brand", "URL", "Added", "Last Fetch"])
        self._url_table.verticalHeader().setVisible(False)
        self._url_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._url_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._url_table.setColumnWidth(0, 130)
        self._url_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._url_table.setColumnWidth(2, 90)
        self._url_table.setColumnWidth(3, 260)
        self._url_table.horizontalHeaderItem(3).setToolTip(
            "Result of the most recent collection for this exact URL — hover a "
            "failed row for the full error. Known limits (confirmed in real "
            "testing): Lowe's AND Home Depot hard-block automated access "
            "(HTTP 403). Amazon and Walmart listings are the remaining sources."
        )
        self._url_table.setFixedHeight(120)
        lay.addWidget(self._url_table)

        self._reload_urls()
        return frame

    # ── Brand selection ───────────────────────────────────────────────────────

    def _checked_brands(self) -> list[str]:
        return [b for b, cb in self._brand_checks.items() if cb.isChecked()]

    def _clear_brands(self):
        target = resolve_target_brand(self.app.get_target_brand(),
                                      self._brand_checks.keys())
        for name, cb in self._brand_checks.items():
            cb.setChecked(name == target)

    def _select_top_mentioned(self):
        """Target + top-5 competitors by AI mention count, from the cached
        Visibility analytics summary. Imported lazily and computed on click
        (~2s first time on a large database) rather than at page build —
        pages are all constructed at app startup and this must not slow
        that down (#53)."""
        from backend.visibility.visibility_service import VisibilityService
        self.setCursor(Qt.WaitCursor)
        try:
            service = VisibilityService(self.app.provider_manager,
                                        target_brand=self.app.get_target_brand())
            counts = service.analytics_summary().get("brand_counts", {})
        finally:
            self.unsetCursor()

        target = resolve_target_brand(self.app.get_target_brand(),
                                      self._brand_checks.keys())
        top = [b for b, _ in sorted(counts.items(), key=lambda x: -x[1])
               if b != target][:5]
        for name, cb in self._brand_checks.items():
            cb.setChecked(name == target or name in top)

    # ── Social link discovery ─────────────────────────────────────────────────

    def _discover_socials(self):
        """Scrape checked brands' websites for social profiles (user request
        2026-07-06): the discovered YouTube channel powers the Ch. Subs
        column and channel gap metric on the next YouTube collection."""
        brands = self._checked_brands()
        if not brands:
            self._status_lbls["youtube"].setText("Check at least one brand first.")
            return
        websites = {row[1]: (row[2] or "")
                    for row in KnowledgeRepository().list_brands()}
        targets = [(b, websites.get(b, "")) for b in brands]

        self._socials_btn.setEnabled(False)
        status = self._status_lbls["youtube"]
        status.setStyleSheet("color: #0B84FF; font-size: 12px;")
        status.setText("Finding social links…")

        class _SocialWorker(QThread):
            progress = Signal(int, int, str)
            done = Signal(dict)

            def __init__(self, pairs):
                super().__init__()
                self._pairs = pairs

            def run(self):
                from backend.targeted_review.social_discovery import (
                    discover_socials_for_website)
                results = {}
                for i, (brand, website) in enumerate(self._pairs):
                    self.progress.emit(i, len(self._pairs), brand)
                    results[brand] = discover_socials_for_website(website)
                self.done.emit(results)

        worker = _SocialWorker(targets)
        worker.progress.connect(
            lambda done, total, label: status.setText(
                f"Finding social links {done + 1}/{total} — {label}"))
        worker.done.connect(self._on_socials_done)
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(worker)
        worker.start()

    def _on_socials_done(self, results: dict):
        self._socials_btn.setEnabled(True)
        with_yt, saved = 0, 0
        for brand, result in results.items():
            links = result.get("links", {})
            if links:
                self.service.repository.save_social_links(brand, links)
                saved += 1
                if links.get("youtube"):
                    with_yt += 1
        status = self._status_lbls["youtube"]
        status.setStyleSheet("color: #6B7280; font-size: 12px;")
        status.setText(
            f"Social links saved for {saved} of {len(results)} brand(s) — "
            f"{with_yt} with a YouTube channel. Channel metrics appear on the "
            f"next YouTube collection.")

    # ── Retail URL management ─────────────────────────────────────────────────

    def _reload_urls(self):
        rows = self.service.repository.list_product_urls()

        # Per-URL result of the latest collection — the brand-level Status
        # column alone couldn't tell the user WHICH listing failed or why.
        last_fetch: dict[str, str] = {}
        latest = self.service.repository.latest_findings(
            PLATFORMS["retail"].platform_name)
        for metrics in latest.values():
            for listing in metrics.get("listings") or []:
                error = listing.get("error", "")
                if error:
                    last_fetch[listing.get("url", "")] = error
                else:
                    reviews = listing.get("review_count")
                    rating = listing.get("rating")
                    parts = []
                    if reviews is not None:
                        parts.append(f"{reviews:,} reviews")
                    if rating is not None:
                        parts.append(f"{rating} ★")
                    last_fetch[listing.get("url", "")] = \
                        "OK · " + ", ".join(parts) if parts else "OK"

        self._url_table.setRowCount(len(rows))
        self._url_row_ids = []
        for r, (url_id, brand, url, added) in enumerate(rows):
            self._url_row_ids.append(url_id)
            self._url_table.setItem(r, 0, QTableWidgetItem(brand))
            self._url_table.setItem(r, 1, QTableWidgetItem(url))
            self._url_table.setItem(r, 2, QTableWidgetItem(added[:10]))
            result = last_fetch.get(url, "—")
            result_item = QTableWidgetItem(result)
            result_item.setToolTip(result)
            self._url_table.setItem(r, 3, result_item)

    def _add_url(self):
        url = self._url_input.text().strip()
        if not url.lower().startswith("http"):
            QMessageBox.information(self, "Invalid URL",
                                    "Paste a full product page URL (https://…).")
            return
        brand = self._url_brand_combo.currentText()
        if self.service.repository.add_product_url(brand, url):
            self._url_input.clear()
            self._reload_urls()
        else:
            QMessageBox.information(self, "Already Saved",
                                    "That URL is already in the list.")

    def _remove_url(self):
        row = self._url_table.currentRow()
        if row < 0 or row >= len(self._url_row_ids):
            return
        self.service.repository.delete_product_url(self._url_row_ids[row])
        self._reload_urls()

    # ── Collection ────────────────────────────────────────────────────────────

    def _start_collect(self, key: str):
        ready, reason = self.service.platform_ready(key)
        if not ready:
            self._status_lbls[key].setText(reason)
            self._status_lbls[key].setStyleSheet("color: #DC2626; font-size: 12px;")
            return

        brands = self._checked_brands()
        if key != "retail" and not brands:
            self._status_lbls[key].setText("Check at least one brand above.")
            self._status_lbls[key].setStyleSheet("color: #DC2626; font-size: 12px;")
            return

        self._collect_btns[key].setEnabled(False)
        self._status_lbls[key].setStyleSheet("color: #0B84FF; font-size: 12px;")
        self._status_lbls[key].setText("Collecting…")

        # Retail scope is the saved-URL list itself (already curated per
        # brand), not the checkbox selection — otherwise an unchecked
        # competitor's listings would silently drop out of the comparison.
        worker = _CollectWorker(self.service, key, [] if key == "retail" else brands)
        worker.progress.connect(
            lambda done, total, label, k=key: self._status_lbls[k].setText(
                f"Collecting {done + 1}/{total} — {label}"
            )
        )
        worker.done.connect(lambda findings, k=key: self._on_collect_done(k, findings))
        worker.fail.connect(lambda msg, k=key: self._on_collect_fail(k, msg))
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )
        self._workers.append(worker)
        worker.start()

    def _on_collect_done(self, key: str, findings: list):
        self._collect_btns[key].setEnabled(True)
        failed = [f for f in findings if f.get("error")]
        ok = len(findings) - len(failed)
        self._refresh_platform(key)
        if key == "retail":
            self._reload_urls()  # refresh the per-URL Last Fetch column

        if failed:
            # Show the first real error message in full — the table's Status
            # column truncates, which made a simple "API not enabled" failure
            # undiagnosable from the screen (found in real-credential testing).
            first_error = failed[0].get("error", "")
            self._status_lbls[key].setStyleSheet("color: #DC2626; font-size: 12px;")
            self._status_lbls[key].setText(
                f"Done — {ok} collected, {len(failed)} failed. First error: {first_error}"
            )
            self._status_lbls[key].setToolTip(first_error)
        else:
            self._status_lbls[key].setStyleSheet("color: #6B7280; font-size: 12px;")
            self._status_lbls[key].setText(f"Done — {ok} brand(s) collected")
            self._status_lbls[key].setToolTip("")

    def _on_collect_fail(self, key: str, message: str):
        self._collect_btns[key].setEnabled(True)
        self._status_lbls[key].setStyleSheet("color: #DC2626; font-size: 12px;")
        self._status_lbls[key].setText(f"Error: {message}")

    def _show_brand_detail(self, key: str, row: int):
        """#103: the per-brand detail behind the summary numbers."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        table = self._tables[key]
        item = table.item(row, 0)
        if item is None:
            return
        brand = item.text()
        metrics = self.service.repository.latest_findings(
            PLATFORMS[key].platform_name).get(brand)
        if not metrics:
            return
        sections = [
            (metrics.get(metrics_key) or [], title, columns)
            for metrics_key, title, columns in _DETAIL_SPECS[key]
        ]
        sections = [s for s in sections if s[0]]
        if not sections:
            QMessageBox.information(
                self, "No Detail",
                f"No stored detail for {brand} — collect again to capture it.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"{brand} — {sections[0][1]}")
        dlg.resize(900, 420 if len(sections) == 1 else 620)
        lay = QVBoxLayout(dlg)

        for rows, title, columns in sections:
            if len(sections) > 1:
                hdr = QLabel(title)
                hdr.setStyleSheet("font-weight: bold; font-size: 12px; color: #374151;")
                lay.addWidget(hdr)
            detail = QTableWidget(len(rows), len(columns))
            detail.setHorizontalHeaderLabels([c[0] for c in columns])
            detail.verticalHeader().setVisible(False)
            detail.setEditTriggers(QTableWidget.NoEditTriggers)
            detail.setAlternatingRowColors(True)
            detail.setWordWrap(True)
            detail.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            for r, entry in enumerate(rows):
                for c, (_, getter) in enumerate(columns):
                    try:
                        text = str(getter(entry))
                    except Exception:
                        text = ""
                    cell = QTableWidgetItem(text)
                    cell.setToolTip(text)
                    detail.setItem(r, c, cell)
            lay.addWidget(detail)
        dlg.exec()

    # ── Display ───────────────────────────────────────────────────────────────

    def _refresh_platform(self, key: str):
        platform_name = PLATFORMS[key].platform_name
        latest = self.service.repository.latest_findings(platform_name)

        # Target brand always listed first, then competitors by first metric.
        target = resolve_target_brand(self.app.get_target_brand(), latest.keys())
        first_metric = _TABLE_COLUMNS[key][0][1]

        def sort_key(brand):
            metrics = latest[brand]
            value = (first_metric(metrics) if callable(first_metric)
                     else metrics.get(first_metric)) or 0
            return (brand != target, -value if isinstance(value, (int, float)) else 0)

        table = self._tables[key]
        ordered = sorted(latest.keys(), key=sort_key)
        table.setRowCount(len(ordered))
        for r, brand in enumerate(ordered):
            metrics = latest[brand]
            name_item = QTableWidgetItem(brand)
            if brand == target:
                font = name_item.font()
                font.setBold(True)
                name_item.setFont(font)
            table.setItem(r, 0, name_item)
            for col, (_, key_or_fn, _) in enumerate(_TABLE_COLUMNS[key], start=1):
                value = key_or_fn(metrics) if callable(key_or_fn) else metrics.get(key_or_fn)
                display = "—" if value in (None, "") else (
                    f"{value:,}" if isinstance(value, int) else str(value))
                table.setItem(r, col, QTableWidgetItem(display))
            error = metrics.get("error", "")
            status_item = QTableWidgetItem(error if error else
                                           f"OK · {metrics.get('collected_at', '')[:10]}")
            if error:
                status_item.setToolTip(error)
            table.setItem(r, len(_TABLE_COLUMNS[key]) + 1, status_item)

        self._render_findings(key)

    def _render_findings(self, key: str):
        layout = self._findings_layouts[key]
        while layout.count() > 1:  # keep trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        findings = self.service.gap_analysis(key)
        if not findings:
            msg = QLabel(
                "No comparison yet — check the target brand plus competitors "
                "above and run a collection to see gap analysis here."
            )
            msg.setStyleSheet("color: #6B7280; padding: 12px;")
            msg.setWordWrap(True)
            layout.insertWidget(0, msg)
            return

        for f in findings:
            layout.insertWidget(layout.count() - 1, self._finding_card(f))

    def _finding_card(self, f: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("StatCard")
        lay = QVBoxLayout(card)
        lay.setSpacing(5)

        top = QHBoxLayout()
        badge = QLabel("GAP" if f["type"] == "gap" else "STRENGTH")
        badge.setStyleSheet(_GAP_BADGE if f["type"] == "gap" else _STRENGTH_BADGE)
        badge.setFixedHeight(18)
        title = QLabel(f["metric_label"])
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        title.setWordWrap(True)
        top.addWidget(badge)
        top.addWidget(title, 1)
        lay.addLayout(top)

        versus = QLabel(
            f"{f['target_brand']}: {f['target_display']}   vs   "
            f"{f['leader_brand']}: {f['leader_display']}"
        )
        versus.setStyleSheet("font-size: 12px; color: #111827; font-weight: 600;")
        lay.addWidget(versus)

        why = QLabel(f["why"])
        why.setWordWrap(True)
        why.setStyleSheet("font-size: 12px; color: #374151;")
        lay.addWidget(why)

        if f.get("tactics"):
            tactics_hdr = QLabel("Tactics")
            tactics_hdr.setStyleSheet(
                "font-size: 11px; color: #6B7280; font-weight: bold;")
            lay.addWidget(tactics_hdr)
            for tactic in f["tactics"]:
                t = QLabel(f"•  {tactic}")
                t.setWordWrap(True)
                t.setStyleSheet("font-size: 12px; color: #374151; padding-left: 6px;")
                lay.addWidget(t)
        return card
