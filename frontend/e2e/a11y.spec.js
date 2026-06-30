import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { loginAdmin, loginCpc, loginViewer, loginMember, openTaskManagement } from "./helpers/auth.js";

async function assertNoSeriousViolations(page, context = "") {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .exclude("[data-sonner-toast]")
    .exclude(".react-joyride__tooltip")
    .exclude(".react-joyride__overlay")
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(serious, context ? `${context}: ${JSON.stringify(serious, null, 2)}` : JSON.stringify(serious)).toEqual([]);
}

async function dismissOverlays(page) {
  await page.locator("[data-sonner-toast]").first().waitFor({ state: "hidden", timeout: 8000 }).catch(() => {});
  const skipTour = page.getByRole("button", { name: /skip tour/i });
  if (await skipTour.isVisible().catch(() => false)) {
    await skipTour.click();
    await page.waitForTimeout(300);
  }
}

test.describe("Accessibility (WCAG 2.1 AA — critical/serious)", () => {
  test("public progress page", async ({ page }) => {
    await page.goto("/public");
    await expect(page.getByRole("heading").first()).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "public progress");
  });

  test("login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByTestId("login-email-input")).toBeVisible();
    await assertNoSeriousViolations(page, "login");
  });

  test("dashboard after viewer login", async ({ page }) => {
    await loginViewer(page);
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "viewer dashboard");
  });

  test("dashboard after admin login", async ({ page }) => {
    await loginAdmin(page);
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "admin dashboard");
  });

  test("physical tracker after CPC login", async ({ page }) => {
    await loginCpc(page);
    await page.getByTestId("nav-physical").click();
    await expect(page.getByTestId("physical-table")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "physical tracker");
  });

  test("financial tracker after CPC login", async ({ page }) => {
    await loginCpc(page);
    await page.getByTestId("nav-financial").click();
    await expect(page.getByTestId("financial-table")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "financial tracker");
  });

  test("outcome tracker after CPC login", async ({ page }) => {
    await loginCpc(page);
    await page.getByTestId("nav-outcome").click();
    await expect(page.getByTestId("outcome-table")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "outcome tracker");
  });

  test("reports page after viewer login", async ({ page }) => {
    await loginViewer(page);
    await page.getByTestId("nav-reports").click();
    await expect(page.getByTestId("reports-root")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "reports");
  });

  test("submissions page after CPC login", async ({ page }) => {
    await loginCpc(page);
    await page.getByTestId("nav-submissions").click();
    await expect(page.getByTestId("submissions-table")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "submissions");
  });

  test("master data after admin login", async ({ page }) => {
    await loginAdmin(page);
    await page.getByTestId("nav-master").click();
    await expect(page.getByRole("tab", { name: /high courts/i })).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "master data");
  });

  test("schedules after admin login", async ({ page }) => {
    await loginAdmin(page);
    await page.getByTestId("nav-schedules").click();
    await expect(page.getByTestId("run-cabinet-now")).toBeVisible({ timeout: 15_000 });
    await dismissOverlays(page);
    await assertNoSeriousViolations(page, "schedules");
  });

  test("app selector after login", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email-input").fill("viewer@pmis.gov.in");
    await page.getByTestId("login-password-input").fill("View@PMIS2026");
    await page.getByTestId("login-submit-btn").click();
    await expect(page.getByTestId("tile-task-management")).toBeVisible({ timeout: 25_000 });
    await assertNoSeriousViolations(page, "app selector");
  });

  test("task management manager dashboard", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await page.getByTestId("tile-task-management").click();
    await expect(page.getByTestId("tm-manager-root")).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "task manager dashboard");
  });

  test("task management team lead workbench", async ({ page }) => {
    await loginCpc(page, undefined, undefined, { openApp: false });
    await openTaskManagement(page);
    await expect(page.getByTestId("tm-lead-root")).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "task team lead workbench");
  });

  test("task management member workspace", async ({ page }) => {
    await loginMember(page);
    await openTaskManagement(page);
    await expect(page.getByTestId("tm-member-root")).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "task member workspace");
  });

  test("task management auditor overview", async ({ page }) => {
    await loginViewer(page, undefined, undefined, { openApp: false });
    await openTaskManagement(page);
    await expect(page.getByTestId("tm-auditor-root")).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "task auditor overview");
  });

  test("task management list page", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await page.goto("/task-management/tasks");
    await expect(page.getByTestId("tm-list-root")).toBeVisible({ timeout: 15_000 });
    await assertNoSeriousViolations(page, "task list");
  });

  test("task management detail page", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await page.goto("/task-management/tasks");
    await expect(page.getByTestId("tm-list-root")).toBeVisible({ timeout: 15_000 });
    const row = page.locator("tbody tr").first();
    if (await row.count()) {
      await row.click();
      await expect(page.getByTestId("tm-task-detail")).toBeVisible({ timeout: 15_000 });
      await assertNoSeriousViolations(page, "task detail");
    }
  });
});
