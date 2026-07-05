"""
Tests for IntelligencePDFReport (#33) — the Intelligence PDF export had zero
coverage. Same documented tuple shapes and constructor as
IntelligenceDocxReport (see tests/test_intelligence_docx_report.py) — this
file mirrors that one's fixtures and edge cases, just verifying via
pypdf-extracted text instead of python-docx paragraphs.
"""
from pypdf import PdfReader

from backend.reports.intelligence_pdf_report import IntelligencePDFReport

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
]


def _extract_text(path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_generate_produces_valid_pdf_with_all_sections(tmp_path):
    out = tmp_path / "report.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, _RESULTS, _OPPORTUNITIES, "Firman").generate(str(out))

    assert out.exists() and out.stat().st_size > 0
    text = _extract_text(out)
    assert "Firman" in text
    assert "Executive Briefing" in text or "This is the executive briefing" in text
    assert "Product Intelligence" in text
    assert "Improve Amazon presence" in text


def test_analyst_result_with_unrecognized_name_is_silently_dropped(tmp_path):
    """Same real, current limitation confirmed in the DOCX report —
    _analyst_sections only recognizes the 3 known bucket names."""
    results = _RESULTS + [
        ("Brand Intelligence", "How is the brand perceived?", "Generally positive.", "2026-07-01T10:00:15"),
    ]
    out = tmp_path / "dropped.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, results, [], "Firman").generate(str(out))
    text = _extract_text(out)

    assert "Generally positive." not in text
    assert "Dual fuel and inverter tech." in text


def test_missing_briefing_and_opportunities_does_not_crash(tmp_path):
    empty_briefing = ("", "", "", "", "", "")
    out = tmp_path / "sparse.pdf"
    IntelligencePDFReport(_RUN, empty_briefing, _RESULTS, [], "Firman").generate(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_generate_does_not_crash_with_all_empty_inputs(tmp_path):
    out = tmp_path / "empty.pdf"
    IntelligencePDFReport(run=None, briefing=None, results=None, opportunities=None).generate(str(out))
    assert out.exists() and out.stat().st_size > 0
    assert "Target Brand" in _extract_text(out)
