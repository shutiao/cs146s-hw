def test_create_and_list_notes(client):
    payload = {"title": "Test", "content": "Hello world"}
    r = client.post("/notes/", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Test"

    r = client.get("/notes/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1

    r = client.get("/notes/search/")
    assert r.status_code == 200

    r = client.get("/notes/search/", params={"q": "Hello"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1


# --- TASKS #2: search endpoint improvements ---


def test_search_empty_q_returns_all(client):
    """Empty q should return all notes."""
    client.post("/notes/", json={"title": "A", "content": "aaa"})
    client.post("/notes/", json={"title": "B", "content": "bbb"})
    r = client.get("/notes/search/", params={"q": ""})
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2


def test_search_no_match_returns_empty(client):
    """Search with no matching notes returns empty list, not 404."""
    client.post("/notes/", json={"title": "Python Tips", "content": "typing is fun"})
    r = client.get("/notes/search/", params={"q": "java"})
    assert r.status_code == 200
    assert r.json() == []


def test_search_matches_title(client):
    """q matches note title."""
    client.post("/notes/", json={"title": "Meeting Notes", "content": "todo items here"})
    r = client.get("/notes/search/", params={"q": "Meeting"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["title"] == "Meeting Notes"


def test_search_matches_content(client):
    """q matches note content, not just title."""
    client.post("/notes/", json={"title": "Weekly Update", "content": "released v2.0 today"})
    r = client.get("/notes/search/", params={"q": "v2.0"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["content"] == "released v2.0 today"


def test_search_ascii_case_insensitive(client):
    """ASCII letters must match regardless of case."""
    client.post("/notes/", json={"title": "Hello World", "content": "Foo bar"})

    r = client.get("/notes/search/", params={"q": "hello"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/notes/search/", params={"q": "HELLO"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/notes/search/", params={"q": "HeLLo"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_unicode_case_insensitive(client):
    """Unicode letters (accented, etc.) must also be case-insensitive.

    SQLite's default LIKE is case-insensitive only for ASCII; Unicode
    characters like é, ñ, ü require explicit LOWER() on both sides.
    """
    client.post("/notes/", json={"title": "Café Menu", "content": "Résumé tips"})

    # lowercase query → match
    r = client.get("/notes/search/", params={"q": "café"})
    assert r.status_code == 200
    assert len(r.json()) == 1, f"expected match for 'café' (lowercase), got: {r.json()}"

    # UPPERCASE query → must still match (this is the bug being fixed)
    r = client.get("/notes/search/", params={"q": "CAFÉ"})
    assert r.status_code == 200
    assert len(r.json()) == 1, f"expected match for 'CAFÉ' (uppercase Unicode), got: {r.json()}"

    # mixed case
    r = client.get("/notes/search/", params={"q": "Café"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_route_without_trailing_slash(client):
    """GET /notes/search?q=... (no trailing slash) should also work.

    TASKS.md specifies `/notes/search?q=...`, but the current
    implementation only has `/notes/search/`. Without the slash, FastAPI
    routes the request to `/{note_id}` which fails to parse 'search'
    as an integer.
    """
    client.post("/notes/", json={"title": "Dinner", "content": "at 7pm"})

    r = client.get("/notes/search", params={"q": "Dinner"})
    assert r.status_code == 200, (
        f"Expected 200, got {r.status_code}: {r.text}. "
        "Route without trailing slash might be hitting /{note_id} instead."
    )
    items = r.json()
    assert len(items) == 1
