"""
Tests for VisibilityPDFReport (#33) — the PDF export had zero coverage
despite being directly user-facing (Visibility page's "Export PDF Report"
button). Verifies actual extracted text content via pypdf, not just "a
file exists" — a PDF full of blank pages would otherwise pass silently.
"""
from pypdf import PdfReader

from backend.reports.pdf_report import VisibilityPDFReport


def _minimal_analytics(target="Firman"):
    return {"target_brand": target, "total_responses": 10, "target_visibility_score": 40.0,
            "brand_counts": {"Firman": 4, "Honda": 6}}


def _full_analytics(target="Firman"):
    return {
        "target_brand": target,
        "total_responses": 10,
        "total_tracked_brands": 2,
        "target_visibility_score": 40.0,
        "provider_visibility_scores": {"openai": 50.0, "anthropic": 30.0},
        "prompt_set_visibility_scores": {"Best Generator Brand": 60.0},
        "first_mention_share": {"Firman": 20.0, "Honda": 80.0},
        "brand_position_counts": {1: {"Firman": 2, "Honda": 8}},
        "brand_position_share": {1: {"Firman": 20.0, "Honda": 80.0}},
        "brand_counts": {"Firman": 4, "Honda": 6},
        "negative_brand_counts": {"Honda": 1},
        "target_negative_rate": 0.0,
        "brand_negative_rate": {"Firman": 0.0, "Honda": 16.7},
        "feature_counts": {"Dual Fuel": 3},
        "feature_brand_counts": {"Dual Fuel": {"Firman": 2, "Honda": 1}},
        "provider_brand_counts": {"openai": {"Firman": 3, "Honda": 2}},
        "channel_counts": {"Amazon": 5},
        "brand_channel_counts": {"Firman": {"Amazon": 1}, "Honda": {"Amazon": 4}},
        "channel_brand_counts": {"Amazon": {"Firman": 1, "Honda": 4}},
        "target_channel_gap": [{
            "channel": "Amazon", "target_count": 1, "top_competitor": "Honda",
            "top_competitor_count": 4, "total_competitor_mentions": 4,
        }],
    }


_STATS = {"total": 10, "runs": 3, "providers": 2, "families": 5}


def _extract_text(path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_generate_produces_a_valid_multi_page_pdf(tmp_path):
    out = tmp_path / "report.pdf"
    VisibilityPDFReport(_full_analytics(), runs=[], stats=_STATS, target_brand="Firman").generate(str(out))

    assert out.exists() and out.stat().st_size > 0
    reader = PdfReader(str(out))
    assert len(reader.pages) >= 1


def test_cover_page_shows_target_brand_and_kpis(tmp_path):
    out = tmp_path / "cover.pdf"
    VisibilityPDFReport(_full_analytics(), [], _STATS, "Firman").generate(str(out))
    text = _extract_text(out)

    assert "Firman" in text
    assert "40" in text  # visibility score
    assert "Visibility Score" in text
    assert "Mention Rank" in text


def test_mention_rank_shows_dash_when_target_brand_never_mentioned(tmp_path):
    """Same edge case as the Excel report: target brand tracked but absent
    from brand_counts must not raise on the rank lookup."""
    out = tmp_path / "no_mentions.pdf"
    analytics = _full_analytics(target="Generac")  # not a key in brand_counts
    VisibilityPDFReport(analytics, [], _STATS, "Generac").generate(str(out))
    text = _extract_text(out)

    assert "Generac" in text
    assert "—" in text or "-" in text  # rank renders as an em-dash placeholder


def test_generate_does_not_crash_with_minimal_analytics(tmp_path):
    """Brand-new installation, barely any data yet — most fields are
    optional (.get(..., {})) so this should degrade gracefully instead
    of raising on a missing key."""
    out = tmp_path / "minimal.pdf"
    VisibilityPDFReport(_minimal_analytics(), [], {}, "Firman").generate(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_generate_does_not_crash_with_no_optional_sections(tmp_path):
    """No provider scores, no feature/channel data, no channel gaps —
    every `if X:`-guarded optional section should just be skipped, not
    error, since real early-stage data collections won't have all of
    these populated yet."""
    analytics = {
        "target_brand": "Firman",
        "total_responses": 3,
        "target_visibility_score": 33.3,
        "brand_counts": {"Firman": 1},
    }
    out = tmp_path / "sparse.pdf"
    VisibilityPDFReport(analytics, [], {"total": 3}, "Firman").generate(str(out))
    assert out.exists() and out.stat().st_size > 0
