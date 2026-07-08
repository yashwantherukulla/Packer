import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// The zip is produced by the Python harness (build_toy_repo) before the UI run;
// the nightly workflow builds it into outputs/e2e-artifacts/ (Task 12).
// ESM-safe __dirname (package.json has "type": "module").
const here = path.dirname(fileURLToPath(import.meta.url));
const TOY_ZIP = path.resolve(here, "../../outputs/e2e-artifacts/toy_repo.zip");

test("pack -> detect -> extract+scan through the UI", async ({ page }) => {
  // 1. PACK — the Uploader auto-submits on file select; live WS progress then a result card.
  await page.goto("/pack");
  await page.getByLabel(/repository/i).setInputFiles(TOY_ZIP);
  await expect(page.getByTestId("job-progress")).toBeVisible(); // live WS progress appears
  const card = page.getByTestId("pack-result");
  await expect(card).toBeVisible({ timeout: 15 * 60_000 });
  await expect(card).toContainText(/original/i); // honest size metrics (not a compressor)
  await expect(card).toContainText(/artifact|\.pak/i);

  // Chain the produced artifact into detect/scan via its id (from the .pak download link).
  const href = await page.getByTestId("download").getAttribute("href");
  const artifactId = href?.match(/artifacts\/([^?]+)/)?.[1];
  expect(artifactId, "artifact id parsed from download href").toBeTruthy();

  // 2. DETECT (drive from the artifact just produced)
  await page.goto("/detect");
  await page.getByTestId("model-ref").fill(`artifact:${artifactId}`);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("verdict-badge")).toHaveText(/MEMORIZED-CODE-LIKELY/i, {
    timeout: 120_000,
  });
  await expect(page.getByTestId("limitations")).toContainText(/signature/i); // ADR-007 note renders

  // 3. EXTRACT + SCAN (model_ref chains extract -> scan; exact-mode reconstruction tree)
  await page.goto("/scan");
  await page.getByTestId("model-ref").fill(`artifact:${artifactId}`);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("reconstruction")).toContainText(/byte-?exact/i, {
    timeout: 120_000,
  });
  await expect(page.getByTestId("report-scan")).toBeVisible();
  const findings = page.getByTestId("findings-table");
  await expect(findings).toBeVisible();
  await expect(findings.getByRole("row", { name: /exfil\.py/i })).toContainText(
    /malicious|high|critical/i,
  );
});
