"""
Tests for backend/intelligence/opportunity_ranking.py (#81 continuation).

Evidence strings below are drawn directly from real opportunities in a
production database (see the module docstring) rather than invented toy
examples, since the real distribution — mostly qualitative, a minority with
an explicit "X of Y" count — is exactly what motivated this design.
"""
from backend.intelligence.opportunity_ranking import _extract_ratio, rank_opportunities


def _opp(id_, title, evidence, created_date="2026-07-01"):
    return (id_, title, evidence, f"Action for {title}", "new", created_date)


def test_extract_ratio_parses_zero_of_n_as_zero():
    assert _extract_ratio(
        "Firman is not mentioned in top RV generator picks across 3 responses (0 of 84 responses)."
    ) == 0.0


def test_extract_ratio_parses_nonzero_of_n():
    assert _extract_ratio(
        '"Champion 3500W Dual Fuel" appears in 5 of 6 dual-fuel top picks.'
    ) == 5 / 6


def test_extract_ratio_returns_none_for_purely_qualitative_evidence():
    """Real example: no exact count anywhere in the sentence."""
    evidence = (
        "The data repeatedly cites Honda and Cummins as leaders in long-term "
        "reliability, with Firman noted for good value but less recognized "
        "for longevity. Customers prioritize reliability highly."
    )
    assert _extract_ratio(evidence) is None


def test_extract_ratio_returns_none_for_empty_evidence():
    assert _extract_ratio("") is None
    assert _extract_ratio(None) is None


def test_extract_ratio_ignores_zero_denominator():
    assert _extract_ratio("Firman appeared in 0 of 0 responses.") is None


def test_extract_ratio_finds_the_ratio_regardless_of_surrounding_punctuation():
    assert _extract_ratio(
        'Honda EU2200i" appears in 6 of 6 camping/RV generator top picks.'
    ) == 1.0


def test_rank_opportunities_puts_zero_ratio_evidence_first():
    opps = [
        _opp(1, "Qualitative gap", "Champion and Honda have thousands of reviews per model."),
        _opp(2, "Complete absence", "Firman is not mentioned (0 of 84 responses)."),
        _opp(3, "Partial gap", "Appears in 5 of 6 dual-fuel top picks."),
    ]
    ranked = rank_opportunities(opps)
    assert [o[0] for o in ranked] == [2, 3, 1]  # 0/84 first, then 5/6, then no-count


def test_rank_opportunities_preserves_recency_order_for_no_count_opportunities():
    """Opportunities with no parseable count keep their original (recency)
    relative order, rather than being arbitrarily reshuffled."""
    opps = [
        _opp(1, "Newest no-count", "Multiple responses emphasize sizing confusion."),
        _opp(2, "Middle no-count", "Consumers seek clear guidance on sizing."),
        _opp(3, "Oldest no-count", "Firman lacks strong presence in reviews."),
    ]
    ranked = rank_opportunities(opps)
    assert [o[0] for o in ranked] == [1, 2, 3]  # unchanged - none have a count


def test_rank_opportunities_handles_a_realistic_mixed_batch():
    """Mirrors the real distribution: 2 ratio-backed, 3 qualitative-only."""
    opps = [
        _opp(1, "A", "Firman is inferred to be in this category but not mentioned in top picks."),
        _opp(2, "B", "0 of 84 responses mention Firman as a top generator choice for RV camping."),
        _opp(3, "C", "Customer support is less emphasized compared to Honda and Generac."),
        _opp(4, "D", '"Champion 3500W Dual Fuel" appears in 5 of 6 dual-fuel top picks.'),
        _opp(5, "E", "Firman is known as a value brand but has fewer reviews comparatively."),
    ]
    ranked = rank_opportunities(opps)
    ranked_ids = [o[0] for o in ranked]

    # Both ratio-backed opportunities (2: 0/84, 4: 5/6) come before all 3
    # qualitative-only ones, and 2 (lower ratio) comes before 4.
    assert ranked_ids.index(2) < ranked_ids.index(4) < ranked_ids.index(1)
    assert ranked_ids[:2] == [2, 4]         # the ratio-backed pair, in ratio order
    assert ranked_ids[2:] == [1, 3, 5]      # the no-count ones, recency order preserved


def test_rank_opportunities_does_not_mutate_or_drop_rows():
    opps = [_opp(i, f"Title {i}", f"{i} of 10 responses") for i in range(5)]
    ranked = rank_opportunities(opps)
    assert len(ranked) == len(opps)
    assert set(o[0] for o in ranked) == set(o[0] for o in opps)


def test_rank_opportunities_handles_empty_list():
    assert rank_opportunities([]) == []
