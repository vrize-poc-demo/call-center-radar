import type { TranscriptTurn } from "../../api/calls";

export type TranscriptSequenceGroup = {
  id: string;
  start_ms: number;
  end_ms: number;
  has_overlap: boolean;
  turns: TranscriptTurn[];
};

function compareTurns(left: TranscriptTurn, right: TranscriptTurn) {
  return (
    left.start_ms - right.start_ms ||
    left.end_ms - right.end_ms ||
    left.transcript_turn_id.localeCompare(right.transcript_turn_id)
  );
}

export function buildTranscriptSequence(
  turns: TranscriptTurn[],
): TranscriptSequenceGroup[] {
  const orderedTurns = [...turns].sort(compareTurns);
  const groups: TranscriptSequenceGroup[] = [];

  for (const turn of orderedTurns) {
    const current = groups.at(-1);
    if (!current || turn.start_ms >= current.end_ms) {
      groups.push({
        id: turn.transcript_turn_id,
        start_ms: turn.start_ms,
        end_ms: turn.end_ms,
        has_overlap: false,
        turns: [turn],
      });
      continue;
    }

    current.turns.push(turn);
    current.end_ms = Math.max(current.end_ms, turn.end_ms);
    current.has_overlap = true;
  }

  return groups;
}
