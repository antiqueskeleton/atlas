from collections import Counter
from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from backend.intelligence.intelligence_service import IntelligenceService
from backend.knowledge.knowledge_repository import KnowledgeRepository
from backend.visibility.visibility_repository import VisibilityRepository
from desktop.widgets.activity_feed import ActivityFeed
from desktop.widgets.stat_card import StatCard


class HomePage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._build_ui()
        self.refresh()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        brand = self.app.get_target_brand() or "your market"
        hour = datetime.now().hour
        greeting = (
            "Good Morning" if hour < 12
            else "Good Afternoon" if hour < 17
            else "Good Evening"
        )

        self._title = QLabel(greeting)
        self._title.setStyleSheet("font-size: 28px; font-weight: bold;")
        self._title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._subtitle = QLabel(f"Here's what Atlas knows about {brand} today.")
        self._subtitle.setStyleSheet("font-size: 14px; color: #6B7280;")
        self._subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # KPI row
        self._mention_card    = StatCard("Brand Mention Rate",  "—", "run Intelligence Analysis first")
        self._responses_card  = StatCard("Responses Stored",    "—", "in visibility database")
        self._vis_runs_card   = StatCard("Visibility Runs",     "—", "completed")
        self._intel_runs_card = StatCard("Intelligence Runs",   "—", "completed")
        self._brands_card     = StatCard("Brands Tracked",      "—", "active in knowledge base")

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        for card in (
            self._mention_card, self._responses_card, self._vis_runs_card,
            self._intel_runs_card, self._brands_card,
        ):
            kpi_row.addWidget(card)

        kpi_widget = QWidget()
        kpi_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        kpi_widget.setLayout(kpi_row)

        self._activity = ActivityFeed("Recent Activity")

        root.addWidget(self._title)
        root.addWidget(self._subtitle)
        root.addSpacing(8)
        root.addWidget(kpi_widget)
        root.addSpacing(8)
        root.addWidget(self._activity)
        root.addStretch()
        self.setLayout(root)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        vis_repo   = VisibilityRepository()
        know_repo  = KnowledgeRepository()
        intel_svc  = IntelligenceService(
            self.app.provider_manager,
            target_brand=self.app.get_target_brand(),
        )
        target = self.app.get_target_brand()

        # Update subtitle in case target brand changed in Settings
        brand = target or "your market"
        self._subtitle.setText(f"Here's what Atlas knows about {brand} today.")

        # ── Responses stored ──────────────────────────────────────────────────
        total_responses = vis_repo.count_responses()
        self._responses_card.set_value(str(total_responses))
        self._responses_card.set_subtitle(
            "run Visibility to collect data" if not total_responses
            else "in visibility database"
        )

        # ── Visibility runs ───────────────────────────────────────────────────
        # list_runs returns DESC (most recent first); TrendsService reverses for charts
        vis_runs       = vis_repo.list_runs()
        completed_vis  = [r for r in vis_runs if r[6] == "completed"]
        self._vis_runs_card.set_value(str(len(completed_vis)))
        if completed_vis:
            last_date = completed_vis[0][4][:10]
            self._vis_runs_card.set_subtitle(f"last: {last_date}")

        # ── Intelligence runs ─────────────────────────────────────────────────
        intel_runs      = intel_svc.list_runs()   # already DESC by started_at
        completed_intel = [r for r in intel_runs if r[6] == "completed"]
        self._intel_runs_card.set_value(str(len(completed_intel)))
        if completed_intel:
            last_date = completed_intel[0][4][:10]
            self._intel_runs_card.set_subtitle(f"last: {last_date}")

        # ── Brand mention rate (from last IE run — DB only, no API calls) ─────
        latest = intel_svc.get_latest_briefing()
        if latest and target:
            results     = latest["results"]
            brand_terms = know_repo.get_brand_detection_terms()
            counts: Counter = Counter()
            total = 0
            for _, _, response, _ in results:
                total += 1
                lower = response.lower()
                for b, terms in brand_terms.items():
                    if any(t in lower for t in terms):
                        counts[b] += 1
            rate = round(counts.get(target, 0) / max(total, 1) * 100)
            self._mention_card.set_value(f"{rate}%")
            self._mention_card.set_subtitle(f"{target} · {total} responses analyzed")
        else:
            self._mention_card.set_value("—")
            self._mention_card.set_subtitle("run Intelligence Analysis first")

        # ── Active brands ─────────────────────────────────────────────────────
        brands       = know_repo.list_brands()
        active_count = sum(1 for b in brands if b[4])
        self._brands_card.set_value(str(active_count))
        self._brands_card.set_subtitle(f"of {len(brands)} total in knowledge base")

        # ── Recent activity — merge vis + intel runs, newest first ────────────
        events = []
        for r in completed_vis[:6]:
            _id, provider, _model, prompt_set, started_at, *_ = r
            date = started_at[:10] if started_at else "?"
            events.append((started_at or "", f"Visibility · {prompt_set} · {provider} · {date}"))
        for r in completed_intel[:4]:
            _id, provider, _model, _brand, started_at, *_ = r
            date = started_at[:10] if started_at else "?"
            events.append((started_at or "", f"Intelligence · {provider} · {date}"))

        events.sort(key=lambda x: x[0], reverse=True)
        items = [text for _, text in events[:8]]

        self._activity.set_items(
            items if items
            else [
                "No runs yet.",
                "Visit Visibility to collect AI responses.",
            ]
        )
