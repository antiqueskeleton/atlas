"""
API usage metering (R9). A module-level, OPT-IN recorder: the app enables it
at startup (AtlasApplication) so real runs log usage, while unit tests never
enable it — so constructing a provider in a test writes nothing, keeping the
real database clean (the verification-isolation rule). Every function here
swallows its own errors: usage metering is bookkeeping and must NEVER break
or measurably slow a provider call.

Cost is ESTIMATED from published per-model list prices (USD per 1M tokens) and
covers Atlas-tracked calls only — it is not the user's real billed spend (no
provider exposes that via API). A model with no known rate yields NULL cost
(an honest "—" in the UI), never a guessed number.
"""
from backend.usage.usage_repository import UsageRepository

_recorder = None   # a UsageRepository once enabled, else None -> no-op

# USD per 1,000,000 tokens as (input_rate, output_rate). Best-effort published
# list prices as of mid-2026; substring-matched LONGEST-KEY-FIRST so
# "gpt-4.1-mini" beats "gpt-4.1". Rates drift and the UI says the totals are an
# estimate. Add a model here to light up its cost column; omit it and cost
# shows "—" (never a fabricated figure).
_RATES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "o4-mini": (1.10, 4.40),
    "claude-opus": (15.00, 75.00),
    "claude-sonnet": (3.00, 15.00),
    "claude-haiku": (0.80, 4.00),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-chat": (0.27, 1.10),
    "mistral-large": (2.00, 6.00),
    "mistral-small": (0.20, 0.60),
    "command-a": (2.50, 10.00),
    "command-r-plus": (2.50, 10.00),
    "command-r": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "sonar-pro": (3.00, 15.00),
    "sonar": (1.00, 1.00),
    "grok": (2.00, 10.00),
}


def enable_recording(repository=None):
    """Turn metering on. Called once by AtlasApplication at startup; safe to
    pass a repository in tests. A failure to open the DB leaves metering off
    rather than raising."""
    global _recorder
    try:
        _recorder = repository or UsageRepository()
    except Exception:
        _recorder = None


def disable_recording():
    global _recorder
    _recorder = None


def is_enabled() -> bool:
    return _recorder is not None


def _num(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def estimate_cost(model, input_tokens, output_tokens):
    """USD estimate for one call, or None when the model has no known rate.
    The longest matching rate key wins so specific variants beat base names."""
    if not model:
        return None
    m = model.lower()
    for key in sorted(_RATES, key=len, reverse=True):
        if key in m:
            in_rate, out_rate = _RATES[key]
            return round((_num(input_tokens) / 1_000_000) * in_rate
                         + (_num(output_tokens) / 1_000_000) * out_rate, 6)
    return None


def extract_usage(response):
    """
    Best-effort (input_tokens, output_tokens) from any provider SDK response.
    Handles the OpenAI Responses API (input/output_tokens on .usage), Chat
    Completions (prompt/completion_tokens), Anthropic (input/output_tokens),
    Cohere v2 (.usage.tokens.*), and Gemini (.usage_metadata.*). Returns
    (0, 0) when nothing is found — never raises.
    """
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens = getattr(usage, "tokens", None)   # Cohere v2 nests here
            src = tokens if tokens is not None else usage
            in_tok = (_num(getattr(src, "input_tokens", None))
                      or _num(getattr(src, "prompt_tokens", None)))
            out_tok = (_num(getattr(src, "output_tokens", None))
                       or _num(getattr(src, "completion_tokens", None)))
            if in_tok or out_tok:
                return in_tok, out_tok
        meta = getattr(response, "usage_metadata", None)   # Gemini
        if meta is not None:
            return (_num(getattr(meta, "prompt_token_count", None)),
                    _num(getattr(meta, "candidates_token_count", None)))
    except Exception:
        pass
    return 0, 0


def record_usage(provider, model, response):
    """Log one API call's usage + estimated cost when metering is enabled;
    a no-op (and fully error-swallowing) otherwise, so it is always safe to
    call from a provider's hot path and harmless in tests."""
    if _recorder is None:
        return
    try:
        in_tok, out_tok = extract_usage(response)
        _recorder.record(provider, model, in_tok, out_tok,
                         estimate_cost(model, in_tok, out_tok))
    except Exception:
        pass


def month_to_date(now=None) -> list[dict]:
    if _recorder is None:
        return []
    try:
        return _recorder.month_to_date(now=now)
    except Exception:
        return []
