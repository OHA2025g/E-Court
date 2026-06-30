import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers/auth.js";

test.describe("Scheduled cabinet brief", () => {
  test("admin can trigger job and download PDF via API", async ({ page }) => {
    await loginAdmin(page);

    const runResp = await page.request.post("/api/admin/scheduled-deliveries/run-now");
    expect(runResp.ok()).toBeTruthy();

    const listResp = await page.request.get("/api/admin/scheduled-deliveries");
    expect(listResp.ok()).toBeTruthy();
    const deliveries = await listResp.json();
    expect(deliveries.length).toBeGreaterThan(0);

    const latest = deliveries[0];
    expect(latest.status).toBe("generated");
    expect(latest.pdf_size_bytes).toBeGreaterThan(1000);

    const pdfResp = await page.request.get(`/api/admin/scheduled-deliveries/${latest.id}/pdf`);
    expect(pdfResp.ok()).toBeTruthy();
    expect(pdfResp.headers()["content-type"]).toContain("pdf");
    const buf = await pdfResp.body();
    expect(buf.slice(0, 4).toString()).toBe("%PDF");
  });

  test("schedules page shows run-now control", async ({ page }) => {
    await loginAdmin(page);
    await page.goto("/schedules");
    await expect(page.getByTestId("run-cabinet-now")).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("run-cabinet-now").click();
    await expect(page.getByText(/generated/i).first()).toBeVisible({ timeout: 20_000 });
  });
});
