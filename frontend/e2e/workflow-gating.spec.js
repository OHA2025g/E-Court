import { test, expect } from "@playwright/test";
import { loginAdmin, loginCpc, adminReturnPeriod } from "./helpers/auth.js";

const TEST_PERIOD = "2026-06";
const TEST_PERIOD_LABEL = "June 2026";

test.describe.configure({ mode: "serial" });

test.describe("Submit → lock → approve workflow", () => {
  test("CPC submit locks edits; admin approve clears lock", async ({ page }) => {
    await adminReturnPeriod(page, TEST_PERIOD);
    await loginCpc(page);

    await page.goto("/submissions");
    await expect(page.getByTestId("sub-period-select")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("sub-period-select").selectOption({ label: TEST_PERIOD_LABEL });
    await page.getByTestId("sub-submit-btn").click();
    await expect(page.locator("[data-sonner-toast]")).toContainText("Status: OK", { timeout: 10_000 });

    await page.goto("/physical");
    await page.getByTestId("period-select").selectOption({ label: TEST_PERIOD_LABEL });
    await expect(page.getByTestId("period-lock-banner")).toBeVisible({ timeout: 10_000 });

    await loginAdmin(page);
    await page.goto("/submissions");
    await page.getByTestId("sub-hc-select").selectOption({ label: "Allahabad" });
    await page.getByTestId("sub-period-select").selectOption({ label: TEST_PERIOD_LABEL });
    await page.getByTestId("sub-approve-btn").click();
    await expect(page.locator("[data-sonner-toast]")).toContainText("Status: OK", { timeout: 10_000 });

    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-root")).toBeVisible({ timeout: 15_000 });
  });
});
