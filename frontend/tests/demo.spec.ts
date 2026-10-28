// The 3-minute judge demo, end to end in a real browser. Changes data: run `make seed` afterwards.
import { expect, test, type Page } from "@playwright/test";

async function as(page: Page, label: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Try a demo account").selectOption({ label });
  await page.getByRole("button", { name: "Continue as this role" }).click();
}

test("judge demo path", async ({ page }) => {
  // 1. Desk Officer: Today's register
  await as(page, "Desk Officer, A. Kulkarni, RB");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await expect(page.getByText("What to do now")).toBeVisible();

  // 2-3. Narmada: overlap banner with reasons
  await page.goto("/institutions");
  await page.getByText("Narmada Institute of Technology").first().click();
  await expect(page.getByText(/open cases? across PGRC and RB/).first()).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Potential Overlapping Cases - Coordination Required" })).toBeVisible();
  await expect(page.getByText(/AICTE ID matched on both cases/).first()).toBeVisible();

  // 4. Coordinator assigns a lead unit
  await as(page, "Coordinator, M. Qureshi");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await page.goto("/overlaps");
  await page.locator("main a.card", { hasText: "Narmada" }).click();
  await expect(page.getByText("Why these cases were matched")).toBeVisible();
  await page.getByRole("button", { name: "Assign RB as lead unit" }).click();
  await page.getByLabel(/Decision and reason/).fill("RB leads the inspection follow-up; PGRC keeps the students informed.");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText(/Coordinator assigned RB as lead unit/)).toBeVisible();

  // 5. Kaveri: typed name -> confirm the suggested match (PGRC officer)
  await as(page, "Desk Officer, S. Iyer, PGRC");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await page.goto("/cases?q=Kaveri%20Inst.");
  await page.locator("tr.clickable").first().click();
  await expect(page.getByText("Suggested institution")).toBeVisible();
  await page.getByRole("button", { name: "Confirm match" }).click();
  await expect(page.getByText(/Institution confirmed/).first()).toBeVisible();

  // 6. Conflict guard: RB records a show-cause notice on Narmada while PGRC's case is open
  await as(page, "Desk Officer, A. Kulkarni, RB");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await page.goto("/cases?q=Narmada&unit=RB&status=OPEN");
  await page.locator("tr.clickable").first().click();
  await page.getByRole("button", { name: "Record action" }).click();
  await page.getByLabel("What was done").selectOption("Show-cause notice issued");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Another unit is handling this institution")).toBeVisible();
  await page.getByLabel(/Why are you continuing/).fill("Coordinator made RB the lead unit; PGRC informed.");
  await page.getByRole("button", { name: "Acknowledge and continue" }).click();
  await expect(page.getByText("Conflict acknowledged").first()).toBeVisible();

  // 7. Admin: demo clock +30 days -> email log
  await as(page, "Admin, T. Joseph");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "+30 days" }).click();
  await expect(page.getByRole("status").getByText("DEMO CLOCK")).toBeVisible();
  await page.goto("/emails");
  await expect(page.getByText(/SLA alerts on your cases|Cases escalated to you/).first()).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page.goto("/admin");
  await page.getByRole("button", { name: "Back to today" }).click();

  // 8. Management dashboard + audit verify
  await as(page, "Management, K. Rao");
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await expect(page.getByText("Case ageing (open)")).toBeVisible();
  await page.goto("/audit");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByText("Chain intact.")).toBeVisible();

  // 9. Public status check shows masked data only
  await page.goto("/check/RB-2026-0001");
  await expect(page.getByText(/\*\*\*/)).toBeVisible();
});
