"""
Minimal block-level markdown parser for AI-generated response text.

Neither reportlab (PDF) nor python-docx have any built-in markdown support
(unlike Qt's QTextEdit.setMarkdown(), used for the on-screen equivalent) —
without this, response text got passed straight into a single Paragraph
call, which collapses ALL whitespace including newlines (the same behavior
as HTML), destroying not just the "##"/"**" syntax (shown as literal
symbols) but the actual paragraph/heading/list/table structure underneath
it — confirmed by checking real stored response text directly, which does
have well-formed markdown with real newlines between blocks; the "wall of
run-on text" appearance was an artifact of Paragraph()'s whitespace
collapsing, not a property of the source data.

Deliberately NOT a general CommonMark implementation — a lean, line-based
parser matching the specific, fairly consistent subset real AI responses in
this app actually use: headers, **bold**, bullet/numbered lists, pipe
tables, and horizontal rules. Produces a renderer-agnostic list of typed
blocks; backend/reports/pdf_blocks.py and docx_blocks.py each render this
same block list into their own flowables/document elements.
"""
import re

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_HR_RE = re.compile(r'^(-{3,}|\*{3,})\s*$')
_BULLET_RE = re.compile(r'^\s*[-*]\s+(.*)$')
_NUMBERED_RE = re.compile(r'^\s*\d+\.\s+(.*)$')
_TABLE_ROW_RE = re.compile(r'^\s*\|(.+)\|\s*$')
# A separator row contains only -, :, |, and whitespace, and at least one dash
# (distinguishes "|---|---|" from a data row that happens to start/end with |).
_TABLE_SEP_RE = re.compile(r'^\s*\|?[\s:|-]+\|?\s*$')

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')


def parse_inline_runs(text: str) -> list[tuple[str, bool]]:
    """Split on **bold** markers into [(text, is_bold), ...]. Anything not
    inside ** markers is a plain (non-bold) run."""
    runs: list[tuple[str, bool]] = []
    pos = 0
    for m in _BOLD_RE.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], False))
        runs.append((m.group(1), True))
        pos = m.end()
    if pos < len(text) or not runs:
        runs.append((text[pos:], False))
    return runs


def parse_markdown_blocks(text: str) -> list[dict]:
    """
    Returns a list of blocks, each one of:
      {"type": "heading", "level": 1-6, "runs": [(text, is_bold), ...]}
      {"type": "paragraph", "runs": [...]}
      {"type": "bullet_list", "items": [[(text, is_bold), ...], ...]}
      {"type": "numbered_list", "items": [[...], ...]}
      {"type": "table", "header": [str, ...], "rows": [[str, ...], ...]}
      {"type": "hr"}
    """
    if not text:
        return []

    lines = text.split("\n")
    blocks: list[dict] = []
    paragraph_lines: list[str] = []

    def flush_paragraph():
        if paragraph_lines:
            joined = " ".join(paragraph_lines)
            blocks.append({"type": "paragraph", "runs": parse_inline_runs(joined)})
            paragraph_lines.clear()

    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        m = _HEADING_RE.match(stripped)
        if m:
            flush_paragraph()
            blocks.append({
                "type": "heading",
                "level": len(m.group(1)),
                "runs": parse_inline_runs(m.group(2).strip()),
            })
            i += 1
            continue

        if _HR_RE.match(stripped):
            flush_paragraph()
            blocks.append({"type": "hr"})
            i += 1
            continue

        if (_TABLE_ROW_RE.match(stripped) and i + 1 < n
                and _TABLE_SEP_RE.match(lines[i + 1].strip())
                and "-" in lines[i + 1]):
            flush_paragraph()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header row + separator row
            rows = []
            while i < n and _TABLE_ROW_RE.match(lines[i].strip()):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows})
            continue

        m = _BULLET_RE.match(lines[i])
        if m:
            flush_paragraph()
            items = [parse_inline_runs(m.group(1).strip())]
            i += 1
            while i < n and _BULLET_RE.match(lines[i]):
                items.append(parse_inline_runs(_BULLET_RE.match(lines[i]).group(1).strip()))
                i += 1
            blocks.append({"type": "bullet_list", "items": items})
            continue

        m = _NUMBERED_RE.match(lines[i])
        if m:
            flush_paragraph()
            items = [parse_inline_runs(m.group(1).strip())]
            i += 1
            while i < n and _NUMBERED_RE.match(lines[i]):
                items.append(parse_inline_runs(_NUMBERED_RE.match(lines[i]).group(1).strip()))
                i += 1
            blocks.append({"type": "numbered_list", "items": items})
            continue

        paragraph_lines.append(stripped)
        i += 1

    flush_paragraph()
    return blocks
