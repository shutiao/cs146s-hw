from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Note
from ..schemas import NoteCreate, NoteRead

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/", response_model=list[NoteRead])
def list_notes(db: Session = Depends(get_db)) -> list[NoteRead]:
    rows = db.execute(select(Note)).scalars().all()
    return [NoteRead.model_validate(row) for row in rows]


@router.post("/", response_model=NoteRead, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> NoteRead:
    note = Note(title=payload.title, content=payload.content)
    db.add(note)
    db.flush()
    db.refresh(note)
    return NoteRead.model_validate(note)


def _search_notes(q: Optional[str], db: Session) -> list[NoteRead]:
    if not q:
        rows = db.execute(select(Note)).scalars().all()
    else:
        q_lower = q.lower()
        rows = (
            db.execute(
                select(Note).where(
                    func.lower(Note.title).contains(q_lower)
                    | func.lower(Note.content).contains(q_lower)
                )
            )
            .scalars()
            .all()
        )
    return [NoteRead.model_validate(row) for row in rows]


@router.get("/search", response_model=list[NoteRead])
@router.get("/search/", response_model=list[NoteRead])
def search_notes(q: Optional[str] = None, db: Session = Depends(get_db)) -> list[NoteRead]:
    return _search_notes(q, db)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: int, db: Session = Depends(get_db)) -> NoteRead:
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteRead.model_validate(note)
