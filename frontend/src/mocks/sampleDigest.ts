import type { Digest } from "../types";

export function getSampleDigest(): Digest {
  return sampleDigest;
}

export const sampleDigest: Digest = {
  id: "dg-sample-001",
  generated_at: "2026-10-20T06:00:00Z",
  window: { start: "2026-10-19T20:00:00Z", end: "2026-10-20T06:00:00Z" },
  model: "sample",
  prompt_version: "sample-1",
  groups: [
    {
      conversation_id: "trip-planning",
      platform: "whatsapp",
      name: "Weekend trip planning 🏔️",
      message_count: 412,
      skipped_count: 358,
      tldr: "Trip venue and cost are still undecided. Riya pitched two options; most hover went quiet.",
      needs_you: [
        {
          message_id: "msg-sample-0042",
          from: "Riya",
          summary: "Asks whether you can drive on Saturday or take the bus",
          reason: "Direct question to you — blocks venue choice",
          suggested_reply:
            "I can drive, +1 passenger seat free. Pick the venue and I'm in.",
        },
        {
          message_id: "msg-sample-0101",
          from: "Aman",
          summary: "Wants your split of the booking amount by Friday",
          reason: "Money deadline directed at you",
          suggested_reply: "Sending my share tonight.",
        },
      ],
      decisions: [
        {
          text: "Leaving Saturday morning, not Friday night",
          message_ids: ["msg-sample-0198", "msg-sample-0201"],
        },
        {
          text: "Budget capped at ₹3,000 per person",
          message_ids: ["msg-sample-0311"],
        },
      ],
      by_person: [
        {
          name: "Riya",
          points: [
            "Pitched Kheerganga and Tirthan Valley",
            "Called the cheapest bus route",
          ],
        },
        {
          name: "Aman",
          points: ["Collected booking amounts", "Tentative Saturday 6am start"],
        },
        { name: "Kabir", points: ["Mostly memes and emojis"] },
      ],
      deadlines: [
        {
          text: "Send booking amount by Friday",
          message_ids: ["msg-sample-0101"],
        },
        { text: "Vote on venue by tonight", message_ids: ["msg-sample-0042"] },
      ],
    },
    {
      conversation_id: "cricket-squad",
      platform: "discord",
      name: "sunday-cricket-squad",
      message_count: 187,
      skipped_count: 171,
      tldr: "Match time moved to 7pm because of heat and ground booking.",
      needs_you: [
        {
          message_id: "msg-sample-0456",
          from: "Dev",
          summary: "Confirming headcount for the 7pm match",
          reason: "Wants your confirmation before booking",
        },
      ],
      decisions: [
        {
          text: "Match moved to Sunday 7pm",
          message_ids: ["msg-sample-0450", "msg-sample-0456"],
        },
      ],
      by_person: [
        {
          name: "Dev",
          points: ["Booked the ground", "Moved the start to 7pm"],
        },
        { name: "Sam", points: ["Bring extra water balls"] },
      ],
      deadlines: [],
    },
  ],
};
