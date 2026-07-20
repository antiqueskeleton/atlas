"""
R7 Part A — provenance labelling. The Product/Personas/Journey blocks
reproduce VERBATIM AI output; these tests pin that every surface (PDF, DOCX,
on-screen) marks them unverified using the one shared source of truth, and
that the old "Synthesis of..." wording — which is what let raw model output
read as an Atlas recommendation — is gone for good.
"""
from backend.reports import provenance


def test_badge_and_note_say_not_verified_in_plain_language():
    assert provenance.UNVERIFIED_BADGE == "NOT FACT-CHECKED"
    note = provenance.UNVERIFIED_NOTE.lower()
    assert "not" in note and "verified" in note
    assert "verbatim" in note or "exactly as the ai models answered" in note
    # Must point the reader at where the trustworthy numbers actually live.
    assert "executive briefing" in note


def test_section_intros_describe_captured_evidence_not_atlas_synthesis():
    """The old intros claimed these blocks were Atlas 'synthesis'. That
    framing is the bug — they are captured model answers."""
    for name in ("Product Intelligence", "Consumer Personas", "Buying Journey"):
        intro = provenance.SECTION_INTROS[name]
        assert intro, f"{name} intro missing"
        assert "synthesis" not in intro.lower()
        assert "captured ai answers" in intro.lower()


def test_no_emoji_in_labels_pdf_font_has_no_glyphs():
    """A previous report bug: the PDF's embedded font renders emoji as tofu,
    so the marker must be text + colour only."""
    for text in (provenance.UNVERIFIED_BADGE, provenance.UNVERIFIED_NOTE,
                 *provenance.SECTION_INTROS.values()):
        assert all(ord(ch) < 0x2500 for ch in text), f"non-text glyph in: {text!r}"


def test_unverified_line_combines_badge_and_note():
    line = provenance.unverified_line()
    assert line.startswith(provenance.UNVERIFIED_BADGE)
    assert provenance.UNVERIFIED_NOTE in line


# ── The three surfaces all consume the shared constants ───────────────────────

def test_pdf_report_uses_shared_provenance_constants():
    import backend.reports.intelligence_pdf_report as pdf
    assert pdf.UNVERIFIED_BADGE is provenance.UNVERIFIED_BADGE
    assert pdf.SECTION_INTROS is provenance.SECTION_INTROS
    # the amber callout style the banner is drawn in must exist
    styles = pdf.IntelligencePDFReport.__dict__.get("_build_styles")
    assert styles is not None


def test_docx_report_uses_shared_provenance_constants():
    import backend.reports.intelligence_docx_report as docx
    assert docx.UNVERIFIED_BADGE is provenance.UNVERIFIED_BADGE
    assert docx.SECTION_INTROS is provenance.SECTION_INTROS


def test_intelligence_page_uses_shared_provenance_constants():
    import desktop.pages.intelligence_page as page
    assert page.UNVERIFIED_BADGE is provenance.UNVERIFIED_BADGE
    assert page.UNVERIFIED_NOTE is provenance.UNVERIFIED_NOTE


def test_old_synthesis_wording_is_gone_from_both_exporters():
    """Regression guard: if someone reinstates the 'Synthesis of how AI
    systems describe...' intro, unlabelled model output starts reading as an
    Atlas finding again."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("backend/reports/intelligence_pdf_report.py",
                "backend/reports/intelligence_docx_report.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "Synthesis of how AI systems describe" not in src, rel
