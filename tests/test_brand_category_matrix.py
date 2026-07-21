"""Brand x family matrix (#69) — pure aggregation, injected detectors."""
from backend.visibility.brand_category_matrix import build_matrix


def _row(rid, family, text):
    return (rid, "run", "OpenAI", "gpt", "prompt", text, "2026-07-20", family)


def _detect(text):
    return [b for b in ("Firman", "Honda") if b.lower() in text.lower()]


def _single(label):
    return bool(label) and "," not in label and label.lower() not in ("custom", "default")


def test_matrix_counts_and_orders():
    rows = [
        _row(1, "Best Inverter", "Honda wins here."),
        _row(2, "Best Inverter", "Honda again, Firman too."),
        _row(3, "Best Tri-Fuel", "Firman is solid."),
        _row(4, "Custom", "Honda everywhere."),           # aggregate -> excluded
        _row(5, "A, B", "Firman multi-family."),          # comma-joined -> excluded
    ]
    m = build_matrix(rows, _detect, _single)
    assert m["families"] == ["Best Inverter", "Best Tri-Fuel"]
    assert m["brands"][0] == "Honda"                       # 2 mentions vs 2 (tie -> stable by count)
    assert m["counts"][("Honda", "Best Inverter")] == 2
    assert m["counts"][("Firman", "Best Tri-Fuel")] == 1
    assert ("Honda", "Best Tri-Fuel") not in m["counts"]   # honest absence, no zero-fill
    assert m["totals"] == {"Best Inverter": 2, "Best Tri-Fuel": 1}


def test_matrix_empty_input():
    m = build_matrix([], _detect, _single)
    assert m == {"families": [], "brands": [], "counts": {}, "totals": {}}
