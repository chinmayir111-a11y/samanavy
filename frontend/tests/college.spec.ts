// Full college-user path in a real browser. The 6-digit code is read from the API's development
// log (APP_ENV=development prints it); set API_LOG if the API logs elsewhere. Run `make seed` after.
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const LOG = process.env.API_LOG || "/tmp/smv-api.log";

function codeFor(email: string): string {
  const lines = readFileSync(LOG, "utf8").split("\n").filter((l) => l.includes(`verification code for ${email}:`));
  const m = lines.at(-1)?.match(/(\d{6})\s*$/);
  if (!m) throw new Error(`no code for ${email} in ${LOG}`);
  return m[1];
}

test("sign up with 'Poona', verify, file, track, then the officer sees it", async ({ page }) => {
  const email = `e2e.${Date.now()}@example.com`;
  await page.goto("/login");
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Full name").fill("Asha Patil");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("college2026");
  await page.getByLabel("Student").check();
  await page.getByRole("button", { name: "Next" }).click();

  await page.getByLabel("College name").fill("Shivneri College of Engineering");
  await page.getByRole("option", { name: "My college is not listed" }).click();
  await page.getByLabel("City or town").fill("Poona");
  await expect(page.getByText("Pune, Pune district, Maharashtra, Western region.")).toBeVisible();
  await page.getByRole("button", { name: "Yes" }).click();
  await page.getByRole("button", { name: "Create my account" }).click();

  await expect(page.getByText("Check your email")).toBeVisible();
  await expect.poll(() => { try { return codeFor(email); } catch { return ""; } }).toMatch(/^\d{6}$/);
  await page.getByLabel("6-digit code").fill(codeFor(email));
  await page.getByRole("button", { name: "Verify and continue" }).click();

  await expect(page.getByText("What do you want to do?")).toBeVisible();
  await page.getByRole("link", { name: "File a complaint" }).first().click();
  await page.getByText("Fees and refunds").click();
  await page.getByLabel("Tell us the problem in your own words").fill("The college charged Rs 25,000 extra as development fee and gave no receipt.");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Skip and continue" }).click();
  await expect(page.getByText("Shivneri College of Engineering")).toBeVisible();
  await page.getByRole("button", { name: "Submit complaint" }).click();

  const ref = (await page.getByTestId("reference").textContent())!.trim();
  expect(ref).toMatch(/^PGRC-\d{4}-\d{4}$/);
  await expect(page.getByRole("img", { name: /QR code/ })).toBeVisible();
  await page.getByRole("link", { name: "Track this complaint" }).click();
  await expect(page.getByText("We received your complaint.")).toBeVisible();
  await expect(page.getByText(/Public Grievance Redressal Cell/).first()).toBeVisible();

  // The demo Desk Officer of PGRC sees it in the register.
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Try a demo account").selectOption({ label: "Desk Officer, S. Iyer, PGRC" });
  await page.getByRole("button", { name: "Continue as this role" }).click();
  await page.getByRole("button", { name: /Skip tour/ }).click({ timeout: 3000 }).catch(() => {});
  await page.goto("/today");
  await expect(page.locator("table.ledger").getByText(ref)).toBeVisible();
});
