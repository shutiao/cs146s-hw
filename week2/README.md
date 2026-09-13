# Action Item Extractor (Week 2)

A FastAPI + SQLite web app that converts free-form meeting notes into an enumerated checklist of action items. It ships with two extraction strategies: a fast rule-based (heuristic) extractor and an LLM-powered extractor backed by a local Ollama model.

## Project Structure

```
week2/
├── app/
│   ├── main.py              # FastAPI entry point: creates app, registers routers, serves frontend
│   ├── db.py                # SQLite data layer: connection, schema, CRUD helpers
│   ├── routers/
│   │   ├── notes.py         # /notes endpoints
│   │   └── action_items.py  # /action-items endpoints (extract, list, mark-done)
│   └── services/
│       └── extract.py       # Extraction logic: heuristic + LLM (Ollama)
├── frontend/
│   └── index.html           # Minimal raw-HTML/JS single-page frontend
├── tests/
│   └── test_extract.py      # Unit tests for both extractors
└── data/                    # Auto-created at runtime; holds app.db
```

## Setup

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management
- [Ollama](https://ollama.com/) for the LLM extractor (optional — only needed for the LLM endpoint)

### Install dependencies

From the repository root (where `pyproject.toml` lives):

```bash
poetry install
```

### Pull an Ollama model

The LLM extractor defaults to `llama3.1:8b`. Pull it (or any other model):

```bash
ollama pull llama3.1:8b
```

To use a different model, set the `OLLAMA_MODEL` environment variable (or add it to a `.env` file at the repo root, which `python-dotenv` loads automatically):

```bash
export OLLAMA_MODEL=mistral-nemo:12b
```

### Run the server

```bash
poetry run uvicorn week2.app.main:app --reload
```

Then open http://127.0.0.1:8000/ in your browser. The `--reload` flag auto-restarts the server on code changes.

## API Endpoints

All endpoints return JSON. The interactive API docs are available at http://127.0.0.1:8000/docs once the server is running.

### Action Items

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/action-items/extract` | Extract action items using the **heuristic** (rule-based) extractor. Body: `{"text": "...", "save_note": bool}`. Returns `{"note_id", "items": [{"id", "text"}]}`. |
| `POST` | `/action-items/extract-llm` | Extract action items using the **LLM-powered** extractor (Ollama). Same request/response shape as above. Slower but understands free-form semantics. |
| `GET` | `/action-items` | List all action items. Optional `?note_id=<id>` query param filters by note. |
| `POST` | `/action-items/{id}/done` | Mark an action item as done (or not). Body: `{"done": bool}`. |

### Notes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/notes` | Create a note. Body: `{"content": "..."}`. Returns the saved note with `id`, `content`, `created_at`. |
| `GET` | `/notes/{note_id}` | Retrieve a single note by ID. Returns 404 if not found. |

## Extraction Strategies

### Heuristic (`extract_action_items`)

A deterministic, regex-based extractor that recognizes:

- Lines starting with bullet markers (`-`, `*`, `•`, or `1.`)
- Lines prefixed with `todo:`, `action:`, or `next:`
- Lines containing `[ ]` or `[todo]` checkboxes
- Fallback: sentences starting with a small set of imperative verbs (`add`, `fix`, `write`, …)

It is fast and requires no external services, but it misses free-form action items that don't follow these patterns.

### LLM (`extract_action_items_llm`)

Calls a local Ollama model with a JSON-schema-enforced prompt (`format={"type": "array", "items": {"type": "string"}}`), ensuring structured output. It understands the semantics of the text and can extract action items from unstructured sentences. If the model returns malformed output, the function returns an empty list rather than raising.

## Running the Test Suite

Tests live in `week2/tests/test_extract.py` and cover both the heuristic and LLM extractors. The LLM tests make real calls to Ollama, so the Ollama server must be running with the configured model available.

From the repository root:

```bash
# Run all tests in week2
poetry run pytest week2/tests/ -v

# Run only the LLM extractor test
poetry run pytest week2/tests/test_extract.py::test_extract_action_items_llm -v
```
