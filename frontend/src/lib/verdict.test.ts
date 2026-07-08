import { expect, test } from "vitest";
import { riskTone, severityTone, toneClasses, verdictTone } from "@/lib/verdict";

test("detect verdict labels map to tones", () => {
  expect(verdictTone("MEMORIZED-CODE-LIKELY")).toBe("danger");
  expect(verdictTone("INCONCLUSIVE")).toBe("warn");
  expect(verdictTone("UNLIKELY")).toBe("ok");
});

test("scan risk + severity map to tones", () => {
  expect(riskTone("malicious")).toBe("danger");
  expect(riskTone("benign")).toBe("ok");
  expect(severityTone("high")).toBe("danger");
  expect(severityTone("low")).toBe("ok");
});

test("every tone has light + dark classes", () => {
  for (const tone of ["danger", "warn", "ok", "neutral"] as const) {
    expect(toneClasses[tone]).toContain("dark:");
  }
});
