import { describe, expect, it } from "vitest";
import { formatHours, formatPercent, formatRelativeDate, UNAVAILABLE } from "../format";

describe("formatHours", () => {
  it("renders null as an explicit dash rather than a zero", () => {
    expect(formatHours(null)).toBe(UNAVAILABLE);
  });

  it("uses minutes below an hour", () => {
    expect(formatHours(0.5)).toBe("30m");
  });

  it("uses hours in the normal range", () => {
    expect(formatHours(3.42)).toBe("3.4h");
  });

  it("switches to days beyond two days, where hours stop being readable", () => {
    expect(formatHours(72)).toBe("3.0d");
  });

  it("does not hide a genuine zero measurement", () => {
    // 0m is a real, meaningful result: it is what the broken lead-time metric
    // actually produces, and hiding it would conceal the defect.
    expect(formatHours(0)).toBe("0m");
  });
});

describe("formatPercent", () => {
  it("renders null as unavailable", () => {
    expect(formatPercent(null)).toBe(UNAVAILABLE);
  });

  it("keeps one decimal place", () => {
    expect(formatPercent(22.66)).toBe("22.7%");
  });
});

describe("formatRelativeDate", () => {
  it("renders null as unavailable", () => {
    expect(formatRelativeDate(null)).toBe(UNAVAILABLE);
  });

  it("renders an unparseable value as unavailable rather than Invalid Date", () => {
    expect(formatRelativeDate("not-a-date")).toBe(UNAVAILABLE);
  });

  it("describes a recent date in days", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 86_400_000).toISOString();
    expect(formatRelativeDate(threeDaysAgo)).toBe("3 days ago");
  });
});
