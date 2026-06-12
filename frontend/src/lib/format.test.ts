import { describe, expect, it } from "vitest";

import { formatEta } from "./format";
import type { Eta } from "./api/types";

function eta(partial: Partial<Eta>): Eta {
  return { minutes: 5, seconds: 300, next_stop: null, source: "gps", ...partial };
}

describe("formatEta", () => {
  it("returns null for nullish or unavailable estimates", () => {
    expect(formatEta(null)).toBeNull();
    expect(formatEta(undefined)).toBeNull();
    expect(formatEta(eta({ source: "unavailable", minutes: null, seconds: null }))).toBeNull();
    expect(formatEta(eta({ minutes: null }))).toBeNull();
  });

  it("names the next stop when known", () => {
    expect(formatEta(eta({ minutes: 4, next_stop: "Tinkune" }))).toBe("Tinkune in 4 min");
  });

  it("falls back to a plain label when no next stop", () => {
    expect(formatEta(eta({ minutes: 7, next_stop: null }))).toBe("Arriving in 7 min");
  });

  it("reads sub-minute as Due (with stop name when known)", () => {
    expect(formatEta(eta({ minutes: 0, next_stop: "Kalanki" }))).toBe("Due at Kalanki");
    expect(formatEta(eta({ minutes: 0, next_stop: null }))).toBe("Due");
  });

  it("renders the schedule-source estimate the same way", () => {
    expect(formatEta(eta({ source: "schedule", minutes: 12, next_stop: null }))).toBe(
      "Arriving in 12 min",
    );
  });
});
