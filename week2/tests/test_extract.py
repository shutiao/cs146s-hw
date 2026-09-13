from ..app.services.extract import extract_action_items, extract_action_items_llm


# ---------------------------------------------------------------------------
# Heuristic extractor tests
# ---------------------------------------------------------------------------


def test_extract_bullets_and_checkboxes():
    text = """
    Notes from meeting:
    - [ ] Set up database
    * implement API extract endpoint
    1. Write tests
    pick up kids 1 hour later
    """.strip()

    items = extract_action_items(text)
    assert "Set up database" in items
    assert "implement API extract endpoint" in items
    assert "Write tests" in items
    # Free-form line without bullet/keyword markers is NOT caught by the heuristic
    # extractor -- this gap is exactly what the LLM-based extractor (TODO 1) solves.
    assert "pick up kids 1 hour later" not in items


# ---------------------------------------------------------------------------
# LLM extractor tests (requires a running Ollama server)
# ---------------------------------------------------------------------------


def test_extract_action_items_llm():
    cases = [
        # (description, input_text, expect_non_empty)
        ("empty input", "", False),
        ("bullet list", "- Set up database\n- Implement API\n- Write tests", True),
        ("keyword prefixed", "todo: buy milk\naction: fix bug", True),
        ("free-form text", "pick up kids 1 hour later\ncomplete exam on wednesday", True),
        ("no actionable items", "The sky is blue and the meeting was pleasant overall.", False),
    ]
    for description, text, expect_non_empty in cases:
        items = extract_action_items_llm(text)
        assert isinstance(items, list), f"{description}: result must be a list"
        assert all(
            isinstance(i, str) and i.strip() for i in items
        ), f"{description}: every item must be a non-empty string"
        if expect_non_empty:
            assert len(items) > 0, f"{description}: expected at least one action item"
        else:
            assert len(items) == 0, f"{description}: expected no action items"
