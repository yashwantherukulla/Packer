import { expect, test } from "@playwright/test";

test("extract+scan a fixture → progress → scan report with findings", async ({ page }) => {
  await page.goto("/scan");
  await page.getByTestId("model-ref").fill(process.env.E2E_SCAN_REF ?? "fixtures/malicious.pak");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("reconstruction")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("report-scan")).toBeVisible();
  await expect(page.getByTestId("findings-table")).toBeVisible();
});
