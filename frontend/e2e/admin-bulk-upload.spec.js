import { test, expect } from "@playwright/test";
import path from "path";
import { loginAdmin } from "./helpers/auth.js";

const FIXTURES = path.join(process.cwd(), "e2e", "fixtures");
const PERIOD = "2026-06";

async function bulkPreviewAndConfirm(page, trackerPath, fixtureName) {
  await page.goto(trackerPath);
  await expect(page.getByText(/Export & Bulk Upload/i)).toBeVisible();

  const periodSelect = page.getByTestId("period-select");
  await expect(periodSelect).toBeVisible();
  await expect(periodSelect.locator(`option[value='${PERIOD}']`)).toHaveCount(1, { timeout: 10_000 });
  await periodSelect.selectOption(PERIOD);

  const fileInput = page.locator('input[type="file"]');
  await expect(fileInput).toBeEnabled({ timeout: 10_000 });
  await fileInput.setInputFiles(path.join(FIXTURES, fixtureName));

  await expect(page.getByText(/Preview \(dry-run\)/i)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Valid rows:/i)).toBeVisible();

  const confirmBtn = page.getByRole("button", { name: /Confirm import/i });
  await expect(confirmBtn).toBeEnabled({ timeout: 10_000 });
  await confirmBtn.click();

  await expect(page.getByText(/Import complete:/i)).toBeVisible({ timeout: 30_000 });
}

test.describe("Admin bulk upload via preview_token", () => {
  test("Admin uploads physical Excel and commits", async ({ page }) => {
    await loginAdmin(page);
    await bulkPreviewAndConfirm(page, "/physical", "physical-bulk.xlsx");
  });

  test("Admin uploads financial Excel and commits", async ({ page }) => {
    await loginAdmin(page);
    await bulkPreviewAndConfirm(page, "/financial", "financial-bulk.xlsx");
  });

  test("Admin uploads outcome Excel and commits", async ({ page }) => {
    await loginAdmin(page);
    await bulkPreviewAndConfirm(page, "/outcome", "outcome-bulk.xlsx");
  });
});
