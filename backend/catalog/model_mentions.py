"""
Model-level AI visibility (#66) + deterministic spec-contradiction detection
(R4b), built on the verified Firman catalog.

Everything here is rule-based and auditable, matching negation.py /
recommendation.py's philosophy: a contradiction is only flagged when a
sentence names a specific Firman model AND makes a claim the first-party
catalog disproves. v1 deliberately checks only BINARY, low-false-positive
claims — generator type ("inverter") and fuel capability ("tri fuel",
"dual fuel") — the exact classes of the real H08051 hallucination ("quiet
inverter", "tri-fuel"). Wattage claims are NOT checked yet: running-vs-
starting-vs-per-fuel ambiguity makes numeric checks false-positive-prone.
"""
import re

from backend.visibility.clause_boundaries import SENTENCE_SPLIT

_INVERTER_CUE = re.compile(r"\binverter\b", re.IGNORECASE)
_TRI_FUEL_CUE = re.compile(r"\btri[- ]?fuel\b", re.IGNORECASE)
_DUAL_FUEL_CUE = re.compile(r"\bdual[- ]?fuel\b", re.IGNORECASE)


def _model_pattern(model: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(model) + r"\b", re.IGNORECASE)


def find_model_mentions(text: str, models: list[str]) -> set[str]:
    """Which catalog models a response names (word-boundary, case-insensitive).
    Cheap substring pre-filter first — the common case is zero mentions."""
    upper = (text or "").upper()
    return {m for m in models
            if m.upper() in upper and _model_pattern(m).search(text)}


def detect_spec_contradictions(text: str, product: dict) -> list[dict]:
    """Sentence-level claims about ONE model that its first-party catalog
    record disproves. Each finding carries the claim, the verified truth,
    and the offending sentence — auditable by inspection."""
    model = product.get("model", "")
    pattern = _model_pattern(model)
    gen_type = product.get("generator_type", "")
    fuels = product.get("fuel_types") or []
    findings = []
    for sentence in SENTENCE_SPLIT.split(text or ""):
        if not pattern.search(sentence):
            continue
        excerpt = sentence.strip()[:240]
        if _INVERTER_CUE.search(sentence) and gen_type != "Inverter":
            findings.append({
                "model": model, "claim": "inverter",
                "truth": f"{gen_type} (not an inverter)", "excerpt": excerpt})
        if _TRI_FUEL_CUE.search(sentence) and len(fuels) < 3:
            findings.append({
                "model": model, "claim": "tri-fuel",
                "truth": f"fuel: {'/'.join(fuels) or 'unknown'}", "excerpt": excerpt})
        if _DUAL_FUEL_CUE.search(sentence) and len(fuels) == 1:
            findings.append({
                "model": model, "claim": "dual-fuel",
                "truth": f"fuel: {fuels[0]} only", "excerpt": excerpt})
    return findings


def scan_responses(responses: list, products: list[dict]) -> dict:
    """Model-level rollup over stored visibility responses.
    `responses` rows: (id, run_id, provider, model, prompt, response, ...)
    — visibility_repository.list_responses() shape. Returns
    {model: {"mentions": int, "contradictions": [finding+provider, ...]}}
    for every catalog model (zero rows included, so 'never mentioned' is a
    visible fact, not an absence)."""
    by_model = {p["model"]: {"mentions": 0, "contradictions": []}
                for p in products}
    products_by_model = {p["model"]: p for p in products}
    model_names = list(by_model)
    for row in responses:
        text = row[5] or ""
        provider = row[2] or ""
        for model in find_model_mentions(text, model_names):
            entry = by_model[model]
            entry["mentions"] += 1
            for f in detect_spec_contradictions(text, products_by_model[model]):
                entry["contradictions"].append({**f, "provider": provider,
                                                "response_id": row[0]})
    return by_model
