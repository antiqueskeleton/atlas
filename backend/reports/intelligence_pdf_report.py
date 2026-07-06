"""
PDF report generator for Atlas AI Intelligence Engine reports.
Shares the same palette and chrome as VisibilityPDFReport.
"""
import io
import textwrap
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)

# ── Palette (shared with visibility PDF) ──────────────────────────────────────
C_BLUE    = HexColor('#0B84FF')
C_NAVY    = HexColor('#1E3A5F')
C_DARK    = HexColor('#111827')
C_MED     = HexColor('#374151')
C_GRAY    = HexColor('#6B7280')
C_LIGHT   = HexColor('#D1D5DB')
C_BG      = HexColor('#F9FAFB')
C_ROW_ALT = HexColor('#F3F4F6')
C_TBL_HDR = HexColor('#2D5A8E')
C_GREEN   = HexColor('#16A34A')
C_AMBER   = HexColor('#F59E0B')

PAGE_W, PAGE_H = LETTER
MARGIN    = 0.65 * inch
CONTENT_W = PAGE_W - 2 * MARGIN


def _pdf_safe(text: str) -> str:
    """
    reportlab's built-in Helvetica only supports WinAnsiEncoding (~cp1252) —
    emoji and other characters outside it don't raise an error, they render
    as a broken glyph box. AI response text routinely contains emoji, so
    strip anything Helvetica can't represent before it reaches a Paragraph.
    """
    if not text:
        return text
    return text.encode("cp1252", errors="ignore").decode("cp1252")


class IntelligencePDFReport:
    """
    Generate a professional PDF from an Intelligence Engine analysis run.

    Usage:
        rpt = IntelligencePDFReport(
            run=run_tuple,
            briefing=briefing_tuple,
            results=results_list,
            opportunities=opp_list,
            target_brand="Firman",
        )
        rpt.generate("/path/to/report.pdf")

    Data shapes (from intelligence_repository):
        run         — (run_id, provider, model, target_brand, started_at, …, duration_seconds)
        briefing    — (product_summary, persona_summary, journey_summary,
                       opportunities_text, executive_briefing, created_at)
        results     — [(analyst_name, prompt, response, collected_at), …]
        opportunities — [(id, title, evidence, description, status), …]
    """

    def __init__(self, run, briefing, results, opportunities,
                 target_brand: str = ""):
        self.run           = run or ()
        self.briefing      = briefing or ()
        self.results       = results or []
        self.opportunities = opportunities or []
        self.target_brand  = (
            target_brand
            or (run[3] if run and len(run) > 3 else "")
            or "Target Brand"
        )
        self.generated_at  = datetime.now()
        self._styles       = self._build_styles()

    # ── Public ─────────────────────────────────────────────────────────────────

    def generate(self, output_path: str) -> None:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=LETTER,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN + 0.25 * inch,
            bottomMargin=MARGIN + 0.1 * inch,
            title=f"Atlas AI Intelligence Report — {self.target_brand}",
            author="Atlas AI",
        )
        story = (
            self._cover()
            + self._executive_briefing()
            + self._analyst_sections()
            + self._opportunities_section()
        )
        doc.build(story,
                  onFirstPage=self._decorate_page,
                  onLaterPages=self._decorate_page)

    # ── Page chrome ────────────────────────────────────────────────────────────

    def _decorate_page(self, canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()

        canvas.setFillColor(C_NAVY)
        canvas.rect(0, PAGE_H - 0.42 * inch, PAGE_W, 0.42 * inch, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont('Helvetica-Bold', 7.5)
        canvas.drawString(MARGIN, PAGE_H - 0.265 * inch,
                          'ATLAS AI  ·  INTELLIGENCE ENGINE REPORT')
        canvas.setFont('Helvetica', 7.5)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.265 * inch,
                               self.target_brand.upper())

        canvas.setStrokeColor(C_LIGHT)
        canvas.line(MARGIN, 0.52 * inch, PAGE_W - MARGIN, 0.52 * inch)
        canvas.setFillColor(C_GRAY)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(MARGIN, 0.36 * inch,
                          f"Generated {self.generated_at.strftime('%B %d, %Y')}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.36 * inch, f"Page {doc.page}")

        canvas.restoreState()

    # ── Cover page ─────────────────────────────────────────────────────────────

    def _cover(self) -> list:
        s  = self._styles
        tb = self.target_brand
        run = self.run

        story = [Spacer(1, 1.1 * inch)]
        story.append(HRFlowable(width=CONTENT_W, thickness=3,
                                color=C_BLUE, spaceAfter=0.16 * inch))
        story.append(Paragraph("ATLAS AI", s['CoverLabel']))
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph("Intelligence Engine Report", s['CoverTitle']))
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Target Brand:", s['CoverBrandLabel']))
        story.append(Spacer(1, 0.04 * inch))
        story.append(Paragraph(tb, s['CoverBrand']))
        story.append(Spacer(1, 0.18 * inch))
        story.append(HRFlowable(width=CONTENT_W, thickness=1,
                                color=C_LIGHT, spaceAfter=0.18 * inch))

        provider  = run[1].capitalize() if run and len(run) > 1 else "—"
        model     = run[2] if run and len(run) > 2 else "—"
        started   = run[4][:16].replace("T", "  ") if run and len(run) > 4 and run[4] else "—"
        duration  = f"{run[7]:.0f}s" if run and len(run) > 7 and run[7] else "—"
        n_results = len(self.results)
        n_opps    = len(self.opportunities)

        meta = [
            ["Generated",           self.generated_at.strftime("%B %d, %Y  ·  %H:%M")],
            ["Run Date",            started],
            ["AI Provider",         provider],
            ["Model",               model],
            ["Duration",            duration],
            ["Analyst Responses",   str(n_results)],
            ["Opportunities Found", str(n_opps)],
        ]
        story.append(self._meta_table(meta))
        story.append(PageBreak())
        return story

    # ── Executive Briefing ─────────────────────────────────────────────────────

    def _executive_briefing(self) -> list:
        s   = self._styles
        txt = self.briefing[4] if self.briefing and len(self.briefing) > 4 else ""
        if not txt:
            return []

        story = [Paragraph("Executive Briefing", s['H1']), Spacer(1, 0.08 * inch)]

        for para in txt.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            story.append(Paragraph(_pdf_safe(para), s['Body']))
            story.append(Spacer(1, 0.08 * inch))

        story.append(PageBreak())
        return story

    # ── Analyst Q&A sections ───────────────────────────────────────────────────

    def _analyst_sections(self) -> list:
        _SECTIONS = [
            ("Product Intelligence",
             "Synthesis of how AI systems describe and position products in this "
             "category — features, comparisons, and purchase-driving attributes."),
            ("Consumer Personas",
             "AI-identified consumer segments most likely to research and purchase "
             "generators — their needs, priorities, and decision factors."),
            ("Buying Journey",
             "How AI models describe the stages a buyer goes through, from initial "
             "awareness through purchase and post-purchase support."),
        ]

        by_analyst: dict[str, list[tuple[str, str]]] = {}
        for analyst_name, prompt, response, _ in self.results:
            by_analyst.setdefault(analyst_name, []).append((prompt, response))

        story = []
        for section_name, intro in _SECTIONS:
            pairs = by_analyst.get(section_name, [])
            if not pairs:
                continue

            story.append(Paragraph(section_name, self._styles['H1']))
            story.append(Spacer(1, 0.06 * inch))
            story.append(Paragraph(intro, self._styles['Body']))
            story.append(Spacer(1, 0.14 * inch))

            for prompt, response in pairs:
                block = [
                    Paragraph(_pdf_safe(prompt), self._styles['QPrompt']),
                    Spacer(1, 0.04 * inch),
                    Paragraph(_pdf_safe(response) or "(no response)", self._styles['QResponse']),
                    Spacer(1, 0.18 * inch),
                ]
                story.append(KeepTogether(block[:2]))
                story.extend(block[2:])

            story.append(PageBreak())

        return story

    # ── Strategic Opportunities ────────────────────────────────────────────────

    def _opportunities_section(self) -> list:
        opps = self.opportunities
        if not opps:
            return []

        s = self._styles
        tb = self.target_brand

        story = [
            Paragraph("Strategic Opportunities", s['H1']),
            Spacer(1, 0.06 * inch),
            Paragraph(
                f"The following opportunities were identified through AI analysis of how "
                f"{tb} and competitors are described across consumer research scenarios. "
                "Each represents an area where improved content, positioning, or product "
                "strategy could meaningfully increase AI visibility.",
                s['Body'],
            ),
            Spacer(1, 0.14 * inch),
        ]

        _STATUS_COLORS = {
            "new":         C_GRAY,
            "in_progress": C_AMBER,
            "done":        C_GREEN,
        }

        for idx, (opp_id, title, evidence, description, status) in enumerate(opps, 1):
            status_color = _STATUS_COLORS.get(status or "new", C_GRAY)
            status_label = (status or "new").replace("_", " ").title()

            header_data = [[
                Paragraph(_pdf_safe(f"{idx}.  {title}"), s['OppTitle']),
                Paragraph(status_label, s['OppStatus']),
            ]]
            header_tbl = Table(header_data,
                               colWidths=[CONTENT_W - 1.1 * inch, 1.1 * inch])
            header_tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, -1), C_NAVY),
                ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING',    (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING',   (0, 0), (0, 0), 10),
                ('ALIGN',         (1, 0), (1, 0), 'RIGHT'),
                ('RIGHTPADDING',  (1, 0), (1, 0), 10),
            ]))

            body_rows = []
            if evidence:
                body_rows.append(["Evidence:", _pdf_safe(evidence)])
            if description:
                # "Action:" — matches the on-screen label (intelligence_page.py's
                # opportunity cards) for this same field. It previously said
                # "Description:" here, which didn't match the screen — the
                # underlying text is the LLM's ACTION + TACTICS output, so
                # "Action" is also the more accurate label of the two.
                body_rows.append(["Action:", _pdf_safe(description)])

            if body_rows:
                body_tbl = Table(body_rows,
                                 colWidths=[1.0 * inch, CONTENT_W - 1.0 * inch])
                body_tbl.setStyle(TableStyle([
                    ('BACKGROUND',    (0, 0), (-1, -1), C_BG),
                    ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE',      (0, 0), (0, -1), 7.5),
                    ('TEXTCOLOR',     (0, 0), (0, -1), C_GRAY),
                    ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE',      (1, 0), (1, -1), 8),
                    ('TEXTCOLOR',     (1, 0), (1, -1), C_DARK),
                    ('TOPPADDING',    (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING',   (0, 0), (0, -1), 10),
                    ('LEFTPADDING',   (1, 0), (1, -1), 6),
                    ('LINEBELOW',     (0, 0), (-1, -2), 0.25, C_LIGHT),
                    ('BOX',           (0, 0), (-1, -1), 0.5, C_LIGHT),
                ]))
                story.append(KeepTogether([header_tbl, body_tbl]))
            else:
                story.append(header_tbl)

            story.append(Spacer(1, 0.14 * inch))

        return story

    # ── Table helpers ──────────────────────────────────────────────────────────

    def _meta_table(self, rows):
        col_w = [1.8 * inch, CONTENT_W - 1.8 * inch]
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
            'QPrompt': ParagraphStyle(
                'QPrompt', fontName='Helvetica-Bold', fontSize=8.5,
                textColor=C_NAVY, leading=12, leftIndent=0,
            ),
            'QResponse': ParagraphStyle(
                'QResponse', fontName='Helvetica', fontSize=8,
                textColor=C_DARK, leading=11.5, leftIndent=12,
            ),
            'OppTitle': ParagraphStyle(
                'OppTitle', fontName='Helvetica-Bold', fontSize=9,
                textColor=white, leading=12,
            ),
            'OppStatus': ParagraphStyle(
                'OppStatus', fontName='Helvetica', fontSize=7.5,
                textColor=C_LIGHT, leading=11, alignment=2,
            ),
            'CoverLabel': ParagraphStyle(
                'CoverLabel', fontName='Helvetica-Bold', fontSize=11,
                textColor=C_BLUE, alignment=TA_LEFT, spaceAfter=2,
            ),
            'CoverTitle': ParagraphStyle(
                'CoverTitle', fontName='Helvetica-Bold', fontSize=28,
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
