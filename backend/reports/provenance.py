"""
Provenance labelling (R7 Part A) — ONE source of truth for how Atlas marks
content it has not verified, so the PDF, DOCX and on-screen views can never
drift apart on the wording.

The Product Intelligence / Consumer Personas / Buying Journey sections
reproduce VERBATIM AI-model answers. They are evidence of what AI systems say
about this market — not Atlas findings — and they demonstrably contain factual
errors about real products: in a live 2026-07 run the models described the
Firman H08051 (a 74 dB, 226 lb SYNCHRONOUS open-frame unit) as a "quiet
inverter" at 72 dB, and invented Amazon links. Reproducing that unlabelled
invites a reader to take it as an Atlas recommendation, so every such block
carries the badge and note below.

Deliberately no emoji: the PDF's embedded font has no glyph for them (a
previous report bug), so the marker is bold capitalised text plus colour.
"""

UNVERIFIED_BADGE = "NOT FACT-CHECKED"

UNVERIFIED_NOTE = (
    "The responses below are reproduced exactly as the AI models answered. "
    "They show what AI systems tell buyers about this market — they are NOT "
    "Atlas findings and have NOT been verified. They can and do contain "
    "incorrect product claims. Atlas's own measured figures appear in the "
    "Executive Briefing, the KPI tiles and the data tables."
)

# The old wording described these blocks as though they were Atlas analysis
# ("Synthesis of how AI systems describe..."), which is exactly what made the
# unlabelled raw text read as a recommendation. They now say what the blocks
# actually are: captured evidence.
SECTION_INTROS = {
    "Product Intelligence":
        "Captured AI answers about products in this category — the features, "
        "comparisons and attributes models push buyers toward.",
    "Consumer Personas":
        "Captured AI answers describing who buys in this category and what "
        "those buyers prioritize.",
    "Buying Journey":
        "Captured AI answers describing the stages buyers move through, from "
        "awareness to post-purchase support.",
}


def unverified_line() -> str:
    """Single-line banner used wherever a full paragraph is too heavy."""
    return f"{UNVERIFIED_BADGE} — {UNVERIFIED_NOTE}"
