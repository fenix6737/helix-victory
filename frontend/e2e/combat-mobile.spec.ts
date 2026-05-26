import { test, expect } from "@playwright/test";

const USER = process.env.E2E_USER ?? "helix_admin";
const PASS = process.env.E2E_PASS ?? "HelixVictory2026!Admin";

test.describe("実戦モバイル E2E", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByText("管理者ID").locator("..").locator("input").fill(USER);
    await page.getByText("パスワード").locator("..").locator("input").fill(PASS);
    await page.getByRole("button", { name: /ログイン/i }).click();
    await page.waitForURL(/\/(welcome)?$/, { timeout: 20_000 });
    if (page.url().includes("/welcome")) {
      await page.getByRole("link", { name: /ホーム|開始/i }).first().click();
    }
    await expect(page.locator("body")).toBeVisible();
  });

  test("combat panel + tabs + pachinko", async ({ page }) => {
    await expect(page.getByTestId("combat-panel")).toBeVisible({ timeout: 25_000 });
    await expect(
      page
        .locator("[data-combat-mode]")
        .or(page.getByText(/打ってよい|打てる|慎重|危ない|やめる|撤退/))
    ).toBeVisible();

    const slotTab = page.getByRole("button", { name: /スロット/i });
    const pachiTab = page.getByRole("button", { name: /パチンコ/i });
    if (await slotTab.isVisible()) await slotTab.click();
    await expect(page.locator("a[href^='/machines/']").first()).toBeVisible({
      timeout: 20_000,
    });

    if (await pachiTab.isVisible()) {
      await pachiTab.click();
      await page.waitForTimeout(800);
    }

    const recTab = page.getByRole("button", { name: /推奨/i });
    if (await recTab.isVisible()) await recTab.click();

    await expect(page.locator("body")).not.toContainText("Loading...", {
      timeout: 5_000,
    });
  });

  test("retreat reason or alt candidates visible", async ({ page }) => {
    await expect(page.getByTestId("combat-panel")).toBeVisible({ timeout: 25_000 });
    const panel = page.getByTestId("combat-panel");
    const hasAlt = await page.getByTestId("alt-candidates").isVisible().catch(() => false);
    const hasPrimary = await panel.getByText(/いち推し/).isVisible().catch(() => false);
    const expand = page.getByRole("button", { name: /詳細・数字を見る/ });
    if (await expand.isVisible()) await expand.click();
    const hasRetreat = await page.getByTestId("retreat-reason").isVisible().catch(() => false);
    expect(hasAlt || hasRetreat || hasPrimary).toBeTruthy();
  });

  test("store switch responsive", async ({ page }) => {
    const storeBtn = page.locator("button, select").filter({ hasText: /店|キコーナ|マルハン/i }).first();
    if (await storeBtn.isVisible()) {
      await storeBtn.click();
    }
    await expect(
      page.getByText(/打ってよい|打てる|慎重|危ない|やめる|撤退/).first()
    ).toBeVisible({
      timeout: 25_000,
    });
  });
});
