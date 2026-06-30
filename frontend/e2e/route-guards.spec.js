import { test, expect } from "@playwright/test";
import { loginCpc, loginViewer } from "./helpers/auth.js";

test.describe("Route guards", () => {
  test("CPC user is redirected from admin-only /users", async ({ page }) => {
    await loginCpc(page);
    await page.goto("/users");
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByTestId("nav-users")).toHaveCount(0);
  });

  test("Viewer can open master data but not user management", async ({ page }) => {
    await loginViewer(page);
    await page.goto("/master");
    await expect(page).toHaveURL(/\/master$/);
    await page.goto("/users");
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

test.describe("Bulk upload panel", () => {
  test("Viewer sees upload control disabled without period", async ({ page }) => {
    await loginViewer(page);
    await page.goto("/physical");
    await expect(page.getByText(/Upload & preview/i)).toBeVisible();
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeDisabled();
  });
});
