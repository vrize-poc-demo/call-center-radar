import { describe, expect, it } from "vitest";

import { TranscriptTurn } from "../../api/calls";
import { buildConversationDisplayTurns } from "./conversationDisplay";

describe("buildConversationDisplayTurns", () => {
  it("splits and reorders long overlapping agent turns for readable conversation order", () => {
    const turns: TranscriptTurn[] = [
      {
        transcript_turn_id: "agent-greeting",
        speaker: "agent",
        start_ms: 3600,
        end_ms: 9440,
        text: "Hello, this is Harper Valley National Bank. My name is Linda. How can I help you today?",
      },
      {
        transcript_turn_id: "agent-long-answer",
        speaker: "agent",
        start_ms: 9440,
        end_ms: 49620,
        text: "The branch hours are 9.30 a.m. to 5 p.m. Thank you for calling. Have a great day.",
      },
      {
        transcript_turn_id: "customer-hi",
        speaker: "customer",
        start_ms: 12500,
        end_ms: 13500,
        text: "Hi, Linda.",
      },
      {
        transcript_turn_id: "customer-name",
        speaker: "customer",
        start_ms: 13500,
        end_ms: 14600,
        text: "My name is Robert Miller.",
      },
      {
        transcript_turn_id: "customer-question",
        speaker: "customer",
        start_ms: 14600,
        end_ms: 29980,
        text: "I was wondering what your local branch hours are.",
      },
      {
        transcript_turn_id: "customer-wonderful",
        speaker: "customer",
        start_ms: 29980,
        end_ms: 43530,
        text: "Wonderful.",
      },
      {
        transcript_turn_id: "customer-okay",
        speaker: "customer",
        start_ms: 43530,
        end_ms: 44530,
        text: "Okay.",
      },
      {
        transcript_turn_id: "customer-thanks",
        speaker: "customer",
        start_ms: 44530,
        end_ms: 45530,
        text: "Well, thank you for your help.",
      },
      {
        transcript_turn_id: "customer-done",
        speaker: "customer",
        start_ms: 45530,
        end_ms: 46530,
        text: "That's all I needed.",
      },
    ];

    expect(
      buildConversationDisplayTurns(turns).map((turn) => turn.text),
    ).toEqual([
      "Hello, this is Harper Valley National Bank. My name is Linda. How can I help you today?",
      "Hi, Linda.",
      "My name is Robert Miller.",
      "I was wondering what your local branch hours are.",
      "The branch hours are 9.30 a.m. to 5 p.m.",
      "Wonderful.",
      "Okay.",
      "Well, thank you for your help.",
      "That's all I needed.",
      "Thank you for calling.",
      "Have a great day.",
    ]);
  });
});
