"""Deterministic, customer-to-agent treatment signals for supportive review."""

import re
from dataclasses import dataclass

from app.transcripts import TranscriptTurn


@dataclass(frozen=True)
class TreatmentRule:
    rule_id: str
    label: str
    patterns: tuple[str, ...]


# The vocabulary is intentionally narrow. A match records only what the customer
# said in the saved transcript; it does not make an assessment of the agent.
TREATMENT_RULES = (
    TreatmentRule(
        rule_id="customer_abusive_language_v1",
        label="Abusive language toward agent",
        patterns=(
            r"\byou(?: are|'re) (?:an )?idiot\b",
            r"\byou(?: are|'re) (?:so )?stupid\b",
            r"\byou(?: are|'re) useless\b",
            r"\byou(?: are|'re) incompetent\b",
            r"\bshut up\b",
            r"\bgo to hell\b",
            r"\b(?:you(?: are|'re) a )?moron\b",
        ),
    ),
    TreatmentRule(
        rule_id="customer_escalation_or_frustration_v1",
        label="Explicit customer escalation or frustration",
        patterns=(
            r"\b(?:let me speak to|i want) (?:a |your )?supervisor\b",
            r"\bescalate this\b",
            r"\bthis is unacceptable\b",
            r"\b(?:i am|i'm) frustrated\b",
            r"\bthis is frustrating\b",
            r"\b(?:i am|i'm) filing a complaint\b",
            r"\bi(?:'ll| will) file a complaint\b",
        ),
    ),
)


@dataclass(frozen=True)
class TreatmentSignalDetection:
    rule_id: str
    label: str
    turn: TranscriptTurn


def detect_agent_treatment_signals(
    turns: list[TranscriptTurn],
) -> tuple[list[TreatmentSignalDetection], int]:
    """Return high-precision customer signals and the unknown-speaker suppression count."""
    detections: list[TreatmentSignalDetection] = []
    unknown_speaker_turn_count = 0
    for turn in turns:
        if turn.speaker == "unknown":
            unknown_speaker_turn_count += 1
            continue
        if turn.speaker != "customer":
            continue
        normalized_text = turn.text.casefold()
        for rule in TREATMENT_RULES:
            if any(re.search(pattern, normalized_text) for pattern in rule.patterns):
                detections.append(
                    TreatmentSignalDetection(
                        rule_id=rule.rule_id,
                        label=rule.label,
                        turn=turn,
                    )
                )
    return detections, unknown_speaker_turn_count
