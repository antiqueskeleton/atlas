"""
PDF report generator for Atlas AI Visibility Intelligence reports.
Uses ReportLab Platypus for layout and matplotlib for embedded charts.
"""
import io
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # non-interactive backend — safe alongside Qt
import matplotlib.pyplot as plt

from backend.visibility.brand_matcher import resolve_target_brand
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image,
)

# ── Palette ────────────────────────────────────────────────────────────────────
C_BLUE    = HexColor('#0B84FF')
C_NAVY    = HexColor('#1E3A5F')
C_DARK    = HexColor('#111827')
C_MED     = HexColor('#374151')
C_GRAY    = HexColor('#6B7280')
C_LIGHT   = HexColor('#D1D5DB')
C_BG      = HexColor('#F9FAFB')
C_ROW_ALT = HexColor('#F3F4F6')
C_TBL_HDR = HexColor('#2D5A8E')  # section-title row in tables

PAGE_W, PAGE_H = LETTER          # 612 × 792 points  (8.5 × 11 in)
MARGIN    = 0.65 * inch           # 46.8 pt each side
CONTENT_W = PAGE_W - 2 * MARGIN  # ≈ 518 pt  (≈ 7.19 in)


class VisibilityPDFReport:
    """
    Generate a professional multi-section PDF from visibility analytics data.

    Usage:
        rpt = VisibilityPDFReport(analytics, runs, stats, target_brand="Firman")
        rpt.generate("/path/to/report.pdf")
    """

    def __init__(self, analytics: dict, runs: list, stats: dict, target_brand: str = ""):
        self.analytics    = analytics
        self.runs         = runs
        self.stats        = stats
        self.target_brand = resolve_target_brand(
            target_brand or analytics.get("target_brand", "Target Brand"),
            analytics.get("brand_counts", {}),
        )
        self.generated_at = datetime.now()
        self._styles      = self._build_styles()

    # ── Public ─────────────────────────────────────────────────────────────────

    def generate(self, output_path: str) -> None:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=LETTER,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN + 0.25 * inch,   # clearance for header bar on inner pages
            bottomMargin=MARGIN + 0.1 * inch,
            title=f"Atlas AI Visibility Report — {self.target_brand}",
            author="Atlas AI",
        )
        story = (
            self._cover_and_summary()   # cover + exec summary — no page break between them
            + self._brand_analysis()
            + self._provider_analysis()
            + self._feature_analysis()
            + self._channel_intelligence()
            # appendix intentionally omitted
        )
        doc.build(story,
                  onFirstPage=self._decorate_page,
                  onLaterPages=self._decorate_page)

    # ── Page chrome ────────────────────────────────────────────────────────────

    def _decorate_page(self, canvas, doc):
        if doc.page == 1:
            return  # cover — clean slate
        canvas.saveState()

        # Header bar
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, PAGE_H - 0.42 * inch, PAGE_W, 0.42 * inch, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont('Helvetica-Bold', 7.5)
        canvas.drawString(MARGIN, PAGE_H - 0.265 * inch,
                          'ATLAS AI  ·  VISIBILITY INTELLIGENCE REPORT')
        canvas.setFont('Helvetica', 7.5)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.265 * inch,
                               self.target_brand.upper())

        # Footer
        canvas.setStrokeColor(C_LIGHT)
        canvas.line(MARGIN, 0.52 * inch, PAGE_W - MARGIN, 0.52 * inch)
        canvas.setFillColor(C_GRAY)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(MARGIN, 0.36 * inch,
                          f"Generated {self.generated_at.strftime('%B %d, %Y')}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.36 * inch, f"Page {doc.page}")

        canvas.restoreState()

    # ── Cover + Executive Summary (page 1) ────────────────────────────────────

    def _cover_and_summary(self) -> list:
        a  = self.analytics
        s  = self._styles
        tb = self.target_brand

        story = [Spacer(1, 1.1 * inch)]
        story.append(HRFlowable(width=CONTENT_W, thickness=3,
                                color=C_BLUE, spaceAfter=0.16 * inch))
        story.append(Paragraph("ATLAS AI", s['CoverLabel']))
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph("Visibility Intelligence Report", s['CoverTitle']))
        story.append(Spacer(1, 0.18 * inch))          # extra breathing room
        story.append(Paragraph("Target Brand:", s['CoverBrandLabel']))
        story.append(Spacer(1, 0.04 * inch))
        story.append(Paragraph(tb, s['CoverBrand']))
        story.append(Spacer(1, 0.18 * inch))
        story.append(HRFlowable(width=CONTENT_W, thickness=1,
                                color=C_LIGHT, spaceAfter=0.18 * inch))

        meta = [
            ["Generated",       self.generated_at.strftime("%B %d, %Y  ·  %H:%M")],
            ["Total Responses", f"{self.stats.get('total', 0):,}"],
            ["Collection Runs", str(self.stats.get('runs', 0))],
            ["Providers",       str(self.stats.get('providers', 0))],
            ["Prompt Families", str(self.stats.get('families', 0))],
        ]
        story.append(self._meta_table(meta))
        story.append(Spacer(1, 0.28 * inch))

        # ── Executive Summary (flows directly after cover content) ────────────
        story.append(Paragraph("Executive Summary", s['H1']))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(
            f"This report analyzes how <b>{tb}</b> is perceived and mentioned across "
            "AI-generated responses collected through the Atlas AI Visibility Collection "
            "system. Prompts representing common consumer purchase journeys, product "
            "research scenarios, and brand comparison questions were sent to leading AI "
            "providers. Responses were scanned to identify brand, feature, and channel "
            "mentions — building a data-driven picture of how AI models describe and "
            "recommend products in your category. Use this report to benchmark brand "
            "presence, identify competitor advantages, and prioritize content or PR "
            "strategy to improve AI visibility over time.",
            s['Body']
        ))
        story.append(Spacer(1, 0.14 * inch))

        # KPI tiles
        score      = a.get('target_visibility_score', 0)
        brand_cnts = a.get('brand_counts', {})
        sorted_b   = sorted(brand_cnts.items(), key=lambda x: -x[1])
        rank       = next((i + 1 for i, (b, _) in enumerate(sorted_b)
                           if b == tb), None)
        total      = a.get('total_responses', 0)
        # total tracked brands, not just ones with >=1 mention in this dataset —
        # same fix as #48 already applied to visibility_page.py; this report
        # generator had its own separate copy of the old, wrong denominator.
        total_tracked = a.get('total_tracked_brands', len(sorted_b))

        kpi_data = [
            ["Visibility Score", "Mention Rank", "Responses Analyzed", "Brands Tracked"],
            [
                f"{score}%",
                f"#{rank} of {total_tracked}" if rank else "—",
                f"{total:,}",
                str(total_tracked),
            ],
        ]
        kpi_tbl = Table(kpi_data, colWidths=[CONTENT_W / 4] * 4)
        kpi_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 7.5),
            ('TOPPADDING',    (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('BACKGROUND',    (0, 1), (-1, 1), C_BG),
            ('FONTNAME',      (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 1), (-1, 1), 18),
            ('TEXTCOLOR',     (0, 1), (-1, 1), C_BLUE),
            ('TOPPADDING',    (0, 1), (-1, 1), 12),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 12),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
            ('INNERGRID',     (0, 0), (-1, -1), 0.5, C_LIGHT),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_BLUE),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph(
            "<b>Visibility Score</b> — the percentage of all collected responses that mention "
            f"{tb}. <b>Mention Rank</b> — {tb}'s rank among all tracked brands by total "
            "mentions (lower number = higher prominence). <b>Responses Analyzed</b> — total "
            "AI provider responses in the dataset. <b>Brands Tracked</b> — number of "
            "competitor brands being monitored.",
            s['Caption']
        ))
        story.append(Spacer(1, 0.18 * inch))

        # Provider scores
        prov_scores = a.get('provider_visibility_scores', {})
        if prov_scores:
            story.append(Paragraph("Visibility Score by Provider", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                f"How {tb}'s visibility score varies across AI providers. Differences "
                "may reflect training data coverage, knowledge cutoff dates, or "
                "provider-specific content curation.",
                s['Body']
            ))
            story.append(Spacer(1, 0.07 * inch))
            story.append(self._section_table(
                "Visibility Score by Provider",
                ["Provider", f"{tb} Visibility Score"],
                [[prov.capitalize(), f"{sc}%"]
                 for prov, sc in sorted(prov_scores.items(), key=lambda x: -x[1])],
                col_widths=[3.59, 3.6],
            ))

        story.append(PageBreak())
        return story

    # ── Brand Analysis ─────────────────────────────────────────────────────────

    def _brand_analysis(self) -> list:
        a  = self.analytics
        s  = self._styles
        tb = self.target_brand

        brand_cnts  = a.get('brand_counts', {})
        total       = max(a.get('total_responses', 1), 1)
        top_brands  = sorted(brand_cnts.items(), key=lambda x: -x[1])[:12]
        pos_counts  = a.get('brand_position_counts', {})
        pos_share   = a.get('brand_position_share', {})
        first_share = a.get('first_mention_share', {})
        neg_counts  = a.get('negative_brand_counts', {})
        neg_rate    = a.get('brand_negative_rate', {})

        story = [Paragraph("Brand Analysis", s['H1']), Spacer(1, 0.08 * inch)]
        story.append(Paragraph(
            "Brand analysis measures how frequently each brand appears across all collected "
            "AI responses and how prominently it is positioned within those responses.",
            s['Body']
        ))
        story.append(Spacer(1, 0.14 * inch))

        # ── Mention Rate chart ────────────────────────────────────────────────
        if top_brands:
            story.append(Paragraph("Top Brands by Mention Rate", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                f"Mention Rate = (responses mentioning the brand ÷ total responses) × 100. "
                f"Any response that references a brand — whether as a primary recommendation, "
                f"in a comparison, or incidentally — is counted. {tb} is highlighted in blue.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))
            story.append(self._bar_chart_h(
                labels=[b for b, _ in top_brands],
                values=[round(c / total * 100, 1) for _, c in top_brands],
                xlabel="Mention Rate (%)",
                highlight=tb,
                figsize=(7, max(2.5, len(top_brands) * 0.33)),
            ))
            story.append(Spacer(1, 0.2 * inch))

        # ── Brand Position Share (pivot: brand × position) ────────────────────
        if pos_counts:
            positions  = sorted(pos_counts.keys())
            all_brands = sorted(
                {b for pc in pos_counts.values() for b in pc},
                key=lambda b: -pos_counts.get(1, {}).get(b, 0),
            )

            story.append(Paragraph("Brand Position Share", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "Position Share measures where each brand appears within a response — "
                "first mention, second, third, and so on. First-position mentions carry "
                "the most weight, as they represent the AI's primary recommendation. "
                "Values show the percentage of all responses where that brand occupied "
                "each position.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))

            # Compact pivot: brand rows × position columns
            col_headers = ["Brand"] + [f"#{p} Share" for p in positions]
            data_rows   = []
            for brand in all_brands:
                row = [brand]
                for pos in positions:
                    share = pos_share.get(pos, {}).get(brand, 0)
                    cnt   = pos_counts.get(pos, {}).get(brand, 0)
                    row.append(f"{share}%" if cnt > 0 else "—")
                data_rows.append(row)

            n_pos   = len(positions)
            brand_w = 2.0
            pos_w   = round((CONTENT_W / inch - brand_w) / max(n_pos, 1), 3)
            story.append(self._section_table(
                "Brand Position Share",
                col_headers,
                data_rows,
                col_widths=[brand_w] + [pos_w] * n_pos,
            ))
            story.append(Spacer(1, 0.2 * inch))

        # ── First-Mention Share ───────────────────────────────────────────────
        if first_share:
            story.append(Paragraph("First-Mention Share", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "The percentage of responses where each brand was the very first brand "
                "mentioned — the leading indicator of which brand AI models consider the "
                "primary answer to a consumer's query.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))
            story.append(self._section_table(
                "First-Mention Share",
                ["Brand", "First-Mention %"],
                [[b, f"{sh}%"]
                 for b, sh in sorted(first_share.items(), key=lambda x: -x[1])[:10]],
                col_widths=[4.59, 2.6],
            ))

        # ── Brand Sentiment ────────────────────────────────────────────────────
        if neg_counts:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("Brand Sentiment", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "Negative mentions are responses where a brand was cast unfavorably or lost "
                "a direct comparison (e.g. \"unlike Firman, Honda includes electric start\"). "
                "Negative % is of that brand's own mentions, not of all responses — it answers "
                "\"when AI brings this brand up, how often is it unfavorable,\" independent of "
                "how often the brand is mentioned at all. Detected via keyword/context rules, "
                "not a language model — see Sources note below for limitations.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))
            story.append(self._section_table(
                "Brand Sentiment",
                ["Brand", "Mentions", "Negative", "Negative %"],
                [[b, str(brand_cnts.get(b, 0)), str(neg_counts.get(b, 0)), f"{neg_rate.get(b, 0)}%"]
                 for b, _ in sorted(brand_cnts.items(), key=lambda x: -x[1])[:12]],
                col_widths=[3.19, 1.3, 1.3, 1.4],
            ))

        story.append(PageBreak())
        return story

    # ── Provider Analysis (pivot: brand × provider) ────────────────────────────

    def _provider_analysis(self) -> list:
        prov_brand = self.analytics.get('provider_brand_counts', {})
        if not prov_brand:
            return []

        s  = self._styles
        tb = self.target_brand

        providers = sorted(prov_brand.keys())
        all_brands = sorted(
            {b for pb in prov_brand.values() for b in pb},
            key=lambda b: -sum(prov_brand[p].get(b, 0) for p in providers),
        )

        story = [Paragraph("Brand Mentions by Provider", s['H1']), Spacer(1, 0.08 * inch)]
        story.append(Paragraph(
            "This pivot table shows how many AI responses from each provider mentioned "
            "each brand. Differences across providers indicate where brand awareness is "
            "stronger or weaker, which may highlight opportunities to improve visibility "
            "through targeted content, press, or product placement.",
            s['Body']
        ))
        story.append(Spacer(1, 0.12 * inch))

        col_headers = ["Brand"] + [p.capitalize() for p in providers]
        data_rows   = []
        for brand in all_brands:
            row = [brand] + [
                str(prov_brand[p].get(brand, 0)) if prov_brand[p].get(brand, 0) else "—"
                for p in providers
            ]
            data_rows.append(row)

        n_prov  = len(providers)
        brand_w = 1.9
        prov_w  = round((CONTENT_W / inch - brand_w) / max(n_prov, 1), 3)
        story.append(self._section_table(
            "Brand Mentions by Provider",
            col_headers,
            data_rows,
            col_widths=[brand_w] + [prov_w] * n_prov,
        ))

        story.append(PageBreak())
        return story

    # ── Feature Analysis ───────────────────────────────────────────────────────

    def _feature_analysis(self) -> list:
        a            = self.analytics
        feature_cnts = a.get('feature_counts', {})
        feat_brand   = a.get('feature_brand_counts', {})
        if not feature_cnts:
            return []

        s  = self._styles
        tb = self.target_brand

        story = [Paragraph("Feature Intelligence", s['H1']), Spacer(1, 0.08 * inch)]
        story.append(Paragraph(
            "Feature mentions are identified by scanning each AI response for keywords "
            "associated with specific product attributes (Dual Fuel, Electric Start, "
            "Inverter, Quiet, RV Ready, etc.). This analysis reveals which product "
            "features AI models most strongly associate with brands in your category — "
            "a proxy for consumer-facing feature positioning and perceived product strengths.",
            s['Body']
        ))
        story.append(Spacer(1, 0.14 * inch))

        # Feature mentions chart
        top = sorted(feature_cnts.items(), key=lambda x: -x[1])[:12]
        story.append(Paragraph("Feature Mentions", s['H2']))
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph(
            "Total number of responses referencing each feature keyword, across all "
            "providers and prompt families.",
            s['Body']
        ))
        story.append(Spacer(1, 0.08 * inch))
        story.append(self._bar_chart_h(
            labels=[f for f, _ in top],
            values=[c for _, c in top],
            xlabel="Mentions",
            figsize=(7, max(2.5, len(top) * 0.33)),
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Feature × Brand pivot (brand rows, feature columns)
        if feat_brand:
            story.append(Paragraph("Feature Mentions by Brand", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "How many responses mentioned each brand alongside each product feature. "
                "High counts indicate that AI models frequently associate that brand with "
                "that capability — a signal of strong consumer perception or content presence.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))

            # Limit to top 8 features to keep columns readable
            top_features = [f for f, _ in sorted(feature_cnts.items(), key=lambda x: -x[1])[:8]]
            all_brands   = sorted(
                {b for fb in feat_brand.values() for b in fb},
                key=lambda b: -sum(feat_brand.get(f, {}).get(b, 0) for f in top_features),
            )

            col_headers = ["Brand"] + top_features
            data_rows   = []
            for brand in all_brands:
                row = [brand] + [
                    str(feat_brand.get(f, {}).get(brand, 0)) if feat_brand.get(f, {}).get(brand, 0) else "—"
                    for f in top_features
                ]
                data_rows.append(row)

            n_feat  = len(top_features)
            brand_w = 1.3
            feat_w  = round((CONTENT_W / inch - brand_w) / max(n_feat, 1), 3)
            story.append(self._section_table(
                "Feature Mentions by Brand",
                col_headers,
                data_rows,
                col_widths=[brand_w] + [feat_w] * n_feat,
                fontsize=7,
            ))

        story.append(PageBreak())
        return story

    # ── Channel Intelligence ───────────────────────────────────────────────────

    def _channel_intelligence(self) -> list:
        a            = self.analytics
        channel_cnts = a.get('channel_counts', {})
        ch_brand     = a.get('channel_brand_counts', {})
        gaps         = a.get('target_channel_gap', [])
        if not channel_cnts and not gaps:
            return []

        s  = self._styles
        tb = self.target_brand

        story = [Paragraph("Channel Intelligence", s['H1']), Spacer(1, 0.08 * inch)]
        story.append(Paragraph(
            "Channels are identified through keyword co-occurrence analysis. When an AI "
            "response mentions a channel keyword (e.g., YouTube, Amazon, Home Depot) "
            "alongside brand names, it is counted as a channel mention for each co-occurring "
            "brand. These are channels that AI models identify as significant touchpoints "
            "where top brands have established presence — not based on web scraping or "
            "actual platform data, but on how AI systems describe brand distribution and "
            "market reach.",
            s['Body']
        ))
        story.append(Spacer(1, 0.14 * inch))

        # Top channels table — brands column uses Paragraph for word-wrap
        if channel_cnts:
            story.append(Paragraph("Top Channels by AI Mention Frequency", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "Channels ranked by total number of AI responses that reference them. "
                "The Top Brands column lists which brands are most frequently cited "
                "alongside each channel.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))

            # widths: Channel(2.1) + Mentions(0.75) + Top Brands(4.34) = 7.19
            ch_w, mn_w, br_w = 2.1 * inch, 0.75 * inch, (CONTENT_W - 2.85 * inch)
            cell_style = s['SmallBody']

            hdr_row = [
                Paragraph("Channel", s['TblHdr']),
                Paragraph("Mentions", s['TblHdr']),
                Paragraph("Top Brands", s['TblHdr']),
            ]
            data_rows = [hdr_row]
            for ch, count in sorted(channel_cnts.items(), key=lambda x: -x[1])[:20]:
                top_b = ch_brand.get(ch, {})
                brand_text = ",  ".join(
                    f"{b} ({c})" for b, c
                    in sorted(top_b.items(), key=lambda x: -x[1])[:5]
                )
                data_rows.append([
                    Paragraph(ch, cell_style),
                    Paragraph(str(count), cell_style),
                    Paragraph(brand_text, cell_style),
                ])

            tbl = Table(data_rows, colWidths=[ch_w, mn_w, br_w], repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
                ('TOPPADDING',    (0, 0), (-1, 0), 6),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_BLUE),
                ('TOPPADDING',    (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, C_ROW_ALT]),
                ('LINEBELOW',     (0, 1), (-1, -1), 0.25, C_LIGHT),
                ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.25 * inch))

        # Channel gaps
        if gaps:
            story.append(Paragraph(f"{tb} Channel Gaps", s['H2']))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                f"Channels where a competitor brand appears more frequently than {tb} in "
                "AI responses. A gap indicates that AI models are more likely to associate "
                "competitors with those channels, which may reflect higher competitor "
                "activity, review volume, or content presence in that space. "
                "<b>Gap</b> shows the raw difference in mention counts. "
                "<b>Lead Factor</b> shows how many times more often the top competitor "
                "appears relative to {tb} in that channel — a 3× lead factor means the "
                "competitor was cited three times as frequently.",
                s['Body']
            ))
            story.append(Spacer(1, 0.08 * inch))

            # widths: Channel(2.0) + Target(0.75) + Competitor(1.75) + Count(0.72) + Gap(0.72) + Factor(1.25) = 7.19
            cw = [2.0 * inch, 0.75 * inch, 1.75 * inch, 0.72 * inch, 0.72 * inch, 1.25 * inch]
            gap_col_headers = [
                "Channel", tb, "Top Competitor", "Their Count", "Gap", "Lead Factor"
            ]
            gap_data = []
            for g in gaps[:20]:
                target_n = g.get("target_count", 0) or 0
                comp_n   = g["top_competitor_count"]
                gap_n    = comp_n - target_n
                factor   = f"{comp_n / max(target_n, 1):.1f}×" if target_n > 0 else f"{comp_n}× more"
                gap_data.append([
                    g["channel"],
                    str(target_n),
                    g["top_competitor"],
                    str(comp_n),
                    f"+{gap_n}",
                    factor,
                ])

            story.append(self._section_table(
                f"{tb} Channel Gaps",
                gap_col_headers,
                gap_data,
                col_widths_pt=cw,
                fontsize=8,
            ))

        return story

    # ── Chart ──────────────────────────────────────────────────────────────────

    def _bar_chart_h(self, labels, values, xlabel="", highlight=None, figsize=(7, 3)):
        fig, ax = plt.subplots(figsize=figsize)
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#F9FAFB')

        colors = ['#0B84FF' if lbl == highlight else '#93C5FD' for lbl in labels]
        ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                height=0.58, edgecolor='white', linewidth=0.4)

        max_val = max(values) if values else 1
        for i, val in enumerate(values[::-1]):
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

    def _section_table(self, section_title: str, col_headers: list,
                       data_rows: list, col_widths=None,
                       col_widths_pt=None, fontsize: int = 8):
        """
        Table with two repeating header rows:
          Row 0 — section title spanning all columns  (repeats on continuation pages)
          Row 1 — column headers
          Row 2+ — data
        Both rows repeat on continuation pages via repeatRows=2,
        giving readers clear "continued" context without extra logic.
        """
        n = len(col_headers)

        # Column widths
        if col_widths_pt:
            col_w = col_widths_pt
        elif col_widths:
            col_w = [w * inch for w in col_widths]
        else:
            col_w = [CONTENT_W / n] * n

        all_rows = (
            [[section_title] + [""] * (n - 1)]   # row 0 — section title (will be spanned)
            + [col_headers]                        # row 1 — column headers
            + data_rows                            # rows 2+
        )

        tbl = Table(all_rows, colWidths=col_w, repeatRows=2)
        tbl.setStyle(TableStyle([
            # Section title row
            ('SPAN',          (0, 0), (-1, 0)),
            ('BACKGROUND',    (0, 0), (-1, 0), C_TBL_HDR),
            ('TEXTCOLOR',     (0, 0), (-1, 0), white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 7.5),
            ('TOPPADDING',    (0, 0), (-1, 0), 4),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            # Column header row
            ('BACKGROUND',    (0, 1), (-1, 1), C_NAVY),
            ('TEXTCOLOR',     (0, 1), (-1, 1), white),
            ('FONTNAME',      (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 1), (-1, 1), fontsize),
            ('TOPPADDING',    (0, 1), (-1, 1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
            ('LINEBELOW',     (0, 1), (-1, 1), 1.5, C_BLUE),
            # Data rows
            ('FONTNAME',      (0, 2), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 2), (-1, -1), fontsize),
            ('TEXTCOLOR',     (0, 2), (-1, -1), C_DARK),
            ('TOPPADDING',    (0, 2), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 2), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [white, C_ROW_ALT]),
            ('LINEBELOW',     (0, 2), (-1, -1), 0.25, C_LIGHT),
            # Outer border
            ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
        ]))
        return tbl

    def _data_table(self, rows, col_widths=None, fontsize=8):
        n_cols = len(rows[0]) if rows else 1
        col_w  = [w * inch for w in col_widths] if col_widths else [CONTENT_W / n_cols] * n_cols
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), fontsize),
            ('TOPPADDING',    (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_BLUE),
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 1), (-1, -1), fontsize),
            ('TEXTCOLOR',     (0, 1), (-1, -1), C_DARK),
            ('TOPPADDING',    (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, C_ROW_ALT]),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.25, C_LIGHT),
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

    # ── Styles ─────────────────────────────────────────────────────────────────

    def _build_styles(self):
        return {
            'H1': ParagraphStyle(
                'H1', fontName='Helvetica-Bold', fontSize=15,
                textColor=C_NAVY, spaceBefore=0, spaceAfter=3,
            ),
            'H2': ParagraphStyle(
                'H2', fontName='Helvetica-Bold', fontSize=10,
                textColor=C_MED, spaceBefore=4, spaceAfter=2,
            ),
            'Body': ParagraphStyle(
                'Body', fontName='Helvetica', fontSize=8.5,
                textColor=C_MED, leading=12.5,
            ),
            'Caption': ParagraphStyle(
                'Caption', fontName='Helvetica', fontSize=7.5,
                textColor=C_GRAY, leading=11, italics=0,
            ),
            'SmallBody': ParagraphStyle(
                'SmallBody', fontName='Helvetica', fontSize=7.5,
                textColor=C_DARK, leading=10,
            ),
            'TblHdr': ParagraphStyle(
                'TblHdr', fontName='Helvetica-Bold', fontSize=8,
                textColor=white, leading=10,
            ),
            'CoverLabel': ParagraphStyle(
                'CoverLabel', fontName='Helvetica-Bold', fontSize=11,
                textColor=C_BLUE, alignment=TA_LEFT, spaceAfter=2,
            ),
            'CoverTitle': ParagraphStyle(
                'CoverTitle', fontName='Helvetica-Bold', fontSize=30,
                textColor=C_DARK, alignment=TA_LEFT, spaceAfter=4,
            ),
            'CoverBrandLabel': ParagraphStyle(
                'CoverBrandLabel', fontName='Helvetica-Bold', fontSize=9,
                textColor=C_GRAY, alignment=TA_LEFT, spaceAfter=2,
            ),
            'CoverBrand': ParagraphStyle(
                'CoverBrand', fontName='Helvetica-Bold', fontSize=22,
                textColor=C_NAVY, alignment=TA_LEFT,
            ),
        }
