"""
Brand x prompt-family visibility matrix (#69): every tracked brand's mention
rate per prompt family, side by side — the per-family computation the target
brand already had, extended to the whole field.

Rule-based single pass over stored responses using the SAME brand detection
the core pipeline uses (word-boundary matcher via detect_mentioned_brands),
so a cell here always agrees with the headline counts. Aggregate labels
("Custom", "Default", comma-joined multi-family runs) are excluded exactly
as trends_service excludes them — a mixed-family run can't attribute a
mention to one family honestly (R7: no guessed attribution).
"""


def build_matrix(responses: list, detect_mentioned_brands,
                 is_single_family_label) -> dict:
    """
    responses: visibility_repository.list_responses() rows
               (id, run_id, provider, model, prompt, response, collected_at,
                family_display).
    detect_mentioned_brands: VisibilityAnalytics.detect_mentioned_brands.
    is_single_family_label:  TrendsService._is_single_family_label.

    Returns {
      "families": [family, ...]     # by response volume desc
      "brands":   [brand, ...]      # by total mentions desc
      "counts":   {(brand, family): mentions}
      "totals":   {family: response_count}
    } — rates are counts/totals, computed by the caller so the raw counts
    stay visible (n= honesty, per R7).
    """
    counts: dict = {}
    totals: dict = {}
    brand_totals: dict = {}
    for row in responses:
        family = (row[7] if len(row) > 7 else "") or ""
        if not is_single_family_label(family):
            continue
        totals[family] = totals.get(family, 0) + 1
        for brand in detect_mentioned_brands(row[5] or ""):
            counts[(brand, family)] = counts.get((brand, family), 0) + 1
            brand_totals[brand] = brand_totals.get(brand, 0) + 1

    families = sorted(totals, key=lambda f: -totals[f])
    brands = sorted(brand_totals, key=lambda b: -brand_totals[b])
    return {"families": families, "brands": brands,
            "counts": counts, "totals": totals}
