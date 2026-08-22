import { TranscriptTurn } from "../../api/calls";

export function selectActiveTranscriptTurn(
  turns: TranscriptTurn[],
  timeMs: number,
): TranscriptTurn | undefined {
  return turns.reduce<TranscriptTurn | undefined>((selected, turn) => {
    if (timeMs < turn.start_ms || timeMs >= turn.end_ms) return selected;
    if (!selected || turn.start_ms > selected.start_ms) return turn;
    if (turn.start_ms !== selected.start_ms) return selected;

    const selectedDuration = selected.end_ms - selected.start_ms;
    const turnDuration = turn.end_ms - turn.start_ms;
    return turnDuration < selectedDuration ? turn : selected;
  }, undefined);
}
