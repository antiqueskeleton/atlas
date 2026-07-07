"""
Deterministic post-generation fact check for the Executive Briefing (#95).

The briefing prompt REQUIRES every claim to cite "X of Y" counts from the
supplied data and FORBIDS inventing numbers — but nothing verified
compliance. This module closes the loop: every "X of Y" pair in the
generated briefing is checked against the exact source blocks that were
fed to the model. Purely mechanical — regex pair extraction and set
membership — so the check itself cannot hallucinate. This is the
difference between "we asked the model not to invent numbers" and "we
checked".

A claim failing verification does NOT mean it's false — the model may
have legitimately derived it (e.g. summed two counts) — which is why the
UI surfaces unverified claims for human review instead of deleting them.
"""
import re

_PAIR_RE = re.compile(r"(\d[\d,]*)\s+(?:out\s+of|of)\s+(\d[\d,]*)")


def _iter_pairs(text: str):
    for match in _PAIR_RE.finditer(text or ""):
        try:
            x = int(match.group(1).replace(",", ""))
            y = int(match.group(2).replace(",", ""))
        except ValueError:
            continue
        yield x, y, match


def verify_briefing_numbers(briefing_text: str, source_texts: list[str]) -> dict:
    """
    Returns {"total_claims", "verified", "unverified": [{"claim",
    "context"}]} — where a claim is an "X of Y" pair in the briefing and it
    verifies when the identical pair appears in any source block.
    """
    source_pairs = {
        (x, y)
        for text in source_texts
        for x, y, _ in _iter_pairs(text)
    }

    total = 0
    unverified = []
    for x, y, match in _iter_pairs(briefing_text):
        total += 1
        if (x, y) not in source_pairs:
            start = max(0, match.start() - 45)
            context = " ".join(
                briefing_text[start:match.end() + 45].split())
            unverified.append({"claim": f"{x:,} of {y:,}", "context": context})

    return {
        "total_claims": total,
        "verified": total - len(unverified),
        "unverified": unverified,
    }
