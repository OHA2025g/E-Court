import { test, expect } from "@playwright/test";
import path from "path";
import {
  loginAdmin,
  loginCpc,
  loginMember,
  loginViewer,
  logoutIfNeeded,
  openApplication,
  openTaskManagement,
  waitForAppSelector,
} from "./helpers/auth.js";

const FIXTURES = path.join(process.cwd(), "e2e", "fixtures");
const CHECKLIST_KEYS = [
  "resolution_matches",
  "evidence_uploaded",
  "evidence_relevant",
  "no_dependency_pending",
  "sla_checked",
];

const LEAD_OPTION = "Allahabad CPC Officer (cpc.allahabad@pmis.gov.in)";
const MEMBER_OPTION = "Task Team Member (member@pmis.gov.in)";

async function createManagerTask(page, { title, description, evidenceRequired = false, managerApproval = false }) {
  await page.getByTestId("tm-create-task").click();
  await page.getByTestId("tm-task-title").fill(title);
  await page.getByTestId("tm-task-description").fill(description);
  if (evidenceRequired) {
    await page.getByTestId("tm-task-evidence-required").check();
  }
  if (managerApproval) {
    await page.getByTestId("tm-task-manager-approval").check();
  }
  await page.getByTestId("tm-task-submit").click();
  await expect(page.getByText(/Task TASK-.* created/i)).toBeVisible({ timeout: 10_000 });
}

async function openTaskBySearch(page, title) {
  await page.goto(`/task-management/tasks?search=${encodeURIComponent(title)}`);
  await expect(page.locator("tr", { hasText: title })).toBeVisible({ timeout: 15_000 });
  await page.locator("tr", { hasText: title }).click();
  await expect(page.getByTestId("tm-task-detail")).toBeVisible();
  return page.url();
}

async function assignLeadAndMember(page) {
  await page.getByTestId("tm-tab-assignment").click();
  await page.getByTestId("tm-assign-lead").selectOption({ label: LEAD_OPTION });
  await page.getByTestId("tm-assign-lead-btn").click();
  await expect(page.getByText(/lead assigned/i)).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("tm-assign-member").selectOption({ label: MEMBER_OPTION });
  await page.getByTestId("tm-assign-member-btn").click();
  await expect(page.getByText(/member assigned/i)).toBeVisible({ timeout: 10_000 });
}

async function memberAcceptAndStart(page) {
  await page.getByTestId("tm-action-accept").click();
  await expect(page.getByTestId("tm-task-status")).toContainText(/accepted/i, { timeout: 10_000 });
  await page.getByTestId("tm-action-start").click();
  await expect(page.getByTestId("tm-task-status")).toContainText(/in progress/i, { timeout: 10_000 });
}

async function leadVerifyWithChecklist(page) {
  await page.getByTestId("tm-tab-approval").click();
  for (const key of CHECKLIST_KEYS) {
    await page.getByTestId(`tm-checklist-${key}`).check();
  }
  await page.getByTestId("tm-action-verify").click();
}

test.describe("App selector", () => {
  test("admin lands on app selector after login", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await expect(page.getByTestId("tile-task-management")).toBeVisible();
  });

  test("application tile opens PMIS dashboard", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openApplication(page);
    await expect(page.getByTestId("dashboard-root")).toBeVisible();
  });

  test("task management tile opens manager command centre", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await expect(page).toHaveURL(/\/task-management\/manager$/);
    await expect(page.getByTestId("tm-manager-root")).toBeVisible();
  });

  test("CPC opens team lead workbench from task tile", async ({ page }) => {
    await loginCpc(page, undefined, undefined, { openApp: false });
    await openTaskManagement(page);
    await expect(page).toHaveURL(/\/task-management\/team-lead$/);
    await expect(page.getByTestId("tm-lead-root")).toBeVisible();
  });

  test("viewer opens auditor overview from task tile", async ({ page }) => {
    await loginViewer(page, undefined, undefined, { openApp: false });
    await openTaskManagement(page);
    await expect(page).toHaveURL(/\/task-management\/auditor$/);
    await expect(page.getByTestId("tm-auditor-root")).toBeVisible();
  });
});

test.describe("Task management workflows", () => {
  test("manager creates a task from command centre", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, {
      title: `E2E task ${Date.now()}`,
      description: "Created by Playwright E2E",
    });
  });

  test("member workspace loads for team member", async ({ page }) => {
    await loginMember(page);
    await openTaskManagement(page);
    await expect(page).toHaveURL(/\/task-management\/my-tasks$/);
    await expect(page.getByTestId("tm-member-root")).toBeVisible();
  });

  test("direct dashboard URL still works after login", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-root")).toBeVisible({ timeout: 10_000 });
  });

  test("task list export links include format parameter", async ({ page }) => {
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await page.goto("/task-management/tasks");
    await expect(page.getByTestId("tm-list-root")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("tm-export-csv")).toHaveAttribute("href", /format=csv/);
    await expect(page.getByTestId("tm-export-xlsx")).toHaveAttribute("href", /format=xlsx/);
    await expect(page.getByTestId("tm-export-pdf")).toHaveAttribute("href", /format=pdf/);
  });
});

test.describe("Task workflow lifecycle", () => {
  test.describe.configure({ mode: "serial" });

  test("assign → accept → submit → verify closes task", async ({ page }) => {
    const title = `E2E workflow ${Date.now()}`;

    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, { title, description: "Playwright assign-submit-verify flow" });

    const taskUrl = await openTaskBySearch(page, title);
    await assignLeadAndMember(page);

    await logoutIfNeeded(page);
    await loginMember(page);
    await page.goto(taskUrl);
    await memberAcceptAndStart(page);
    await page.getByTestId("tm-action-submit").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/submitted/i, { timeout: 10_000 });

    await logoutIfNeeded(page);
    await loginCpc(page, undefined, undefined, { openApp: false });
    await page.goto(taskUrl);
    await leadVerifyWithChecklist(page);
    await expect(page.getByTestId("tm-task-status")).toContainText(/closed/i, { timeout: 10_000 });
  });

  test("evidence-required task blocks submit until evidence uploaded", async ({ page }) => {
    const title = `E2E evidence ${Date.now()}`;

    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, {
      title,
      description: "Evidence required before submit",
      evidenceRequired: true,
    });

    const taskUrl = await openTaskBySearch(page, title);
    await assignLeadAndMember(page);

    await logoutIfNeeded(page);
    await loginMember(page);
    await page.goto(taskUrl);
    await memberAcceptAndStart(page);

    await page.getByTestId("tm-action-submit").click();
    await expect(page.getByText(/evidence required/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("tm-task-status")).toContainText(/in progress/i);

    await page.getByTestId("tm-tab-evidence").click();
    const fileInput = page.getByTestId("tm-file-input");
    await fileInput.setInputFiles(path.join(FIXTURES, "task-evidence.txt"));
    await expect(page.getByText("task-evidence.txt")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("tm-evidence-upload-btn")).toBeEnabled();
    await page.getByTestId("tm-evidence-upload-btn").click();
    await expect(page.getByText(/evidence uploaded/i)).toBeVisible({ timeout: 10_000 });

    await page.getByTestId("tm-action-submit").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/submitted/i, { timeout: 10_000 });
  });

  test("manager final approval path closes after manager approves", async ({ page }) => {
    const title = `E2E manager closure ${Date.now()}`;

    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, {
      title,
      description: "Requires manager final approval",
      managerApproval: true,
    });

    const taskUrl = await openTaskBySearch(page, title);
    await assignLeadAndMember(page);

    await logoutIfNeeded(page);
    await loginMember(page);
    await page.goto(taskUrl);
    await memberAcceptAndStart(page);
    await page.getByTestId("tm-action-submit").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/submitted/i, { timeout: 10_000 });

    await logoutIfNeeded(page);
    await loginCpc(page, undefined, undefined, { openApp: false });
    await page.goto(taskUrl);
    await leadVerifyWithChecklist(page);
    await expect(page.getByTestId("tm-task-status")).toContainText(/manager approval pending/i, { timeout: 10_000 });

    await logoutIfNeeded(page);
    await loginAdmin(page, { openApp: false });
    await page.goto(taskUrl);
    await page.getByTestId("tm-action-approve-closure").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/closed/i, { timeout: 10_000 });
  });

  test("team lead escalates and member marks task blocked", async ({ page }) => {
    const escalateTitle = `E2E escalate ${Date.now()}`;
    const blockTitle = `E2E block ${Date.now()}`;

    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, { title: escalateTitle, description: "Escalate test" });
    const escalateUrl = await openTaskBySearch(page, escalateTitle);
    await page.getByTestId("tm-tab-assignment").click();
    await page.getByTestId("tm-assign-lead").selectOption({ label: LEAD_OPTION });
    await page.getByTestId("tm-assign-lead-btn").click();
    await expect(page.getByText(/lead assigned/i)).toBeVisible({ timeout: 10_000 });

    await logoutIfNeeded(page);
    await loginCpc(page, undefined, undefined, { openApp: false });
    await page.goto(escalateUrl);
    await page.getByTestId("tm-action-remarks").fill("Vendor dependency blocking progress");
    await page.getByTestId("tm-action-escalate").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/escalated/i, { timeout: 10_000 });

    await logoutIfNeeded(page);
    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, { title: blockTitle, description: "Block test" });
    const blockUrl = await openTaskBySearch(page, blockTitle);
    await assignLeadAndMember(page);

    await logoutIfNeeded(page);
    await loginMember(page);
    await page.goto(blockUrl);
    await memberAcceptAndStart(page);
    await page.getByTestId("tm-action-remarks").fill("Waiting on external vendor");
    await page.getByTestId("tm-action-block").click();
    await expect(page.getByTestId("tm-task-status")).toContainText(/blocked/i, { timeout: 10_000 });
  });

  test("bulk assign team lead on task list", async ({ page }) => {
    const prefix = `E2E bulk ${Date.now()}`;
    const titleA = `${prefix} A`;
    const titleB = `${prefix} B`;

    await loginAdmin(page, { openApp: false });
    await openTaskManagement(page);
    await createManagerTask(page, { title: titleA, description: "Bulk A" });
    await createManagerTask(page, { title: titleB, description: "Bulk B" });

    await page.goto(`/task-management/tasks?search=${encodeURIComponent(prefix)}`);
    await expect(page.locator("tr", { hasText: titleA })).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("tr", { hasText: titleB })).toBeVisible();

    await page.getByTestId("tm-select-all").check();
    await expect(page.getByTestId("tm-bulk-bar")).toBeVisible();
    await page.getByTestId("tm-bulk-assign-lead").selectOption({ label: LEAD_OPTION });
    await page.getByTestId("tm-bulk-assign-lead-btn").click();
    await expect(page.getByText(/team lead assigned to 2 task/i)).toBeVisible({ timeout: 10_000 });

    await page.locator("tr", { hasText: titleA }).click();
    await expect(page.getByTestId("tm-task-detail")).toBeVisible();
    await page.getByTestId("tm-tab-assignment").click();
    await expect(page.getByText("Current lead: Allahabad CPC Officer")).toBeVisible();
  });
});
