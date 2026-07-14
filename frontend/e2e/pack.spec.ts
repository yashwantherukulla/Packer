import { expect, test } from "@playwright/test";
import path from "node:path";

test("pack a tiny repo → progress streams → artifact card with honest metrics", async ({ page }) => {
  await page.goto("/pack");
  await page.getByLabel(/repository/i).setInputFiles(path.join(__dirname, "fixtures/toy_repo.zip"));
  await expect(page.getByTestId("job-progress")).toBeVisible();
  const card = page.getByTestId("pack-result");
  await expect(card).toBeVisible({ timeout: 180_000 });
  await expect(card).toContainText("Original");
  await expect(card).toContainText("Artifact (.pak)");
  await expect(page.getByTestId("download")).toBeVisible();
  await expect(page.getByTestId("detect-from-pack")).toBeVisible();
});
