"""
Renders parsed markdown blocks (markdown_blocks.py) into reportlab
Flowables — replaces dumping raw AI response text into one plain Paragraph,
which showed literal "##"/"**"/"|" syntax AND collapsed the response's real
paragraph/heading/list/table structure into a single wall of run-on text
(Paragraph collapses embedded newlines the same way HTML does).
"""
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, Spacer, Table, TableStyle,
)

from backend.reports.markdown_blocks import parse_inline_runs, parse_markdown_blocks

_HEADING_STYLE_KEY = {1: "h1", 2: "h2", 3: "h3", 4: "h4", 5: "h4", 6: "h4"}


def _escape_xml(text: str) -> str:
    """reportlab Paragraph text is a small XML-like markup language (used
    here to emit <b> tags for bold runs) — literal &/</> in the actual
    content must be escaped or they'd be misread as markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _runs_to_markup(runs, pdf_safe_fn) -> str:
    parts = []
    for text, is_bold in runs:
        safe = _escape_xml(pdf_safe_fn(text))
        parts.append(f"<b>{safe}</b>" if is_bold else safe)
    return "".join(parts)


def build_markdown_styles(base_color, heading_color) -> dict:
    # Spacing kept deliberately tight: a real analyst response bucket runs to
    # ~40 blocks and ~50 list items per response (measured against a real
    # 84-response run) -- even a couple points of spaceBefore/spaceAfter per
    # block compounds into many extra pages once multiplied out, so every
    # value here is the minimum that still visually separates elements.
    return {
        "h1": ParagraphStyle("MDH1", fontName="Helvetica-Bold", fontSize=10,
                             textColor=heading_color, leading=12, spaceBefore=4, spaceAfter=2),
        "h2": ParagraphStyle("MDH2", fontName="Helvetica-Bold", fontSize=9,
                             textColor=heading_color, leading=11, spaceBefore=3, spaceAfter=2),
        "h3": ParagraphStyle("MDH3", fontName="Helvetica-Bold", fontSize=8.5,
                             textColor=heading_color, leading=10.5, spaceBefore=2, spaceAfter=1),
        "h4": ParagraphStyle("MDH4", fontName="Helvetica-Bold", fontSize=8,
                             textColor=heading_color, leading=10, spaceBefore=2, spaceAfter=1),
        "body": ParagraphStyle("MDBody", fontName="Helvetica", fontSize=8,
                               textColor=base_color, leading=11, spaceAfter=2),
        "list_item": ParagraphStyle("MDListItem", fontName="Helvetica", fontSize=8,
                                    textColor=base_color, leading=10, spaceAfter=0),
        "table_header": ParagraphStyle("MDTableHeader", fontName="Helvetica-Bold", fontSize=7.5,
                                       textColor=HexColor("#FFFFFF"), leading=9),
        "table_cell": ParagraphStyle("MDTableCell", fontName="Helvetica", fontSize=7.5,
                                     textColor=base_color, leading=9),
    }


def render_markdown_to_flowables(
    text, styles, pdf_safe_fn, content_width,
    hr_color=HexColor("#D1D5DB"), table_header_bg=HexColor("#2D5A8E"),
):
    blocks = parse_markdown_blocks(text)
    flowables = []

    for block in blocks:
        btype = block["type"]

        if btype == "heading":
            style_key = _HEADING_STYLE_KEY.get(block["level"], "h4")
            markup = _runs_to_markup(block["runs"], pdf_safe_fn)
            if markup.strip():
                flowables.append(Paragraph(markup, styles[style_key]))

        elif btype == "paragraph":
            markup = _runs_to_markup(block["runs"], pdf_safe_fn)
            if markup.strip():
                flowables.append(Paragraph(markup, styles["body"]))

        elif btype == "hr":
            flowables.append(HRFlowable(width=content_width, thickness=0.5,
                                        color=hr_color, spaceBefore=2, spaceAfter=2))

        elif btype in ("bullet_list", "numbered_list"):
            items = []
            for item_runs in block["items"]:
                markup = _runs_to_markup(item_runs, pdf_safe_fn)
                if markup.strip():
                    items.append(ListItem(Paragraph(markup, styles["list_item"])))
            if items:
                bullet_type = "bullet" if btype == "bullet_list" else "1"
                flowables.append(ListFlowable(
                    items, bulletType=bullet_type, leftIndent=14, bulletFontSize=7.5,
                    spaceBefore=0, spaceAfter=2,
                ))

        elif btype == "table":
            header = block["header"]
            rows = block["rows"]
            if not header:
                continue
            n_cols = len(header)
            col_w = content_width / n_cols
            def _cell(c, style):
                # Table cells can contain **bold** too (e.g. "| **Use Case**
                # | **Best Pick** |") -- must run through the same inline-run
                # parser as everything else, not just escape+pdf_safe the
                # raw text (which left literal ** in header/cell text).
                return Paragraph(_runs_to_markup(parse_inline_runs(c), pdf_safe_fn), style)

            table_data = [[_cell(c, styles["table_header"]) for c in header]]
            for row in rows:
                # A malformed row with a different column count shouldn't
                # crash the whole report -- pad/truncate to the header width.
                padded = (row + [""] * n_cols)[:n_cols]
                table_data.append([_cell(c, styles["table_cell"]) for c in padded])
            tbl = Table(table_data, colWidths=[col_w] * n_cols)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), table_header_bg),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F3F4F6")]),
                ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            flowables.append(tbl)
            flowables.append(Spacer(1, 2))

    return flowables
