"""
Tests for IntelligenceDocxReport (#33) — the Word export had zero coverage
despite being directly user-facing (Intelligence page's "Export Word"
button). Tuple shapes match the module's own documented format (run,
briefing, results, opportunities) rather than guessing.
"""
from docx import Document

from backend.reports.intelligence_docx_report import IntelligenceDocxReport


def _all_paragraph_text(doc: Document) -> str:
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _heading_texts(doc: Document) -> list:
    return [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]


_RUN = ("run-1", "openai", "gpt-4.1-mini", "Firman", "2026-07-01T10:00:00", None, None, 26.4)
_BRIEFING = ("product summary", "persona summary", "journey summary",
             "opportunities text", "This is the executive briefing.\n\nSecond paragraph.",
             "2026-07-01T10:00:26")
_RESULTS = [
    ("Product Intelligence", "What features matter?", "Dual fuel and inverter tech.", "2026-07-01T10:00:05"),
    ("Consumer Personas", "Who buys generators?", "Homeowners and contractors.", "2026-07-01T10:00:10"),
]
_OPPORTUNITIES = [
    (1, "Improve Amazon presence", "Firman has fewer reviews than Honda", "Increase review volume", "new"),
    (2, "Fix spec accuracy", "AI cites wrong running watts", "Update product feed", "in_progress"),
]


def test_generate_produces_valid_docx_with_all_sections(tmp_path):
    out = tmp_path / "report.docx"
    IntelligenceDocxReport(
        run=_RUN, briefing=_BRIEFING, results=_RESULTS,
        opportunities=_OPPORTUNITIES, target_brand="Firman",
    ).generate(str(out))

    assert out.exists() and out.stat().st_size > 0
    doc = Document(str(out))
    headings = _heading_texts(doc)
    assert "Executive Briefing" in headings
    assert "Product Intelligence" in headings
    assert "Consumer Personas" in headings
    assert "Strategic Opportunities" in headings


def test_cover_page_shows_run_metadata(tmp_path):
    out = tmp_path / "cover.docx"
    IntelligenceDocxReport(_RUN, _BRIEFING, _RESULTS, _OPPORTUNITIES, "Firman").generate(str(out))
    text = _all_paragraph_text(Document(str(out)))

    assert "Firman" in text
    assert "Openai" in text  # provider.capitalize()
    assert "gpt-4.1-mini" in text
    assert "26s" in text  # duration formatted as f"{duration:.0f}s"
    assert "2" in text  # analyst response count / opportunities count


def test_analyst_result_with_unrecognized_name_is_silently_dropped(tmp_path):
    """Current, real behavior: _write_analyst_sections only recognizes
    exactly 'Product Intelligence'/'Consumer Personas'/'Buying Journey'
    (confirmed these match intelligence_service.py's actual bucket names).
    A result tagged with anything else — e.g. a typo, or a name from a
    future new analyst bucket that isn't wired into this report yet —
    is silently excluded rather than raising or showing an 'Other'
    section. Pinning this so it's a known, intentional limitation, not
    a silent data-loss surprise if it's ever hit in practice."""
    results = _RESULTS + [
        ("Brand Intelligence", "How is the brand perceived?", "Generally positive.", "2026-07-01T10:00:15"),
    ]
    out = tmp_path / "dropped.docx"
    IntelligenceDocxReport(_RUN, _BRIEFING, results, [], "Firman").generate(str(out))
    text = _all_paragraph_text(Document(str(out)))

    assert "Generally positive." not in text
    assert "Dual fuel and inverter tech." in text  # the recognized ones still appear


def test_opportunity_status_labels_render_correctly(tmp_path):
    out = tmp_path / "opps.docx"
    IntelligenceDocxReport(_RUN, _BRIEFING, [], _OPPORTUNITIES, "Firman").generate(str(out))
    text = _all_paragraph_text(Document(str(out)))

    assert "New" in text
    assert "In Progress" in text
    assert "Improve Amazon presence" in text
    assert "Fix spec accuracy" in text


def test_opportunity_section_labels_field_action_not_description(tmp_path):
    """Regression: this field was labeled "Description" here but "Action" on
    the Intelligence page's opportunity cards — same underlying data, two
    different labels depending on where you looked."""
    out = tmp_path / "labels.docx"
    IntelligenceDocxReport(_RUN, _BRIEFING, [], _OPPORTUNITIES, "Firman").generate(str(out))
    text = _all_paragraph_text(Document(str(out)))

    assert "Action" in text
    assert "Description" not in text


def test_missing_briefing_text_skips_section_without_crashing(tmp_path):
    empty_briefing = ("", "", "", "", "", "")  # executive_briefing (index 4) blank
    out = tmp_path / "no_briefing.docx"
    IntelligenceDocxReport(_RUN, empty_briefing, _RESULTS, [], "Firman").generate(str(out))

    doc = Document(str(out))
    assert "Executive Briefing" not in _heading_texts(doc)


def test_empty_opportunities_skips_section_without_crashing(tmp_path):
    out = tmp_path / "no_opps.docx"
    IntelligenceDocxReport(_RUN, _BRIEFING, _RESULTS, [], "Firman").generate(str(out))

    doc = Document(str(out))
    assert "Strategic Opportunities" not in _heading_texts(doc)


def test_generate_does_not_crash_with_all_empty_inputs(tmp_path):
    """No run yet (e.g. report requested before any Intelligence Analysis
    has ever completed) — every field falls back to its documented
    default (run=(), briefing=(), results=[], opportunities=[])."""
    out = tmp_path / "empty.docx"
    IntelligenceDocxReport(run=None, briefing=None, results=None, opportunities=None).generate(str(out))
    assert out.exists() and out.stat().st_size > 0

    text = _all_paragraph_text(Document(str(out)))
    assert "Target Brand" in text  # falls back to the literal default label
