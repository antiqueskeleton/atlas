"""
Tests for backend/reports/markdown_blocks.py.

Includes a case built directly from a real stored AI response (see the
module docstring for how it was confirmed the raw text has genuine
newline-separated structure, unlike what a reportlab Paragraph() dump of
the same text made it look like).
"""
from backend.reports.markdown_blocks import parse_inline_runs, parse_markdown_blocks

# ── Inline runs ────────────────────────────────────────────────────────────────

def test_parse_inline_runs_splits_bold_from_plain_text():
    runs = parse_inline_runs("The **quietest open-frame generators** available")
    assert runs == [
        ("The ", False),
        ("quietest open-frame generators", True),
        (" available", False),
    ]


def test_parse_inline_runs_with_no_bold_returns_one_plain_run():
    assert parse_inline_runs("plain text only") == [("plain text only", False)]


def test_parse_inline_runs_handles_multiple_bold_spans():
    runs = parse_inline_runs("**Noise Level:** 52-58 dB(A) **Wattage:** 7,000W")
    assert runs == [
        ("Noise Level:", True),
        (" 52-58 dB(A) ", False),
        ("Wattage:", True),
        (" 7,000W", False),
    ]


def test_parse_inline_runs_empty_string():
    assert parse_inline_runs("") == [("", False)]


# ── Block parsing ──────────────────────────────────────────────────────────────

def test_heading_levels_parsed_correctly():
    blocks = parse_markdown_blocks("### Quietest Open Frame Generators")
    assert blocks == [{
        "type": "heading", "level": 3,
        "runs": [("Quietest Open Frame Generators", False)],
    }]


def test_heading_with_bold_text():
    blocks = parse_markdown_blocks("## **Top Picks**")
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["level"] == 2
    assert blocks[0]["runs"] == [("Top Picks", True)]


def test_horizontal_rule_detected():
    blocks = parse_markdown_blocks("Some text\n\n---\n\nMore text")
    types = [b["type"] for b in blocks]
    assert types == ["paragraph", "hr", "paragraph"]


def test_bullet_list_groups_consecutive_items_into_one_block():
    text = (
        "- **Honda EU Series**: quiet\n"
        "- **Generac GP Series**: moderate\n"
        "- **Champion**: louder\n"
    )
    blocks = parse_markdown_blocks(text)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "bullet_list"
    assert len(blocks[0]["items"]) == 3
    assert blocks[0]["items"][0] == [("Honda EU Series", True), (": quiet", False)]


def test_numbered_list_groups_consecutive_items():
    text = (
        "1. **Decibel Rating (dB)**: lower is quieter.\n"
        "2. **Open Frame Design**: louder generally.\n"
    )
    blocks = parse_markdown_blocks(text)
    assert blocks[0]["type"] == "numbered_list"
    assert len(blocks[0]["items"]) == 2


def test_table_parses_header_and_data_rows_separately_from_separator():
    text = (
        "| Model | Noise | Price |\n"
        "|-------|-------|-------|\n"
        "| Honda EU7000is | 52-58 | $4,500 |\n"
        "| Generac 7175 | 57-65 | $2,500 |\n"
    )
    blocks = parse_markdown_blocks(text)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "table"
    assert blocks[0]["header"] == ["Model", "Noise", "Price"]
    assert blocks[0]["rows"] == [
        ["Honda EU7000is", "52-58", "$4,500"],
        ["Generac 7175", "57-65", "$2,500"],
    ]


def test_paragraph_lines_are_joined_with_a_space_not_concatenated():
    text = "This is line one\nand this continues it."
    blocks = parse_markdown_blocks(text)
    assert blocks[0]["type"] == "paragraph"
    joined_text = "".join(t for t, _ in blocks[0]["runs"])
    assert joined_text == "This is line one and this continues it."


def test_empty_text_returns_no_blocks():
    assert parse_markdown_blocks("") == []
    assert parse_markdown_blocks(None) == []


# ── Real sample from an actual stored AI response ─────────────────────────────

_REAL_SAMPLE = (
    "When looking for the **quietest open frame generator**, there are a few key "
    "factors to consider:\n\n"
    "1. **Decibel Rating (dB)**: The noise level of generators is typically measured "
    "in decibels. Lower dB means quieter operation.\n"
    "2. **Open Frame Design**: Open frame generators are generally louder than "
    "enclosed or inverter generators because they lack soundproofing.\n\n"
    "### Quietest Open Frame Generators (General Recommendations)\n\n"
    "- **Honda EU Series (e.g., EU2200i)**: While technically inverter generators "
    "and often enclosed, they are among the quietest on the market (~48-57 dB).\n"
    "- **Generac GP Series (e.g., GP2200i)**: Some models have relatively low noise "
    "levels (~58-65 dB) but are usually enclosed.\n\n"
    "---\n\n"
    "### Specific Quiet Open Frame Generator Models\n\n"
    "| Model | Noise (dB) |\n"
    "|-------|-----------|\n"
    "| Honda EU7000is | 52-58 |\n"
)


def test_real_stored_response_sample_parses_into_the_expected_block_sequence():
    blocks = parse_markdown_blocks(_REAL_SAMPLE)
    types = [b["type"] for b in blocks]
    assert types == [
        "paragraph", "numbered_list", "heading", "bullet_list",
        "hr", "heading", "table",
    ]
    assert blocks[2]["runs"] == [("Quietest Open Frame Generators (General Recommendations)", False)]
    assert len(blocks[3]["items"]) == 2
    assert blocks[6]["header"] == ["Model", "Noise (dB)"]
    assert blocks[6]["rows"] == [["Honda EU7000is", "52-58"]]
