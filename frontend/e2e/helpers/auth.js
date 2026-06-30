import { execSync } from "child_process";
import path from "path";
import { expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.PMIS_ADMIN_EMAIL || "admin@pmis.gov.in";
const ADMIN_PASSWORD = process.env.PMIS_ADMIN_PASSWORD || "Admin@PMIS2026";
const ADMIN_TOTP_SECRET = process.env.ADMIN_TOTP_SECRET || "JBSWY3DPEHPK3PXP";

function projectRoot() {
  const cwd = process.cwd();
  return cwd.endsWith(`${path.sep}frontend`) ? path.dirname(cwd) : cwd;
}

export function currentTotp(secret = ADMIN_TOTP_SECRET) {
  try {
    return execSync(
      `docker compose exec -T backend python -c "import pyotp; print(pyotp.TOTP('${secret}').now())"`,
      { cwd: projectRoot(), encoding: "utf8" },
    ).trim();
  } catch {
    return null;
  }
}

export async function waitForAppSelector(page) {
  await expect(page.getByTestId("tile-task-management")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("tile-application")).toBeVisible();
}

export async function openApplication(page) {
  if (!(await page.getByTestId("tile-application").isVisible().catch(() => false))) {
    await page.goto("/app-selector");
    await waitForAppSelector(page);
  }
  await page.getByTestId("tile-application").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByTestId("dashboard-root")).toBeVisible({ timeout: 15_000 });
}

export async function openTaskManagement(page) {
  if (!page.url().includes("/app-selector")) {
    await page.goto("/app-selector");
    await waitForAppSelector(page);
  }
  await page.getByTestId("tile-task-management").click();
  await page.waitForURL(/task-management/, { timeout: 15_000 });
}

export async function logoutIfNeeded(page) {
  await page.goto("/login");
  if (await page.getByTestId("login-email-input").isVisible().catch(() => false)) {
    return;
  }
  await page.context().clearCookies();
  await page.goto("/login");
  await expect(page.getByTestId("login-email-input")).toBeVisible({ timeout: 15_000 });
}

/** Admin-return an Allahabad period so CPC E2E tests can submit/edit again. */
export async function adminReturnPeriod(page, period = "2026-06") {
  await loginAdmin(page, { openApp: false });
  const ok = await page.evaluate(async ({ period, note }) => {
    const resp = await fetch("/api/submissions/return", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ high_court: "Allahabad", reporting_period: period, note }),
    });
    return resp.ok;
  }, { period, note: "E2E reset" });
  expect(ok).toBeTruthy();
  await logoutIfNeeded(page);
}

export async function loginAdmin(page, { openApp = true } = {}) {
  await logoutIfNeeded(page);
  await page.getByTestId("login-email-input").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password-input").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit-btn").click();

  await expect(page.getByTestId("login-totp-input")).toBeVisible({ timeout: 12_000 });
  const totp = currentTotp();
  if (!totp) {
    throw new Error("Admin 2FA required but TOTP could not be generated (is Docker running?)");
  }
  await page.getByTestId("login-totp-input").fill(totp);
  await page.getByTestId("login-submit-btn").click();

  await waitForAppSelector(page);
  if (openApp) {
    await openApplication(page);
  }
}

export async function loginCpc(page, email = "cpc.allahabad@pmis.gov.in", password = "Cpc@PMIS2026", { openApp = true } = {}) {
  await logoutIfNeeded(page);
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(password);
  await page.getByTestId("login-submit-btn").click();
  await waitForAppSelector(page);
  if (openApp) {
    await openApplication(page);
  }
}

export async function loginMember(page, email = "member@pmis.gov.in", password = "Member@PMIS2026") {
  await logoutIfNeeded(page);
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(password);
  await page.getByTestId("login-submit-btn").click();
  await waitForAppSelector(page);
}

export async function loginViewer(page, email = "viewer@pmis.gov.in", password = "View@PMIS2026", { openApp = true } = {}) {
  await logoutIfNeeded(page);
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(password);
  await page.getByTestId("login-submit-btn").click();
  await waitForAppSelector(page);
  if (openApp) {
    await openApplication(page);
  }
}
