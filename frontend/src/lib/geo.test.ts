import { describe, expect, it } from "vitest";

import { formatDistance, haversineKm } from "./geo";

describe("haversineKm", () => {
  it("is zero for identical points", () => {
    expect(haversineKm({ lat: 27.7, lng: 85.3 }, { lat: 27.7, lng: 85.3 })).toBe(0);
  });

  it("matches the ~111 km/degree of latitude rule", () => {
    const d = haversineKm({ lat: 0, lng: 0 }, { lat: 1, lng: 0 });
    expect(d).toBeGreaterThan(110);
    expect(d).toBeLessThan(112);
  });

  it("is symmetric", () => {
    const a = { lat: 27.7, lng: 85.3 };
    const b = { lat: 27.72, lng: 85.34 };
    expect(haversineKm(a, b)).toBeCloseTo(haversineKm(b, a), 6);
  });
});

describe("formatDistance", () => {
  it("renders metres under 1 km", () => {
    expect(formatDistance(0.35)).toBe("350 m");
    expect(formatDistance(0)).toBe("0 m");
  });

  it("renders one-decimal km at or above 1 km", () => {
    expect(formatDistance(1.234)).toBe("1.2 km");
    expect(formatDistance(12)).toBe("12.0 km");
  });

  it("returns an empty string for non-finite input", () => {
    expect(formatDistance(Number.NaN)).toBe("");
  });
});
