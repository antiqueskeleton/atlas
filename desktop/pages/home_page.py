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
        self._subtitle.setStyleSheet("font-size: 14px; color: #69727E;")
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

        # #104: first-run setup checklist — visible only until the four
        # required steps are done, then it disappears for good.
        self._setup_frame, self._setup_lay = self._status_card("Getting Started")
        self._setup_frame.setVisible(False)

        # #101: Home as mission control — per-source data freshness at a
        # glance, so "is my data current?" never requires touring five pages.
        self._health_frame, self._health_lay = self._status_card("Data Health")

        root.addWidget(self._title)
        root.addWidget(self._subtitle)
        root.addSpacing(8)
        root.addWidget(self._setup_frame)
        root.addWidget(kpi_widget)
        root.addSpacing(8)
        root.addWidget(self._health_frame)
        root.addSpacing(8)
        root.addWidget(self._activity)
        root.addStretch()
        self.setLayout(root)

    @staticmethod
    def _status_card(title: str):
        from PySide6.QtWidgets import QFrame
        frame = QFrame()
        frame.setObjectName("StatCard")
        lay = QVBoxLayout()
        lay.setSpacing(3)
        lay.setContentsMargins(14, 10, 14, 12)
        header = QLabel(title)
        header.setObjectName("CardTitle")
        lay.addWidget(header)
        frame.setLayout(lay)
        return frame, lay

    @staticmethod
    def _clear_rows(lay):
        while lay.count() > 1:  # keep the title
            item = lay.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _status_row(state: str, text: str) -> QLabel:
        """state: ok | warn | todo — one glanceable line per source/step."""
        mark, color = {
            "ok":   ("\u2713", "#2E8B5E"),
            "warn": ("\u26a0", "#B45309"),
            "todo": ("\u25cb", "#69727E"),
        }[state]
        row = QLabel(f'<span style="color:{color}; font-weight:bold;">{mark}</span>'
                     f'&nbsp;&nbsp;<span style="color:#2B323A;">{text}</span>')
        row.setStyleSheet("font-size: 12px;")
        row.setWordWrap(True)
        return row

    def _refresh_setup_and_health(self):
        from datetime import datetime
        from backend.intelligence.intelligence_repository import IntelligenceRepository
        from backend.services.backup_service import list_backups
        from backend.targeted_review.targeted_review_repository import (
            TargetedReviewRepository)
        from backend.targeted_review.targeted_review_service import PLATFORMS

        cfg = self.app.config_service
        vis_repo = VisibilityRepository()
        n_responses = vis_repo.count_responses()
        vis_runs = [r for r in (vis_repo.list_runs() or []) if r[6] == "completed"]
        intel_runs = [r for r in IntelligenceRepository().list_runs()
                      if r[6] == "completed"]
        ai_keys = sum(1 for v in (cfg.settings.get("api_keys") or {}).values() if v)

        # ── Setup checklist (#104) ────────────────────────────────────────────
        steps = [
            (bool(cfg.get_target_brand()),
             "Set the target brand (Settings)"),
            (ai_keys > 0,
             "Add at least one AI provider key (Settings)"),
            (n_responses > 0,
             "Run a Visibility Collection (Visibility page) to start the dataset"),
            (len(intel_runs) > 0,
             "Run an Intelligence Analysis (Intelligence page) for the first briefing"),
        ]
        if all(done for done, _ in steps):
            self._setup_frame.setVisible(False)
        else:
            self._clear_rows(self._setup_lay)
            for done, text in steps:
                self._setup_lay.addWidget(
                    self._status_row("ok" if done else "todo", text))
            platform_creds = cfg.settings.get("platform_credentials") or {}
            has_platform = any(any(v for v in fields.values())
                               for fields in platform_creds.values())
            self._setup_lay.addWidget(self._status_row(
                "ok" if has_platform else "todo",
                "Optional: add platform research keys for Targeted Review "
                "(Settings → Platform Research)"))
            self._setup_frame.setVisible(True)

        # ── Data health (#101) ────────────────────────────────────────────────
        self._clear_rows(self._health_lay)

        def age_days(iso: str):
            try:
                return (datetime.now() - datetime.fromisoformat(iso)).days
            except (ValueError, TypeError):
                return None

        if vis_runs:
            days = age_days(vis_runs[0][4])
            stale = days is None or days >= 7
            self._health_lay.addWidget(self._status_row(
                "warn" if stale else "ok",
                f"Visibility: last collection {vis_runs[0][4][:10]}"
                + (f" ({days}d ago)" if days is not None else "")
                + f" · {len(vis_runs)} runs · {n_responses:,} responses"
                + (" — run the Saved Panel to keep trends comparable"
                   if stale else "")))
        else:
            self._health_lay.addWidget(self._status_row(
                "warn", "Visibility: no collections yet"))

        if intel_runs:
            days = age_days(intel_runs[0][4])
            self._health_lay.addWidget(self._status_row(
                "ok" if days is not None and days < 7 else "warn",
                f"Intelligence: last analysis {intel_runs[0][4][:10]}"
                + (f" ({days}d ago)" if days is not None else "")
                + f" · {len(intel_runs)} runs"))
        else:
            self._health_lay.addWidget(self._status_row(
                "warn", "Intelligence: no analysis yet"))

        tr_repo = TargetedReviewRepository()
        parts = []
        any_collected = False
        for key, provider_cls in PLATFORMS.items():
            latest = tr_repo.latest_findings(provider_cls.platform_name)
            dates = [m.get("collected_at", "")[:10] for m in latest.values()
                     if m.get("collected_at")]
            if dates:
                any_collected = True
                parts.append(f"{provider_cls.platform_name} {max(dates)[5:]}")
            else:
                parts.append(f"{provider_cls.platform_name} —")
        self._health_lay.addWidget(self._status_row(
            "ok" if any_collected else "todo",
            "Targeted Review: " + " · ".join(parts)))

        backups = list_backups()
        if backups:
            hours = (datetime.now().timestamp() - backups[0].stat().st_mtime) / 3600
            self._health_lay.addWidget(self._status_row(
                "ok" if hours < 48 else "warn",
                f"Backups: {len(backups)} on disk, newest {hours:.0f}h old"))
        else:
            self._health_lay.addWidget(self._status_row(
                "warn", "Backups: none yet (created automatically at launch)"))

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        self._refresh_setup_and_health()
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
