"""
PDF report generator for Atlas AI Visibility Intelligence reports.
Uses ReportLab Platypus for layout and matplotlib for embedded charts.
"""
import io
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # non-interactive backend — safe alongside Qt
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image,
)

# ── Brand palette ──────────────────────────────────────────────────────────────
C_BLUE    = HexColor('#0B84FF')
C_NAVY    = HexColor('#1E3A5F')
C_DARK    = HexColor('#111827')
C_MED     = HexColor('#374151')
C_GRAY    = HexColor('#6B7280')
C_LIGHT   = HexColor('#D1D5DB')
C_BG      = HexColor('#F9FAFB')
C_ROW_ALT = HexColor('#F3F4F6')

PAGE_W, PAGE_H = LETTER
MARGIN    = 0.65 * inch
CONTENT_W = PAGE_W - 2 * MARGIN


class VisibilityPDFReport:
    """
    Generate a multi-section PDF from visibility analytics data.

    Usage:
        rpt = VisibilityPDFReport(analytics, runs, stats, target_brand="Firman")
        rpt.generate("/path/to/report.pdf")
    """

    def __init__(self, analytics: dict, runs: list, stats: dict, target_brand: str = ""):
        self.analytics    = analytics
        self.runs         = runs
        self.stats        = stats
        self.target_brand = target_brand or analytics.get("target_brand", "Target Brand")
        self.generated_at = datetime.now()
        self._styles      = self._build_styles()

    # ── Public ─────────────────────────────────────────────────────────────────

    def generate(self, output_path: str) -> None:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=LETTER,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN + 0.2 * inch,  # room for header bar on inner pages
            bottomMargin=MARGIN,
            title=f"Atlas AI Visibility Report — {self.target_brand}",
            author="Atlas AI",
        )
        story = (
            self._cover_page()
            + self._executive_summary()
            + self._brand_analysis()
            + self._provider_analysis()
            + self._feature_analysis()
            + self._channel_intelligence()
            + self._runs_appendix()
        )
        doc.build(story,
                  onFirstPage=self._decorate_page,
                  onLaterPages=self._decorate_page)

    # ── Page header / footer ───────────────────────────────────────────────────

    def _decorate_page(self, canvas, doc):
        if doc.page == 1:
            return  # cover page — clean, no chrome
        canvas.saveState()

        # Navy header bar
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, PAGE_H - 0.42 * inch, PAGE_W, 0.42 * inch, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont('Helvetica-Bold', 7.5)
        canvas.drawString(MARGIN, PAGE_H - 0.26 * inch,
                          'ATLAS AI  ·  VISIBILITY INTELLIGENCE REPORT')
        canvas.setFont('Helvetica', 7.5)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.26 * inch,
                               self.target_brand.upper())

        # Footer rule + text
        canvas.setStrokeColor(C_LIGHT)
        canvas.line(MARGIN, 0.52 * inch, PAGE_W - MARGIN, 0.52 * inch)
        canvas.setFillColor(C_GRAY)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(MARGIN, 0.36 * inch,
                          f"Generated {self.generated_at.strftime('%B %d, %Y')}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.36 * inch, f"Page {doc.page}")

        canvas.restoreState()

    # ── Cover page ─────────────────────────────────────────────────────────────

    def _cover_page(self) -> list:
        s = self._styles
        story = [Spacer(1, 1.8 * inch)]

        # Thin blue rule above title
        story.append(HRFlowable(width=CONTENT_W, thickness=3,
                                color=C_BLUE, spaceAfter=0.18 * inch))

        story.append(Paragraph("ATLAS AI", s['CoverLabel']))
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph("Visibility Intelligence Report", s['CoverTitle']))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(self.target_brand, s['CoverBrand']))
        story.append(Spacer(1, 0.18 * inch))
        story.append(HRFlowable(width=CONTENT_W, thickness=1,
                                color=C_LIGHT, spaceAfter=0.25 * inch))

        meta = [
            ["Generated",         self.generated_at.strftime("%B %d, %Y  ·  %H:%M")],
            ["Total Responses",   f"{self.stats.get('total', 0):,}"],
            ["Collection Runs",   str(self.stats.get('runs', 0))],
            ["Providers",         str(self.stats.get('providers', 0))],
            ["Prompt Families",   str(self.stats.get('families', 0))],
        ]
        story.append(self._meta_table(meta))
        story.append(PageBreak())
        return story

    # ── Executive summary ──────────────────────────────────────────────────────

    def _executive_summary(self) -> list:
        a  = self.analytics
        s  = self._styles
        story = [Paragraph("Executive Summary", s['H1']), Spacer(1, 0.12 * inch)]

        score       = a.get('target_visibility_score', 0)
        brand_cnts  = a.get('brand_counts', {})
        sorted_b    = sorted(brand_cnts.items(), key=lambda x: -x[1])
        rank        = next((i + 1 for i, (b, _) in enumerate(sorted_b)
                            if b == self.target_brand), None)
        total       = a.get('total_responses', 0)
        prov_scores = a.get('provider_visibility_scores', {})

        # KPI banner
        kpi_data = [
            ["Visibility Score", "Mention Rank", "Responses Analyzed", "Brands Tracked"],
            [
                f"{score}%",
                f"#{rank} of {len(sorted_b)}" if rank else "—",
                f"{total:,}",
                str(len(sorted_b)),
            ],
        ]
        kpi_tbl = Table(kpi_data, colWidths=[CONTENT_W / 4] * 4)
        kpi_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 8),
            ('TOPPADDING',    (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND',    (0, 1), (-1, 1), C_BG),
            ('FONTNAME',      (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 1), (-1, 1), 20),
            ('TEXTCOLOR',     (0, 1), (-1, 1), C_BLUE),
            ('TOPPADDING',    (0, 1), (-1, 1), 14),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 14),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
            ('INNERGRID',     (0, 0), (-1, -1), 0.5, C_LIGHT),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_BLUE),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 0.25 * inch))

        if prov_scores:
            story.append(Paragraph("Visibility Score by Provider", s['H2']))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Provider", "Visibility Score (%)"]]
            for prov, sc in sorted(prov_scores.items(), key=lambda x: -x[1]):
                rows.append([prov.capitalize(), f"{sc}%"])
            story.append(self._data_table(rows, col_widths=[3.5, 1.4]))

        story.append(PageBreak())
        return story

    # ── Brand analysis ─────────────────────────────────────────────────────────

    def _brand_analysis(self) -> list:
        a     = self.analytics
        s     = self._styles
        story = [Paragraph("Brand Analysis", s['H1']), Spacer(1, 0.12 * inch)]

        brand_cnts  = a.get('brand_counts', {})
        total       = max(a.get('total_responses', 1), 1)
        top_brands  = sorted(brand_cnts.items(), key=lambda x: -x[1])[:12]
        pos_counts  = a.get('brand_position_counts', {})
        pos_share   = a.get('brand_position_share', {})
        first_share = a.get('first_mention_share', {})

        if top_brands:
            story.append(Paragraph("Top Brands by Mention Rate", s['H2']))
            story.append(Spacer(1, 0.06 * inch))
            story.append(self._bar_chart_h(
                labels=[b for b, _ in top_brands],
                values=[round(c / total * 100, 1) for _, c in top_brands],
                xlabel="Mention Rate (%)",
                highlight=self.target_brand,
                figsize=(7, max(2.5, len(top_brands) * 0.33)),
            ))
            story.append(Spacer(1, 0.2 * inch))

        if pos_counts:
            story.append(Paragraph(
                "Brand Position Share  —  which brands are mentioned earliest in responses",
                s['H2']
            ))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Position", "Brand", "Mentions", "Share %"]]
            for pos in sorted(pos_counts.keys()):
                for brand, count in sorted(pos_counts[pos].items(), key=lambda x: -x[1])[:6]:
                    share = pos_share.get(pos, {}).get(brand, 0)
                    rows.append([f"#{pos}", brand, str(count), f"{share}%"])
            story.append(self._data_table(rows, col_widths=[0.7, 2.4, 1.0, 0.8]))
            story.append(Spacer(1, 0.2 * inch))

        if first_share:
            story.append(Paragraph(
                "First-Mention Share  —  % of responses where each brand appears first",
                s['H2']
            ))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Brand", "First-Mention %"]]
            for brand, share in sorted(first_share.items(), key=lambda x: -x[1])[:10]:
                rows.append([brand, f"{share}%"])
            story.append(self._data_table(rows, col_widths=[3.5, 1.4]))

        story.append(PageBreak())
        return story

    # ── Provider analysis ──────────────────────────────────────────────────────

    def _provider_analysis(self) -> list:
        prov_brand = self.analytics.get('provider_brand_counts', {})
        if not prov_brand:
            return []
        s     = self._styles
        story = [Paragraph("Provider Analysis", s['H1']), Spacer(1, 0.12 * inch)]
        story.append(Paragraph("Brand Mentions by Provider", s['H2']))
        story.append(Spacer(1, 0.06 * inch))
        rows = [["Provider", "Brand", "Mentions"]]
        for provider, brands in sorted(prov_brand.items()):
            for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                rows.append([provider.capitalize(), brand, str(count)])
        story.append(self._data_table(rows, col_widths=[1.5, 2.9, 0.5]))
        story.append(PageBreak())
        return story

    # ── Feature analysis ───────────────────────────────────────────────────────

    def _feature_analysis(self) -> list:
        a            = self.analytics
        feature_cnts = a.get('feature_counts', {})
        feat_brand   = a.get('feature_brand_counts', {})
        if not feature_cnts:
            return []
        s     = self._styles
        story = [Paragraph("Feature Intelligence", s['H1']), Spacer(1, 0.12 * inch)]

        top = sorted(feature_cnts.items(), key=lambda x: -x[1])[:12]
        story.append(Paragraph("Feature Mentions", s['H2']))
        story.append(Spacer(1, 0.06 * inch))
        story.append(self._bar_chart_h(
            labels=[f for f, _ in top],
            values=[c for _, c in top],
            xlabel="Mentions",
            figsize=(7, max(2.5, len(top) * 0.33)),
        ))
        story.append(Spacer(1, 0.2 * inch))

        if feat_brand:
            story.append(Paragraph("Feature Mentions by Brand", s['H2']))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Feature", "Brand", "Mentions"]]
            for feature, brands in sorted(feat_brand.items()):
                for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
                    rows.append([feature, brand, str(count)])
            story.append(self._data_table(rows, col_widths=[2.4, 2.0, 0.5]))

        story.append(PageBreak())
        return story

    # ── Channel intelligence ───────────────────────────────────────────────────

    def _channel_intelligence(self) -> list:
        a            = self.analytics
        channel_cnts = a.get('channel_counts', {})
        ch_brand     = a.get('channel_brand_counts', {})
        gaps         = a.get('firman_channel_gap', [])
        if not channel_cnts and not gaps:
            return []
        s     = self._styles
        story = [Paragraph("Channel Intelligence", s['H1']), Spacer(1, 0.12 * inch)]

        if channel_cnts:
            story.append(Paragraph("Top Channels by AI Mention Frequency", s['H2']))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Channel", "Mentions", "Top Brands"]]
            for ch, count in sorted(channel_cnts.items(), key=lambda x: -x[1])[:20]:
                top_brands = ch_brand.get(ch, {})
                brand_str = ", ".join(
                    f"{b} ({c})" for b, c
                    in sorted(top_brands.items(), key=lambda x: -x[1])[:4]
                )
                rows.append([ch, str(count), brand_str])
            story.append(self._data_table(rows, col_widths=[1.7, 0.7, 2.5]))
            story.append(Spacer(1, 0.25 * inch))

        if gaps:
            story.append(Paragraph(
                f"{self.target_brand} Channel Gaps  —  channels where competitors lead",
                s['H2']
            ))
            story.append(Spacer(1, 0.06 * inch))
            rows = [["Channel", self.target_brand, "Top Competitor", "Their Count"]]
            for g in gaps[:20]:
                rows.append([
                    g["channel"],
                    str(g.get("firman_count", 0)),
                    g["top_competitor"],
                    str(g["top_competitor_count"]),
                ])
            story.append(self._data_table(rows, col_widths=[1.8, 0.85, 1.65, 0.6]))

        story.append(PageBreak())
        return story

    # ── Recent runs appendix ───────────────────────────────────────────────────

    def _runs_appendix(self) -> list:
        if not self.runs:
            return []
        s     = self._styles
        story = [Paragraph("Appendix — Collection Runs", s['H1']), Spacer(1, 0.12 * inch)]
        rows  = [["Date", "Provider", "Families", "Responses", "Errors"]]
        for r in self.runs[:40]:
            err  = r[9] if len(r) > 9 else 0
            rows.append([
                (r[4] or "")[:16],
                (r[1] or ""),
                (r[3] or "")[:42],
                str(r[7]),
                str(err) if err else "—",
            ])
        story.append(self._data_table(
            rows, col_widths=[1.25, 0.85, 2.3, 0.7, 0.55], fontsize=7
        ))
        return story

    # ── Chart builder ──────────────────────────────────────────────────────────

    def _bar_chart_h(self, labels, values, xlabel="", highlight=None, figsize=(7, 3)):
        fig, ax = plt.subplots(figsize=figsize)
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#F9FAFB')

        colors = ['#0B84FF' if lbl == highlight else '#93C5FD' for lbl in labels]
        ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                height=0.58, edgecolor='white', linewidth=0.4)

        max_val = max(values) if values else 1
        for i, (lbl, val) in enumerate(zip(labels[::-1], values[::-1])):
            ax.text(val + max_val * 0.012, i, f"{val}",
                    va='center', ha='left', fontsize=8, color='#374151')

        ax.set_xlabel(xlabel, fontsize=8.5, color='#6B7280', labelpad=6)
        ax.tick_params(axis='y', labelsize=8.5, colors='#374151', length=0)
        ax.tick_params(axis='x', labelsize=7.5, colors='#9CA3AF', length=2)
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.spines['left'].set_color('#E5E7EB')
        ax.spines['bottom'].set_color('#E5E7EB')
        ax.set_xlim(0, max_val * 1.2)
        ax.grid(axis='x', color='#E5E7EB', linewidth=0.5, zorder=0)

        buf = io.BytesIO()
        fig.tight_layout(pad=0.5)
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return Image(buf, width=CONTENT_W, height=figsize[1] * 0.82 * inch)

    # ── Table builders ─────────────────────────────────────────────────────────

    def _data_table(self, rows, col_widths=None, fontsize=8):
        n_cols = len(rows[0]) if rows else 1
        if col_widths:
            col_w = [w * inch for w in col_widths]
        else:
            col_w = [CONTENT_W / n_cols] * n_cols

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header
            ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), fontsize),
            ('TOPPADDING',    (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_BLUE),
            # Data
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 1), (-1, -1), fontsize),
            ('TEXTCOLOR',     (0, 1), (-1, -1), C_DARK),
            ('TOPPADDING',    (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, C_ROW_ALT]),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.25, C_LIGHT),
            # Border
            ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
        ]))
        return tbl

    def _meta_table(self, rows):
        col_w = [1.6 * inch, CONTENT_W - 1.6 * inch]
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9),
            ('TEXTCOLOR',     (0, 0), (0, -1), C_GRAY),
            ('TEXTCOLOR',     (1, 0), (1, -1), C_DARK),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW',     (0, 0), (-1, -1), 0.25, C_LIGHT),
        ]))
        return tbl

    # ── Style registry ─────────────────────────────────────────────────────────

    def _build_styles(self):
        return {
            'H1': ParagraphStyle(
                'H1', fontName='Helvetica-Bold', fontSize=16,
                textColor=C_NAVY, spaceBefore=0, spaceAfter=4,
            ),
            'H2': ParagraphStyle(
                'H2', fontName='Helvetica-Bold', fontSize=10,
                textColor=C_MED, spaceBefore=6, spaceAfter=2,
            ),
            'Body': ParagraphStyle(
                'Body', fontName='Helvetica', fontSize=9,
                textColor=C_DARK, leading=13,
            ),
            'CoverLabel': ParagraphStyle(
                'CoverLabel', fontName='Helvetica-Bold', fontSize=11,
                textColor=C_BLUE, alignment=TA_LEFT, spaceAfter=2,
            ),
            'CoverTitle': ParagraphStyle(
                'CoverTitle', fontName='Helvetica-Bold', fontSize=30,
                textColor=C_DARK, alignment=TA_LEFT, spaceAfter=4,
            ),
            'CoverBrand': ParagraphStyle(
                'CoverBrand', fontName='Helvetica-Bold', fontSize=20,
                textColor=C_GRAY, alignment=TA_LEFT,
            ),
        }
