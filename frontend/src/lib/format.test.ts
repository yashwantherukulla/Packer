import { expect, test } from "vitest";
import { formatBytes, formatPct, formatRatio } from "@/lib/format";

test("formatBytes scales units", () => {
  expect(formatBytes(512)).toBe("512 B");
  expect(formatBytes(1536)).toBe("1.5 KB");
  expect(formatBytes(180_000)).toBe("175.8 KB");
});

test("formatPct + formatRatio", () => {
  expect(formatPct(0.25)).toBe("25%");
  expect(formatRatio(39.2)).toBe("39.2×");
});
