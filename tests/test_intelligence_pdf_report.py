"""
Tests for IntelligencePDFReport (#33) — the Intelligence PDF export had zero
coverage. Same documented tuple shapes and constructor as
IntelligenceDocxReport (see tests/test_intelligence_docx_report.py) — this
file mirrors that one's fixtures and edge cases, just verifying via
pypdf-extracted text instead of python-docx paragraphs.
"""
import re

from pypdf import PdfReader

from backend.reports.intelligence_pdf_report import IntelligencePDFReport, _pdf_safe

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
    """Extracted page text with every whitespace run collapsed to one space.

    ReportLab line-wraps paragraphs, so a multi-word assertion such as
    "Showing 5 of 8" can straddle a wrap and fail purely because the
    surrounding copy changed length — not because the behaviour broke (this
    happened when the section intros were reworded for R7). Normalising keeps
    these assertions about CONTENT rather than incidental layout.
    """
    reader = PdfReader(str(path))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", raw)


def test_generate_produces_valid_pdf_with_all_sections(tmp_path):
    out = tmp_path / "report.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, _RESULTS, _OPPORTUNITIES, "Firman").generate(str(out))

    assert out.exists() and out.stat().st_size > 0
    text = _extract_text(out)
    assert "Firman" in text
    assert "Executive Briefing" in text or "This is the executive briefing" in text
    assert "Product Intelligence" in text
    assert "Improve Amazon presence" in text


def test_opportunity_tactics_render_as_a_split_labeled_list(tmp_path):
    """R5 Part 2: an opportunity's action text + 'Tactics:' bullet list used to
    be dumped into one raw-string table cell, which ReportLab won't wrap (text
    ran off the page) and won't format (bullets showed as literal dashes). It
    now splits into Evidence / Action / Tactics rows with the tactics rendered
    as a real markdown list."""
    opp = (1, "Gain AI Overview presence",
           "Firman appears in 0 of 5 Google AI Overview buying queries.",
           "Optimize web content for AI buying guides.\n\nTactics:\n"
           "- Publish SEO comparison pages.\n- Submit structured product data.",
           "new")
    out = tmp_path / "opp.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, [], [opp], "Firman",
                          full_export=True).generate(str(out))
    text = _extract_text(out)

    # the three labels are now distinct rows
    assert "Evidence:" in text and "Action:" in text and "Tactics:" in text
    # the action text and the tactics list are both present
    assert "Optimize web content for AI buying guides." in text
    assert "Publish SEO comparison pages." in text
    # the markdown bullet dash is NOT shown literally — it's a real bullet now
    # (this is the before/after distinguisher: the old raw-string cell kept the
    # leading "- ")
    assert "- Publish SEO comparison pages." not in text


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


def test_briefing_only_export_contains_briefing_but_no_analyst_content(tmp_path):
    """#85 (Export Briefing button): constructing the report with a real
    briefing but empty results/opportunities must yield a standalone
    executive-briefing document — briefing text present, analyst Q&A and
    opportunity content absent."""
    out = tmp_path / "briefing_only.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, [], [], "Firman").generate(str(out))

    text = _extract_text(out)
    assert "This is the executive briefing" in text
    assert "Dual fuel and inverter tech." not in text
    assert "Improve Amazon presence" not in text


def test_generate_does_not_crash_with_all_empty_inputs(tmp_path):
    out = tmp_path / "empty.pdf"
    IntelligencePDFReport(run=None, briefing=None, results=None, opportunities=None).generate(str(out))
    assert out.exists() and out.stat().st_size > 0
    assert "Target Brand" in _extract_text(out)


# ── Regression: opportunity label must match the screen (intelligence_page.py
# labels this field "Action", not "Description") ──────────────────────────────

def test_opportunity_section_labels_field_action_not_description(tmp_path):
    out = tmp_path / "labels.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, _RESULTS, _OPPORTUNITIES, "Firman").generate(str(out))
    text = _extract_text(out)
    assert "Action:" in text
    assert "Description:" not in text


# ── Regression: emoji in AI response text must not render as broken glyph
# boxes (reportlab's Helvetica has no emoji support) ──────────────────────────

def test_pdf_safe_strips_emoji_but_keeps_normal_punctuation():
    text = "Portable Generator — Best For: ✅ High power needs, “quoted” text"
    safe = _pdf_safe(text)
    assert "✅" not in safe
    assert "—" in safe  # em dash is in WinAnsiEncoding, must survive
    assert "quoted" in safe


def test_generate_strips_emoji_from_analyst_responses(tmp_path):
    results = [
        ("Product Intelligence", "Best for tailgating?",
         "✅ Great for tailgating\n✅ Quiet operation", "2026-07-01T10:00:05"),
    ]
    out = tmp_path / "emoji.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, results, [], "Firman").generate(str(out))
    text = _extract_text(out)
    assert "■" not in text  # the broken-glyph box character
    assert "Great for tailgating" in text


# ── Caps + ranking (#81 continuation) ─────────────────────────────────────────

def test_analyst_section_caps_qa_pairs_shown_with_a_note(tmp_path):
    results = [
        ("Product Intelligence", f"Question {i}?", f"Response body {i}.", "2026-07-01T10:00:00")
        for i in range(8)
    ]
    out = tmp_path / "capped.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, results, [], "Firman").generate(str(out))
    text = _extract_text(out)

    assert "Showing 5 of 8" in text
    for i in range(5):
        assert f"Question {i}?" in text
    for i in range(5, 8):
        assert f"Question {i}?" not in text


def test_analyst_section_shows_no_cap_note_when_under_the_limit(tmp_path):
    out = tmp_path / "uncapped.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, _RESULTS, [], "Firman").generate(str(out))
    text = _extract_text(out)
    assert "Showing" not in text


def test_full_export_disables_qa_pair_cap(tmp_path):
    results = [
        ("Product Intelligence", f"Question {i}?", f"Response body {i}.", "2026-07-01T10:00:00")
        for i in range(8)
    ]
    out = tmp_path / "full.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, results, [], "Firman", full_export=True).generate(str(out))
    text = _extract_text(out)

    assert "Showing" not in text
    for i in range(8):
        assert f"Question {i}?" in text


def test_full_export_disables_opportunities_cap(tmp_path):
    opps = [(i, f"Opp {i}", f"{i} of 20 responses", f"Action {i}", "new") for i in range(15)]
    out = tmp_path / "full_opps.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, [], opps, "Firman", full_export=True).generate(str(out))
    text = _extract_text(out)

    assert "Showing the top" not in text
    for i in range(15):
        assert f"Opp {i}" in text


def test_opportunities_with_trailing_created_date_column_dont_crash(tmp_path):
    """Pinned to a real crash: get_all_opportunities() (used by the
    Opportunities tab's "Export Tab (Full)" button) returns a 6th
    created_date column that get_opportunities_for_run() doesn't have —
    "too many values to unpack (expected 5, got 6)" on real export."""
    opps = [(i, f"Opp {i}", f"{i} of 20 responses", f"Action {i}", "new",
              "2026-07-01T10:00:00") for i in range(3)]
    out = tmp_path / "full_opps_6col.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, [], opps, "Firman", full_export=True).generate(str(out))
    text = _extract_text(out)
    for i in range(3):
        assert f"Opp {i}" in text


def test_executive_briefing_sections_get_distinct_header_styling(tmp_path):
    briefing = (
        "product summary", "persona summary", "journey summary", "opportunities text",
        "VISIBILITY SNAPSHOT  \nFirman appeared in 12 of 84 responses.\n\n"
        "SENTIMENT  \nOut of 12 mentions, 4 were negative.",
        "2026-07-01T10:00:26",
    )
    out = tmp_path / "briefing_sections.pdf"
    IntelligencePDFReport(_RUN, briefing, [], [], "Firman").generate(str(out))
    text = _extract_text(out)

    assert "VISIBILITY SNAPSHOT" in text
    assert "Firman appeared in 12 of 84 responses." in text
    assert "SENTIMENT" in text
    assert "Out of 12 mentions, 4 were negative." in text


def test_opportunities_section_is_ranked_and_capped(tmp_path):
    opps = [
        (1, "Qualitative gap", "Champion and Honda have thousands of reviews.", "Action A", "new"),
        (2, "Complete absence", "Firman is not mentioned (0 of 84 responses).", "Action B", "new"),
    ] + [
        (i, f"Filler {i}", "No count here.", f"Action {i}", "new") for i in range(3, 13)
    ]
    out = tmp_path / "ranked_opps.pdf"
    IntelligencePDFReport(_RUN, _BRIEFING, [], opps, "Firman").generate(str(out))
    text = _extract_text(out)

    assert "Showing the top 10 of 12" in text
    assert "1." in text  # "Complete absence" should rank #1 (0/84 ratio)
    assert "Complete absence" in text
    idx_complete = text.index("Complete absence")
    idx_qualitative = text.index("Qualitative gap")
    assert idx_complete < idx_qualitative  # ranked above the qualitative one
