import { test, expect } from "@playwright/test";

test.describe("Public progress page", () => {
  test("loads national KPIs and visualisations without login", async ({ page }) => {
    await page.goto("/public");
    await expect(page.getByTestId("public-progress-root")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Physical progress", { exact: true })).toBeVisible();
    await expect(page.getByText("Financial utilisation", { exact: true })).toBeVisible();
    await expect(page.getByText("Outcome KPI reporting", { exact: true })).toBeVisible();
    await expect(page.getByTestId("rag-delta-widget")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("pareto-chart")).toBeVisible();
    await expect(page.getByText("Official login")).toBeVisible();
  });

  test("public RAG delta API returns comparison data", async ({ request }) => {
    const base = process.env.PMIS_BASE_URL || "http://localhost:5182";
    const r = await request.get(`${base}/api/public/rag-delta`, {
      params: { reporting_period: "2026-06", metric: "physical" },
    });
    expect(r.ok()).toBeTruthy();
    const data = await r.json();
    expect(data.turned_green).toBeDefined();
    expect(data.current_period).toBe("2026-06");
  });
});
