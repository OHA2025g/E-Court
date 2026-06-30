import { test, expect } from "@playwright/test";
import path from "path";
import { loginCpc, adminReturnPeriod } from "./helpers/auth.js";

const FIXTURES = path.join(process.cwd(), "e2e", "fixtures");
const PERIOD = "2026-06";

async function ensureTrackerRows(page, trackerPath) {
  if (trackerPath === "/physical") return;
  const initPath = trackerPath.includes("financial") ? "/api/financial/init-period" : "/api/outcome/init-period";
  const ok = await page.evaluate(async ({ path, period }) => {
    const resp = await fetch(path, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ high_court: "Allahabad", reporting_period: period }),
    });
    return resp.ok;
  }, { path: initPath, period: PERIOD });
  expect(ok).toBeTruthy();
}

async function bulkPreviewAndConfirm(page, trackerPath, fixtureName) {
  await ensureTrackerRows(page, trackerPath);
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
  await expect(page.getByText(/Preview \(dry-run\)/i)).toHaveCount(0);
}

test.describe.configure({ mode: "serial" });

test.describe("Bulk upload preview → confirm", () => {
  test.beforeEach(async ({ page }) => {
    await adminReturnPeriod(page, PERIOD);
    await loginCpc(page, "cpc.allahabad@pmis.gov.in", "Cpc@PMIS2026");
  });

  test("Physical tracker", async ({ page }) => {
    await bulkPreviewAndConfirm(page, "/physical", "physical-bulk.xlsx");
  });

  test("Financial tracker", async ({ page }) => {
    await bulkPreviewAndConfirm(page, "/financial", "financial-bulk.xlsx");
  });

  test("Outcome tracker", async ({ page }) => {
    await bulkPreviewAndConfirm(page, "/outcome", "outcome-bulk.xlsx");
  });
});
