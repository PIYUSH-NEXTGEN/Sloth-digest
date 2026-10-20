import { describe, expect, it } from "vitest";
import { sampleDigest } from "../mocks/sampleDigest";

describe("sampleDigest", () => {
  it("matches the digest structure from AGENTS.md 7.1", () => {
    expect(sampleDigest.id).toBeTruthy();
    expect(sampleDigest.window.start).toBeTruthy();
    expect(sampleDigest.window.end).toBeTruthy();
    expect(sampleDigest.model).toBeTruthy();
    expect(sampleDigest.prompt_version).toBeTruthy();
    expect(sampleDigest.groups.length).toBeGreaterThan(0);

    for (const group of sampleDigest.groups) {
      expect(group.conversation_id).toBeTruthy();
      expect(group.message_count).toBeGreaterThan(0);
      expect(group.message_count).toBeGreaterThanOrEqual(group.skipped_count);
      // tldr is max 2 sentences
      expect(group.tldr).not.toBe("");
      for (const item of group.needs_you) {
        expect(item.message_id).toBeTruthy();
        expect(item.from).toBeTruthy();
        expect(item.reason).toBeTruthy();
      }
      for (const decision of group.decisions) {
        expect(decision.message_ids.length).toBeGreaterThan(0);
      }
      for (const person of group.by_person) {
        expect(person.points.length).toBeGreaterThan(0);
      }
      for (const deadline of group.deadlines) {
        expect(deadline.message_ids.length).toBeGreaterThan(0);
      }
    }
  });
});
