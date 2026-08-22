from dataclasses import dataclass

from app.transcripts import TranscriptTurn

RULE_ID = "false_resolution_contradiction_v1"

# These phrases deliberately describe a completed outcome, rather than a promise
# to investigate. The narrow vocabulary favours precision for the POC.
RESOLUTION_PHRASES = (
    "is resolved",
    "has been resolved",
    "is fixed",
    "is fixed now",
    "has been fixed",
    "is working now",
    "should be working now",
    "all set",
)
CONTRADICTION_PHRASES = (
    "not resolved",
    "still not working",
    "still is not working",
    "still can't",
    "still cannot",
    "still unable",
    "didn't work",
    "doesn't work",
    "does not work",
    "can't access",
    "cannot access",
    "unable to access",
)


@dataclass(frozen=True)
class FalseResolutionDetection:
    resolution_turn: TranscriptTurn | None
    contradiction_turn: TranscriptTurn | None
    suppression_reason: str | None = None

    @property
    def detected(self) -> bool:
        return self.resolution_turn is not None and self.contradiction_turn is not None


def detect_false_resolution(turns: list[TranscriptTurn]) -> FalseResolutionDetection:
    """Find one strong agent-resolution/customer-contradiction sequence.

    This is deliberately deterministic and speaker-aware. It does not infer an
    outcome from vague language or from a customer repeating the agent's words.
    """
    resolution_turn: TranscriptTurn | None = None
    for turn in turns:
        text = turn.text.lower()
        if resolution_turn is None:
            if turn.speaker == "agent" and any(phrase in text for phrase in RESOLUTION_PHRASES):
                resolution_turn = turn
            continue
        if turn.speaker == "customer" and any(phrase in text for phrase in CONTRADICTION_PHRASES):
            return FalseResolutionDetection(resolution_turn, turn)

    if resolution_turn is not None:
        return FalseResolutionDetection(
            None,
            None,
            suppression_reason="no_later_customer_contradiction",
        )
    return FalseResolutionDetection(None, None)
