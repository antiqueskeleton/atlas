from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as mticker

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backend.visibility.trends_service import TrendsService


# ── Color palettes ─────────────────────────────────────────────────────────────

_BRAND_PALETTE = [
    "#2563EB", "#DC2626", "#16A34A", "#D97706",
    "#7C3AED", "#0891B2", "#EA580C", "#9333EA",
]
_PROVIDER_COLORS = {
    "openai":     "#10A37F",
    "OpenAI":     "#10A37F",
    "anthropic":  "#D97706",
    "Anthropic":  "#D97706",
    "Google Gemini": "#4285F4",
    "gemini":     "#4285F4",
    "Perplexity": "#20C997",
    "perplexity": "#20C997",
    "Grok":       "#111827",
    "grok":       "#111827",
    "Mistral":    "#FF7000",
    "mistral":    "#FF7000",
    "Mock":       "#6B7280",
    "mock":       "#6B7280",
}
_FEAT_PALETTE = [
    "#6366F1", "#F43F5E", "#14B8A6", "#F59E0B",
    "#8B5CF6", "#EC4899",
]


# ── Reusable canvas ────────────────────────────────────────────────────────────

class _MplCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(8, 4.5), dpi=96, facecolor="#FFFFFF")
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.18)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._style_axes()

    def _style_axes(self):
        self.ax.set_facecolor("#F9FAFB")
        self.ax.grid(color="#E5E7EB", linewidth=0.8, linestyle="--")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        for spine in ("left", "bottom"):
            self.ax.spines[spine].set_color("#D1D5DB")

    def reset(self):
        self.ax.clear()
        self._style_axes()

    def no_data(self, msg="No data yet.\n\nRun Visibility collection to populate trends."):
        self.reset()
        self.ax.text(
            0.5, 0.5, msg,
            transform=self.ax.transAxes,
            ha="center", va="center",
            fontsize=11, color="#6B7280",
            linespacing=1.8,
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.draw()


def _tab(canvas: _MplCanvas) -> QWidget:
    w = QWidget()
    v = QVBoxLayout()
    v.setContentsMargins(4, 4, 4, 4)
    v.addWidget(canvas)
    w.setLayout(v)
    return w


# ── KPI card ────────────────────────────────────────────────────────────────────

def _kpi(title: str, value: str = "—", sub: str = "") -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lay = QVBoxLayout()
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    v = QLabel(value)
    v.setObjectName("CardValue")
    lay.addWidget(t)
    lay.addWidget(v)
    if sub:
        s = QLabel(sub)
        s.setObjectName("CardSubtitle")
        lay.addWidget(s)
    frame.setLayout(lay)
    return frame, v


# ── Main page ──────────────────────────────────────────────────────────────────

class TrendsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.service = TrendsService(target_brand=app.get_target_brand())
        self._summaries: list[dict] = []
        self._build_ui()
        self._refresh()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(10)

        # Header
        title = QLabel("Trends")
        title.setStyleSheet("font-size:30px;font-weight:bold;")
        subtitle = QLabel(
            "How AI visibility changes over time — across providers, brands, features, and prompt sets."
        )
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")
        subtitle.setWordWrap(True)

        # Controls bar
        ctrl = QHBoxLayout()
        self.status_lbl = QLabel("Loading…")
        self.status_lbl.setStyleSheet("color:#6B7280;font-size:13px;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._refresh)
        ctrl.addWidget(self.status_lbl)
        ctrl.addStretch()
        ctrl.addWidget(refresh_btn)
        ctrl_w = QWidget()
        ctrl_w.setLayout(ctrl)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        brand = self.app.get_target_brand() or "Target Brand"
        self._kpi_score_card,  self._kpi_score  = _kpi(f"{brand} Avg Score", "—%", "avg across all runs")
        self._kpi_top_ps_card, self._kpi_top_ps = _kpi("Top Prompt Set", "—", "best performing category")
        self._kpi_best_card,   self._kpi_best   = _kpi("Best Provider", "—", "highest avg score")
        for card in (self._kpi_score_card, self._kpi_top_ps_card, self._kpi_best_card):
            kpi_row.addWidget(card)
        kpi_w = QWidget()
        kpi_w.setLayout(kpi_row)

        # Canvases
        self._c_score    = _MplCanvas()
        self._c_brands   = _MplCanvas()
        self._c_provider = _MplCanvas()
        self._c_features = _MplCanvas()
        self._c_position = _MplCanvas()
        self._c_promptset = _MplCanvas()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(_tab(self._c_score),    "Visibility Score")
        self.tabs.addTab(_tab(self._c_brands),   "Brand Standing")
        self.tabs.addTab(_tab(self._c_provider), "By Provider")
        self.tabs.addTab(_tab(self._c_features), "Features")
        self.tabs.addTab(_tab(self._c_position), "Positions")
        self.tabs.addTab(_tab(self._c_promptset), "Prompt Sets")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(ctrl_w)
        root.addWidget(kpi_w)
        root.addWidget(self.tabs)
        self.setLayout(root)

    # ── Refresh ────────────────────────────────────────────────────────────────

    def _refresh(self):
        # Re-read target brand in case it changed in Settings
        self.service.target_brand = self.app.get_target_brand()
        self.service.analytics.target_brand = self.app.get_target_brand()

        self._summaries = self.service.get_run_summaries()
        n = len(self._summaries)

        if n == 0:
            self.status_lbl.setText("No visibility runs yet.")
            self._kpi_runs.setText("0")
            for c in (self._c_score, self._c_brands, self._c_provider,
                      self._c_features, self._c_position, self._c_promptset):
                c.no_data()
            return

        # Update status
        first_date = self._summaries[0]["date"]
        last_date  = self._summaries[-1]["date"]
        self.status_lbl.setText(
            f"{n} run{'s' if n != 1 else ''} · {first_date} → {last_date}"
        )

        # KPIs
        scores = [s["target_score"] for s in self._summaries]
        avg = round(sum(scores) / len(scores), 1) if scores else 0

        prov_avgs = self.service.provider_averages(self._summaries)
        best_prov = max(prov_avgs, key=prov_avgs.get) if prov_avgs else "—"

        top_ps = self.service.best_prompt_set_for_target(self._summaries)
        top_ps_display = (top_ps[:22] + "…") if len(top_ps) > 22 else top_ps

        self._kpi_score.setText(f"{avg}%")
        self._kpi_top_ps.setText(top_ps_display)
        self._kpi_best.setText(best_prov)

        # Draw active tab + pre-draw score tab
        self._draw_score()
        idx = self.tabs.currentIndex()
        if idx != 0:
            self._draw_tab(idx)

    def _on_tab_changed(self, idx: int):
        if self._summaries:
            self._draw_tab(idx)

    def _draw_tab(self, idx: int):
        if   idx == 0: self._draw_score()
        elif idx == 1: self._draw_brands()
        elif idx == 2: self._draw_provider()
        elif idx == 3: self._draw_features()
        elif idx == 4: self._draw_position()
        elif idx == 5: self._draw_promptset()

    # ── Charts ─────────────────────────────────────────────────────────────────

    def _draw_score(self):
        s = self._summaries
        if not s:
            self._c_score.no_data()
            return
        if len(s) < 5:
            self._c_score.no_data(
                f"Score trend needs 5+ runs to be meaningful.\n"
                f"You have {len(s)} — keep running Visibility to build history."
            )
            return

        c = self._c_score
        c.reset()
        ax = c.ax
        brand = self.app.get_target_brand() or "Target Brand"

        labels  = [x["label"] for x in s]
        scores  = [x["target_score"] for x in s]
        providers = [x["provider"] for x in s]
        xs = range(len(s))

        # Color points by provider
        for i, (score, prov) in enumerate(zip(scores, providers)):
            clr = _PROVIDER_COLORS.get(prov, "#6B7280")
            ax.scatter(i, score, color=clr, s=60, zorder=4)

        # Main line
        ax.plot(xs, scores, color="#2563EB", linewidth=2, zorder=3)

        # Moving average (window=3 if enough data)
        if len(scores) >= 3:
            ma = [
                round(sum(scores[max(0, i-1):i+2]) / len(scores[max(0, i-1):i+2]), 1)
                for i in range(len(scores))
            ]
            ax.plot(xs, ma, color="#93C5FD", linewidth=1.5,
                    linestyle="--", label="3-run avg", zorder=2)

        # Mean reference line
        mean_score = sum(scores) / len(scores)
        ax.axhline(mean_score, color="#9CA3AF", linewidth=1,
                   linestyle=":", label=f"Mean {mean_score:.1f}%")

        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("Visibility Score (%)", fontsize=9)
        ax.set_ylim(bottom=0)
        ax.set_title(f"{brand} Visibility Score Over Time", fontsize=11, fontweight="bold", pad=8)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.legend(fontsize=8, loc="upper left")

        # Provider legend patches
        unique_provs = list(dict.fromkeys(providers))
        if len(unique_provs) > 1:
            from matplotlib.lines import Line2D
            handles = [
                Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=_PROVIDER_COLORS.get(p, "#6B7280"),
                       markersize=7, label=p)
                for p in unique_provs
            ]
            ax.legend(handles=handles, fontsize=8, loc="upper right", title="Provider", title_fontsize=8)

        c.draw()

    def _draw_brands(self):
        s = self._summaries
        if not s:
            self._c_brands.no_data()
            return

        c = self._c_brands
        c.reset()
        ax = c.ax
        brand = self.app.get_target_brand() or ""

        snapshot = self.service.brand_snapshot(s, top_n=8)
        # Sort ascending so highest appears at top of horizontal bar chart
        sorted_brands = sorted(snapshot, key=lambda b: snapshot[b])
        names  = sorted_brands
        values = [snapshot[b] for b in names]
        colors = ["#2563EB" if n == brand else "#94A3B8" for n in names]

        bars = ax.barh(names, values, color=colors, height=0.5, zorder=3)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9, color="#374151"
            )

        ax.set_xlabel("Avg Mention Rate (%)", fontsize=9)
        ax.set_xlim(0, (max(values) * 1.35 if values else 10))
        ax.set_title(
            "Brand Mention Rates — Current Standing\n(avg across all runs · target brand in blue)",
            fontsize=10, fontweight="bold", pad=8
        )
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        c.draw()

    def _draw_provider(self):
        s = self._summaries
        if not s:
            self._c_provider.no_data()
            return

        c = self._c_provider
        c.reset()
        ax = c.ax
        brand = self.app.get_target_brand() or "Target Brand"

        prov_avgs = self.service.provider_averages(s)
        if not prov_avgs:
            c.no_data("No provider data.")
            return

        prov_counts = {}
        for run in s:
            prov_counts[run["provider"]] = prov_counts.get(run["provider"], 0) + 1

        sorted_provs = sorted(prov_avgs, key=lambda p: prov_avgs[p])
        avgs = [prov_avgs[p] for p in sorted_provs]
        colors = [_PROVIDER_COLORS.get(p, "#6B7280") for p in sorted_provs]

        bars = ax.barh(sorted_provs, avgs, color=colors, height=0.55, zorder=3)
        for bar, val, prov in zip(bars, avgs, sorted_provs):
            n = prov_counts.get(prov, 0)
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}%  ({n} run{'s' if n != 1 else ''})",
                    va="center", fontsize=9, color="#374151")

        ax.set_xlabel("Avg Visibility Score (%)", fontsize=9)
        ax.set_xlim(0, max(avgs) * 1.35 if avgs else 10)
        ax.set_title(f"{brand} Score by Provider", fontsize=11, fontweight="bold", pad=8)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        c.draw()

    def _draw_features(self):
        s = self._summaries
        if not s:
            self._c_features.no_data()
            return
        if len(s) < 5:
            self._c_features.no_data(
                f"Feature trend needs 5+ runs to be meaningful.\n"
                f"You have {len(s)} — keep running Visibility to build history."
            )
            return

        c = self._c_features
        c.reset()
        ax = c.ax

        series = self.service.feature_time_series(s, top_n=6)
        if not series:
            c.no_data("No feature data available.")
            return

        labels = [x["label"] for x in s]
        xs = range(len(s))
        colors = _FEAT_PALETTE

        for i, (feat, rates) in enumerate(series.items()):
            ax.plot(xs, rates, color=colors[i % len(colors)], linewidth=1.8,
                    label=f"{feat} (now: {rates[-1]:.0f}%)",
                    marker="o" if len(s) <= 15 else None, markersize=3.5, zorder=3)

        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("Mention Rate (%)", fontsize=9)
        ax.set_ylim(bottom=0)
        ax.set_title("Feature Mention Trends Over Time", fontsize=11, fontweight="bold", pad=8)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.legend(fontsize=7, loc="upper left", ncol=2)
        c.draw()

    def _draw_position(self):
        s = self._summaries
        if not s:
            self._c_position.no_data()
            return
        if len(s) < 5:
            self._c_position.no_data(
                f"Position trend needs 5+ runs to be meaningful.\n"
                f"You have {len(s)} — keep running Visibility to build history."
            )
            return

        c = self._c_position
        c.reset()
        ax = c.ax
        brand = self.app.get_target_brand() or "Target Brand"

        series = self.service.position_time_series(s, top_n=5)
        if not series:
            c.no_data("No position data available.")
            return

        labels = [x["label"] for x in s]
        xs = list(range(len(s)))
        colors = list(_BRAND_PALETTE)

        non_targets = [b for b in series if b != brand]
        targets     = [b for b in series if b == brand]

        for i, b in enumerate(non_targets):
            rates = series[b]
            ax.plot(xs, rates, color=colors[(i+1) % len(colors)],
                    linewidth=1.5, label=f"{b}", zorder=3,
                    marker="o" if len(s) <= 15 else None, markersize=3.5)

        for b in targets:
            rates = series[b]
            ax.plot(xs, rates, color="#2563EB", linewidth=2.5,
                    label=f"{b} ★", zorder=5,
                    marker="o" if len(s) <= 15 else None, markersize=5)

        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("First-Mention Share (%)", fontsize=9)
        ax.set_ylim(bottom=0)
        ax.set_title(
            "First-Position Brand Mentions Over Time\n"
            "(% of responses where brand is mentioned first)",
            fontsize=10, fontweight="bold", pad=8
        )
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.legend(fontsize=7, loc="upper left", ncol=2)
        c.draw()

    def _draw_promptset(self):
        s = self._summaries
        if not s:
            self._c_promptset.no_data()
            return

        c = self._c_promptset
        c.reset()
        ax = c.ax
        brand = self.app.get_target_brand() or "Target Brand"

        ps_avgs = self.service.prompt_set_averages(s)
        if not ps_avgs:
            c.no_data("No prompt set data.")
            return

        ps_counts = {}
        for run in s:
            ps = run["prompt_set"]
            ps_counts[ps] = ps_counts.get(ps, 0) + 1

        sorted_ps = sorted(ps_avgs, key=lambda p: ps_avgs[p])
        avgs = [ps_avgs[p] for p in sorted_ps]

        bars = ax.barh(sorted_ps, avgs, color="#6366F1", height=0.5, zorder=3)
        for bar, val, ps in zip(bars, avgs, sorted_ps):
            n = ps_counts.get(ps, 0)
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}%  ({n} run{'s' if n != 1 else ''})",
                    va="center", fontsize=9, color="#374151")

        ax.set_xlabel("Avg Target Brand Visibility Score (%)", fontsize=9)
        ax.set_xlim(0, max(avgs) * 1.35 if avgs else 10)
        ax.set_title(f"{brand} Score by Prompt Set", fontsize=11, fontweight="bold", pad=8)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        c.draw()
