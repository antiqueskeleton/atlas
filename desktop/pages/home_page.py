from collections import Counter
from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from backend.intelligence.intelligence_service import IntelligenceService
from backend.knowledge.knowledge_repository import KnowledgeRepository
from backend.visibility.brand_matcher import resolve_target_brand, text_contains_term
from backend.visibility.visibility_repository import VisibilityRepository
from desktop.widgets.activity_feed import ActivityFeed
from desktop.widgets.stat_card import StatCard


def _summarize_prompt_set(prompt_set: str) -> str:
    """A Visibility run's prompt_set field is a comma-joined string of every
    selected family name (visibility_page.py's _get_selected_prompts) —
    selecting 20+ families is the normal case for a real collection run, so
    that field can be a multi-hundred-character wall of text with no place
    in a short activity feed. Show a count once there's more than one; a
    single family name is still short and worth showing as-is."""
    if not prompt_set:
        return "—"
    n = prompt_set.count(",") + 1
    if n == 1:
        return prompt_set
    return f"{n} prompt sets"


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
        self._mention_card    = StatCard(
            "Brand Mention Rate",  "—", "run Intelligence Analysis first",
            info=(
                "% of responses in your MOST RECENT Intelligence Analysis run that "
                "mention your target brand. This is not the same as Visibility Score "
                "on the Visibility page, which uses ALL collected Visibility responses "
                "— this tile only reflects the smaller sample from the latest "
                "Intelligence run."
            ),
        )
        self._responses_card  = StatCard(
            "Responses Stored",    "—", "in visibility database",
            info="Total AI responses ever collected across all Visibility runs, stored in the database.",
        )
        self._vis_runs_card   = StatCard(
            "Visibility Runs",     "—", "completed",
            info="Number of completed Visibility collection runs (prompts sent to AI providers and saved).",
        )
        self._intel_runs_card = StatCard(
            "Intelligence Runs",   "—", "completed",
            info=(
                "Number of completed Intelligence Analysis runs (executive briefing + "
                "strategic opportunities synthesized from stored responses)."
            ),
        )
        self._brands_card     = StatCard(
            "Brands Tracked",      "—", "active in knowledge base",
            info=(
                "Number of brands marked ACTIVE in the Knowledge library, out of the "
                "total tracked (inactive brands are excluded from Visibility analytics "
                "and mention counting, but still stored)."
            ),
        )

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
                    # Word-boundary check (#87) — plain substring credited
                    # CAT for "category" and WEN for "went".
                    if any(text_contains_term(lower, t) for t in terms):
                        counts[b] += 1
            resolved_target = resolve_target_brand(target, brand_terms.keys())
            rate = round(counts.get(resolved_target, 0) / max(total, 1) * 100)
            self._mention_card.set_value(f"{rate}%")
            self._mention_card.set_subtitle(f"intelligence analysis · {total} responses")
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
            label = _summarize_prompt_set(prompt_set)
            events.append((started_at or "", f"Visibility · {label} · {provider} · {date}"))
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
