import { describe, expect, it } from "vitest";
import { formatRange, formatUsd } from "./money";

describe("formatUsd", () => {
  it("formats decimal strings with grouping", () => {
    expect(formatUsd("1234567.5")).toBe("$1,234,567.50");
    expect(formatUsd("-12")).toBe("-$12.00");
    expect(formatUsd("0.07")).toBe("$0.07");
  });
  it("rejects non-decimal input", () => {
    expect(() => formatUsd("1e5")).toThrow();
    expect(() => formatUsd("abc")).toThrow();
  });
});

describe("formatRange", () => {
  it("collapses equal bounds", () => {
    expect(formatRange("10", "10")).toBe("$10.00");
    expect(formatRange("10", "20.5")).toBe("$10.00 – $20.50");
  });
});
