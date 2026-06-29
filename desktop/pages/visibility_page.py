from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.visibility.visibility_service import VisibilityService


def _stat_card(title, value, subtitle=""):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    layout = QVBoxLayout()
    layout.setSpacing(2)

    t = QLabel(title)
    t.setObjectName("CardTitle")

    v = QLabel(value)
    v.setObjectName("CardValue")

    layout.addWidget(t)
    layout.addWidget(v)

    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("CardSubtitle")
        layout.addWidget(s)

    frame.setLayout(layout)
    return frame, v


def _section(title):
    frame = QFrame()
    frame.setObjectName("StatCard")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    layout = QVBoxLayout()
    layout.setSpacing(6)

    t = QLabel(title)
    t.setObjectName("CardTitle")

    body = QTextEdit()
    body.setReadOnly(True)
    body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    layout.addWidget(t)
    layout.addWidget(body)
    frame.setLayout(layout)
    return frame, body


class VisibilityPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.service = VisibilityService(self.app.provider_manager)

        root = QVBoxLayout()
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        title = QLabel("Atlas Visibility")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel(
            "Run prompt sets against AI providers and measure brand visibility."
        )
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        # ── Control bar ───────────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.prompt_set = QComboBox()
        self.prompt_set.addItems(self.service.prompt_library.list_sets())
        self.prompt_set.setFixedWidth(220)

        self.provider = QComboBox()
        for key in self.app.provider_manager.list_providers():
            self.provider.addItem(key)
        self.provider.setFixedWidth(160)

        run_btn = QPushButton("Run Visibility Collection")
        run_btn.setFixedWidth(200)
        run_btn.clicked.connect(self.run_visibility)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#6B7280;font-size:13px;")

        controls.addWidget(QLabel("Prompt Set:"))
        controls.addWidget(self.prompt_set)
        controls.addWidget(QLabel("Provider:"))
        controls.addWidget(self.provider)
        controls.addWidget(run_btn)
        controls.addWidget(self.status_label)
        controls.addStretch()

        controls_widget = QWidget()
        controls_widget.setLayout(controls)

        # ── KPI row ───────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._score_card, self._score_val = _stat_card(
            "Firman Visibility Score", "—%", "% of responses mentioning Firman"
        )
        self._total_card, self._total_val = _stat_card(
            "Total Responses", "—", "across all runs"
        )
        self._top_card, self._top_val = _stat_card(
            "Top Mentioned Brand", "—", "most frequent in responses"
        )
        self._runs_card, self._runs_val = _stat_card(
            "Runs Completed", "—", "visibility collection runs"
        )

        kpi_row.addWidget(self._score_card)
        kpi_row.addWidget(self._total_card)
        kpi_row.addWidget(self._top_card)
        kpi_row.addWidget(self._runs_card)

        kpi_widget = QWidget()
        kpi_widget.setLayout(kpi_row)

        # ── Content panels ────────────────────────────────────────────────────
        self._pos_frame, self._pos_body = _section("Brand Position Share")
        self._brand_frame, self._brand_body = _section("Brand Mentions by Provider")
        self._feature_frame, self._feature_body = _section("Feature Mentions")
        self._runs_frame, self._runs_body = _section("Recent Runs")
        self._responses_frame, self._responses_body = _section(
            "Latest Run Responses"
        )

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self._pos_frame)
        left_splitter.addWidget(self._brand_frame)
        left_splitter.setSizes([300, 300])

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self._feature_frame)
        right_splitter.addWidget(self._runs_frame)
        right_splitter.addWidget(self._responses_frame)
        right_splitter.setSizes([200, 160, 240])

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(right_splitter)
        h_splitter.setSizes([580, 420])
        h_splitter.setHandleWidth(6)

        # ── Assemble ──────────────────────────────────────────────────────────
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(controls_widget)
        root.addWidget(kpi_widget)
        root.addWidget(h_splitter)

        self.setLayout(root)
        self.refresh()

    # ── Actions ───────────────────────────────────────────────────────────────

    def run_visibility(self):
        self.status_label.setText("Running…")
        self.status_label.repaint()

        result = self.service.run(
            prompt_set=self.prompt_set.currentText(),
            provider_name=self.provider.currentText(),
        )
        run = result["run"]

        self.status_label.setText(
            f"Done — {run.response_count} responses in {run.duration_seconds:.1f}s"
        )
        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        summary = self.service.analytics_summary()
        runs = self.service.list_runs() or []

        # KPI cards
        score = summary["firman_visibility_score"]
        total = summary["total_responses"]
        brand_counts = summary.get("brand_counts", {})
        top_brand = (
            max(brand_counts, key=brand_counts.get) if brand_counts else "—"
        )

        self._score_val.setText(f"{score}%")
        self._total_val.setText(str(total))
        self._top_val.setText(top_brand)
        self._runs_val.setText(str(len(runs)))

        # Brand Position Share
        pos_text = "Factual mention order — not a recommendation rank.\n\n"
        pos_counts = summary.get("brand_position_counts", {})
        pos_shares = summary.get("brand_position_share", {})
        if pos_counts:
            for pos in sorted(pos_counts.keys()):
                pos_text += f"Position {pos}:\n"
                for brand, count in pos_counts[pos].items():
                    share = pos_shares.get(pos, {}).get(brand, 0)
                    pos_text += f"  • {brand}: {count} ({share}%)\n"
                pos_text += "\n"
        else:
            pos_text += "No data yet. Run a visibility collection first."
        self._pos_body.setPlainText(pos_text)

        # Brand Mentions by Provider
        prov_brand = summary.get("provider_brand_counts", {})
        prov_text = ""
        if prov_brand:
            for provider, brands in prov_brand.items():
                prov_text += f"{provider}:\n"
                for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                    prov_text += f"  • {brand}: {count}\n"
                prov_text += "\n"
        else:
            prov_text = "No provider brand data yet."
        self._brand_body.setPlainText(prov_text)

        # Feature Mentions
        feat_text = ""
        feature_counts = summary.get("feature_counts", {})
        if feature_counts:
            for feature, count in sorted(
                feature_counts.items(), key=lambda x: -x[1]
            ):
                feat_text += f"• {feature}: {count}\n"
        else:
            feat_text = "No feature data yet."
        self._feature_body.setPlainText(feat_text)

        # Recent Runs
        runs_text = ""
        if runs:
            for run in runs[:15]:
                runs_text += (
                    f"{run[4]}  |  {run[1]}  |  {run[3]}  |  {run[7]} responses\n"
                )
        else:
            runs_text = "No visibility runs yet."
        self._runs_body.setPlainText(runs_text)

        # Latest Run Responses
        latest_id = runs[0][0] if runs else None
        resp_text = ""
        if latest_id:
            responses = self.service.get_responses_for_run(latest_id)
            for r in responses:
                resp_text += f"Prompt: {r[4]}\n"
                resp_text += f"Response: {r[5][:400]}...\n"
                resp_text += "─" * 60 + "\n\n"
        else:
            resp_text = "No responses available."
        self._responses_body.setPlainText(resp_text)
