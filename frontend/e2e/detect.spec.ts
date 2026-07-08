import { expect, test } from "@playwright/test";

test("detect a fixture → progress → detect report with the limitation note", async ({ page }) => {
  await page.goto("/detect");
  await page.getByTestId("model-ref").fill(process.env.E2E_DETECT_REF ?? "fixtures/memorized.pak");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("verdict-badge")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("report-detect")).toBeVisible();
  await expect(page.getByTestId("limitations")).toContainText(/signature/i);
});
