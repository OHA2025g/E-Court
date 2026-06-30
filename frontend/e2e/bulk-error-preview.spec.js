import { test, expect } from "@playwright/test";
import path from "path";
import { loginCpc } from "./helpers/auth.js";

const FIXTURES = path.join(process.cwd(), "e2e", "fixtures");
const PERIOD = "2026-06";

async function login(page, email, password) {
  await page.goto("/login");
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(password);
  await page.getByTestId("login-submit-btn").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test.describe("Bulk upload error row preview", () => {
  test.beforeEach(async ({ page }) => {
    await loginCpc(page);
  });

  test("shows error rows in preview table", async ({ page }) => {
    await page.goto("/physical");
    await page.getByTestId("period-select").selectOption(PERIOD);

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(FIXTURES, "physical-bulk-errors.xlsx"));

    await expect(page.getByText(/Preview \(dry-run\)/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Errors:/i)).toBeVisible();
    await expect(page.locator("tbody tr.bg-red-50").first()).toBeVisible();
    await expect(page.getByText(/^Error$/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Confirm import/i })).toBeDisabled();
  });
});
