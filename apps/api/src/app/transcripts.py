from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.logging import log_event

router = APIRouter(prefix="/api/calls", tags=["transcripts"])


class TranscriptTurnInput(BaseModel):
    speaker: str = Field(pattern="^(agent|customer|unknown)$")
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=10000)


class TranscriptTurn(BaseModel):
    transcript_turn_id: str
    speaker: str
    start_ms: int
    end_ms: int
    text: str


class TranscriptSaveRequest(BaseModel):
    turns: list[TranscriptTurnInput] = Field(min_length=1, max_length=1000)


class TranscriptResponse(BaseModel):
    call_id: str
    turns: list[TranscriptTurn]


def _get_call_row(connection, call_id: str):
    row = connection.execute(
        "SELECT id, call_id FROM calls WHERE call_id = ?", (call_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
    return row


def get_call_row(database, call_id: str):
    with database.connect() as connection:
        return _get_call_row(connection, call_id)


def replace_transcript_turns(
    database, call_id: str, turns: list[TranscriptTurnInput], *, connection=None
) -> list[TranscriptTurn]:
    """Replace a call transcript atomically while creating fresh immutable turn identifiers."""

    if any(turn.end_ms < turn.start_ms for turn in turns):
        raise ValueError("invalid_transcript_timing")
    if connection is not None:
        return _replace_transcript_turns(connection, call_id, turns)
    with database.connect() as database_connection:
        return _replace_transcript_turns(database_connection, call_id, turns)


def _replace_transcript_turns(connection, call_id: str, turns: list[TranscriptTurnInput]):
    call = _get_call_row(connection, call_id)
    connection.execute("DELETE FROM call_analyses WHERE call_id = ?", (call["id"],))
    connection.execute("DELETE FROM transcript_turns WHERE call_id = ?", (call["id"],))
    saved = []
    for turn in turns:
        turn_id = f"turn_{uuid4().hex}"
        connection.execute(
            "INSERT INTO transcript_turns "
            "(transcript_turn_id, call_id, speaker, start_ms, end_ms, text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (turn_id, call["id"], turn.speaker, turn.start_ms, turn.end_ms, turn.text.strip()),
        )
        saved.append(TranscriptTurn(transcript_turn_id=turn_id, **turn.model_dump()))
    return saved


@router.put("/{call_id}/transcript", response_model=TranscriptResponse)
def save_transcript(
    call_id: str, payload: TranscriptSaveRequest, request: Request
) -> TranscriptResponse:
    database = request.app.state.database
    try:
        saved = replace_transcript_turns(database, call_id, payload.turns)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Turn end time must not precede start time.",
        ) from None
    log_event(
        request.app.state.logger,
        "transcript_saved",
        "Transcript turns persisted",
        context={"call_id": call_id, "turn_count": len(saved)},
    )
    return TranscriptResponse(call_id=call_id, turns=saved)


@router.get("/{call_id}/transcript", response_model=TranscriptResponse)
def get_transcript(call_id: str, request: Request) -> TranscriptResponse:
    database = request.app.state.database
    call = get_call_row(database, call_id)
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT transcript_turn_id, speaker, start_ms, end_ms, text "
            "FROM transcript_turns WHERE call_id = ? ORDER BY start_ms, id",
            (call["id"],),
        ).fetchall()
    return TranscriptResponse(call_id=call_id, turns=[TranscriptTurn(**dict(row)) for row in rows])
