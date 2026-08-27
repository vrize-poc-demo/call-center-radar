import { TranscriptTurn } from "../../api/calls";

export type ConversationDisplayTurn = {
  id: string;
  source_turn_id: string;
  speaker: TranscriptTurn["speaker"];
  start_ms: number;
  end_ms: number;
  text: string;
};

const stopWords = new Set([
  "about",
  "after",
  "again",
  "calling",
  "could",
  "hello",
  "hours",
  "local",
  "name",
  "needed",
  "please",
  "thank",
  "that",
  "there",
  "today",
  "what",
  "with",
  "wonderful",
  "would",
  "your",
]);

function splitSentences(text: string) {
  const protectedText = text.replaceAll("a.m.", "a_m_");
  return protectedText
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((sentence) => sentence.replaceAll("a_m_", "a.m.").trim())
    .filter(Boolean);
}

function keywords(text: string) {
  return new Set(
    text
      .toLocaleLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((word) => word.length > 3 && !stopWords.has(word)),
  );
}

function hasSharedTopic(left: string, right: string) {
  const leftWords = keywords(left);
  if (!leftWords.size) return false;
  return [...keywords(right)].some((word) => leftWords.has(word));
}

function isClosing(text: string) {
  return /\b(great day|thank you for calling|thanks for calling)\b/i.test(text);
}

function shouldSplit(turn: TranscriptTurn) {
  return (
    turn.end_ms - turn.start_ms > 12_000 && splitSentences(turn.text).length > 1
  );
}

export function buildConversationDisplayTurns(
  turns: TranscriptTurn[],
): ConversationDisplayTurn[] {
  const baseTurns = turns.flatMap((turn) => {
    const sentences = shouldSplit(turn)
      ? splitSentences(turn.text)
      : [turn.text];
    const sliceMs = Math.max(
      1,
      (turn.end_ms - turn.start_ms) / sentences.length,
    );
    return sentences.map((sentence, index) => ({
      id: `${turn.transcript_turn_id}:${index}`,
      source_turn_id: turn.transcript_turn_id,
      speaker: turn.speaker,
      start_ms: Math.round(turn.start_ms + sliceMs * index),
      end_ms: Math.round(
        index === sentences.length - 1
          ? turn.end_ms
          : turn.start_ms + sliceMs * (index + 1),
      ),
      text: sentence,
    }));
  });

  const customerTurns = baseTurns.filter((turn) => turn.speaker === "customer");
  const lastCustomerEnd = Math.max(
    0,
    ...customerTurns.map((turn) => turn.end_ms),
  );

  return baseTurns
    .map((turn, index) => {
      let sortMs = turn.start_ms;
      if (turn.speaker === "agent" && isClosing(turn.text) && lastCustomerEnd) {
        sortMs = lastCustomerEnd + index;
      } else if (turn.speaker === "agent") {
        const matchingCustomer = customerTurns
          .filter(
            (customer) =>
              customer.start_ms < turn.end_ms &&
              customer.end_ms > turn.start_ms &&
              hasSharedTopic(turn.text, customer.text),
          )
          .sort((left, right) => right.end_ms - left.end_ms)[0];
        if (matchingCustomer) sortMs = matchingCustomer.end_ms - 1;
      }
      return { turn, sortMs, index };
    })
    .sort(
      (left, right) => left.sortMs - right.sortMs || left.index - right.index,
    )
    .map(({ turn }) => turn);
}
