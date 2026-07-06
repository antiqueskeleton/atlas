"""
Splits Executive Briefing text into (header, body) sections.

The briefing prompt (_BRIEFING_PROMPT_TEMPLATE in intelligence_service.py)
deliberately forbids markdown and instead asks for "plain section headers
(all-caps on their own line)" — VISIBILITY SNAPSHOT, WHAT AI MODELS SAY
ABOUT {target_brand}, SENTIMENT, KEY CONSUMER SEGMENTS, BUYING JOURNEY
INSIGHTS, GAPS AND RISKS, RECOMMENDED ACTIONS — but nothing gave those
headers any visual distinction from the body text that follows, so a
correctly-formatted briefing still read as one dense wall of text with no
way to tell where one section ends and the next begins at a glance.

Confirmed against real stored briefing text: each section is exactly
"HEADER LINE\\nBody text..." with sections separated by a blank line, so
the header is simply each block's first line — no need to hardcode the
specific section names (robust to the prompt's section list ever changing,
and to the target-brand-name casing varying, since real output has been
observed rendering it as both "Firman" and "FIRMAN").
"""


def split_briefing_sections(text: str) -> list[tuple[str, str]]:
    """Returns [(header, body), ...]. header is "" for a block with no
    newline at all (kept, not dropped, so nothing is silently lost if a
    real briefing ever omits a header for one section)."""
    if not text:
        return []

    sections: list[tuple[str, str]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if "\n" in block:
            header, body = block.split("\n", 1)
            sections.append((header.strip(), body.strip()))
        else:
            sections.append(("", block))
    return sections
