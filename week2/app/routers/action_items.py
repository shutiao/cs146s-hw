from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from .. import db
from ..services.extract import extract_action_items, extract_action_items_llm


router = APIRouter(prefix="/action-items", tags=["action-items"])


def _extract_and_save(text: str, save_note: bool, extractor) -> Dict[str, Any]:
    """Shared logic for both extract endpoints: extract, optionally save note, persist items."""
    note_id: Optional[int] = None
    if save_note:
        note_id = db.insert_note(text)

    items = extractor(text)
    ids = db.insert_action_items(items, note_id=note_id)
    return {"note_id": note_id, "items": [{"id": i, "text": t} for i, t in zip(ids, items)]}


@router.post("/extract")
def extract(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic-based action item extraction (rule-based, fast)."""
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return _extract_and_save(text, bool(payload.get("save_note")), extract_action_items)


@router.post("/extract-llm")
def extract_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-powered action item extraction via Ollama (slower, understands semantics)."""
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return _extract_and_save(text, bool(payload.get("save_note")), extract_action_items_llm)


@router.get("")
def list_all(note_id: Optional[int] = None) -> List[Dict[str, Any]]:
    rows = db.list_action_items(note_id=note_id)
    return [
        {
            "id": r["id"],
            "note_id": r["note_id"],
            "text": r["text"],
            "done": bool(r["done"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/{action_item_id}/done")
def mark_done(action_item_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    done = bool(payload.get("done", True))
    db.mark_action_item_done(action_item_id, done)
    return {"id": action_item_id, "done": done}


