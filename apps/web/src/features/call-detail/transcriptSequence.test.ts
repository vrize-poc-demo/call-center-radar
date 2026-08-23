import { describe, expect, it } from "vitest";

import type { TranscriptTurn } from "../../api/calls";
import { buildTranscriptSequence } from "./transcriptSequence";

function turn(
  transcript_turn_id: string,
  speaker: TranscriptTurn["speaker"],
  start_ms: number,
  end_ms: number,
): TranscriptTurn {
  return {
    transcript_turn_id,
    speaker,
    start_ms,
    end_ms,
    text: transcript_turn_id,
  };
}

describe("buildTranscriptSequence", () => {
  it("orders non-overlapping turns by immutable saved timing", () => {
    const groups = buildTranscriptSequence([
      turn("third", "agent", 3000, 4000),
      turn("first", "customer", 0, 1000),
      turn("second", "agent", 1000, 2000),
    ]);

    expect(groups.map((group) => group.turns[0].transcript_turn_id)).toEqual([
      "first",
      "second",
      "third",
    ]);
    expect(groups.every((group) => !group.has_overlap)).toBe(true);
  });

  it("groups a long segment with speech whose timing overlaps it", () => {
    const groups = buildTranscriptSequence([
      turn("checkbook-sentence", "agent", 22020, 44900),
      turn("address", "customer", 30000, 32000),
      turn("next-turn", "agent", 45000, 47000),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].has_overlap).toBe(true);
    expect(groups[0].turns.map((item) => item.transcript_turn_id)).toEqual([
      "checkbook-sentence",
      "address",
    ]);
    expect(groups[0].start_ms).toBe(22020);
    expect(groups[0].end_ms).toBe(44900);
  });

  it("uses end time and turn ID as stable equal-start tie breakers", () => {
    const groups = buildTranscriptSequence([
      turn("z-long", "agent", 1000, 4000),
      turn("b-short", "customer", 1000, 2000),
      turn("a-short", "agent", 1000, 2000),
    ]);

    expect(groups[0].turns.map((item) => item.transcript_turn_id)).toEqual([
      "a-short",
      "b-short",
      "z-long",
    ]);
  });
});
