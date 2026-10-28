// Screens for college users at 1440 and 390 px: node scripts/shoot-college.mjs ../screenshots
// Files a real complaint as the demo student (run `make seed` afterwards).
import { chromium } from "@playwright/test";
const out = process.argv[2] || "../screenshots";
const WEB = process.env.WEB || "http://localhost:5173";
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome" });
for (const w of [1440, 390]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
  const p = await ctx.newPage();
  const shot = (n) => p.screenshot({ path: `${out}/${n}-${w}.png`, fullPage: true });
  await p.goto(WEB + "/login"); await p.waitForTimeout(700);
  await p.selectOption("#demo", "officer"); await shot("login");
  await p.goto(WEB + "/signup"); await p.waitForTimeout(400);
  await p.fill("#sn", "Asha Patil"); await p.fill("#se", "asha.demo@example.com"); await p.fill("#sp", "college2026");
  await p.getByLabel("Student").check(); await shot("create-account-step1");
  await p.getByRole("button", { name: "Next" }).click();
  await p.fill("#college", "Narmada"); await p.waitForTimeout(800); await shot("create-account-step2");
  await p.getByRole("option").first().click();
  await p.fill("#sc", "Poona"); await p.waitForTimeout(1200); await shot("location-confirm");
  await p.fill("#sc", "Aurangabad"); await p.waitForTimeout(1200); await shot("location-choices");
  await p.request.post(`${WEB}/api/auth/demo-login`, { data: { username: "student" } });
  await p.goto(WEB + "/welcome"); await p.waitForTimeout(500); await shot("welcome");
  await p.evaluate(() => localStorage.removeItem("smv_complaint_draft"));
  await p.goto(WEB + "/file"); await p.waitForTimeout(600);
  await p.getByRole("button", { name: "Next" }).click(); await shot("complaint-step1-errors");
  await p.getByText("Fees and refunds").click();
  await p.fill("#desc", "The college took Rs 30,000 extra as a hostel fee this year and gave no receipt.");
  await shot("complaint-step1");
  await p.getByRole("button", { name: "Next" }).click(); await p.waitForTimeout(200); await shot("complaint-step2");
  await p.getByRole("button", { name: /Skip and continue|Next/ }).click(); await p.waitForTimeout(200); await shot("complaint-step3");
  await p.getByRole("button", { name: "Submit complaint" }).click(); await p.waitForURL(/\/done$/); await p.waitForTimeout(600); await shot("complaint-result");
  await p.getByRole("link", { name: "Track this complaint" }).click(); await p.waitForTimeout(800); await shot("tracking");
  await ctx.close();
}
await browser.close();
console.log("saved to", out);
