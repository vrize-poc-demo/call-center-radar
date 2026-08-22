from dataclasses import dataclass

from app.transcripts import TranscriptTurn

SILENCE_THRESHOLD_MS = 3000


@dataclass(frozen=True)
class SilenceWindow:
    before_turn: TranscriptTurn
    after_turn: TranscriptTurn
    duration_ms: int


@dataclass(frozen=True)
class ConversationBalance:
    agent_talk_ms: int
    customer_talk_ms: int
    agent_share_pct: float
    customer_share_pct: float


def detect_silence_windows(turns: list[TranscriptTurn]) -> list[SilenceWindow]:
    """Find meaningful no-speech gaps between ordered saved transcript turns."""
    if not turns:
        return []
    windows = []
    before_turn = turns[0]
    latest_end_ms = before_turn.end_ms
    for turn in turns[1:]:
        gap_ms = turn.start_ms - latest_end_ms
        if gap_ms >= SILENCE_THRESHOLD_MS:
            windows.append(SilenceWindow(before_turn, turn, gap_ms))
        if turn.end_ms > latest_end_ms:
            before_turn = turn
            latest_end_ms = turn.end_ms
    return windows


def calculate_conversation_balance(turns: list[TranscriptTurn]) -> ConversationBalance:
    agent_talk_ms = sum(turn.end_ms - turn.start_ms for turn in turns if turn.speaker == "agent")
    customer_talk_ms = sum(
        turn.end_ms - turn.start_ms for turn in turns if turn.speaker == "customer"
    )
    attributed_talk_ms = agent_talk_ms + customer_talk_ms
    if attributed_talk_ms == 0:
        return ConversationBalance(0, 0, 0, 0)
    return ConversationBalance(
        agent_talk_ms=agent_talk_ms,
        customer_talk_ms=customer_talk_ms,
        agent_share_pct=round(agent_talk_ms / attributed_talk_ms * 100, 1),
        customer_share_pct=round(customer_talk_ms / attributed_talk_ms * 100, 1),
    )
