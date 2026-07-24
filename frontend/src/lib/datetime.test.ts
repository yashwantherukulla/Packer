import { expect, test } from "vitest";
import { formatTimestamp } from "@/lib/datetime";

test("formatTimestamp renders stable utc text", () => {
  expect(formatTimestamp("2026-07-23T10:01:30Z")).toBe("2026-07-23 10:01:30 UTC");
  expect(formatTimestamp(null)).toBe("pending");
});
