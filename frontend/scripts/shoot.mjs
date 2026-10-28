// Screenshot the main pages at 1440 and 390 px: node scripts/shoot.mjs <outdir> [wide|narrow]
import { chromium } from "@playwright/test";
const out = process.argv[2] || "../screenshots";
const WEB = process.env.WEB || "http://localhost:5173";
const PAGES = [
  ["login", null, "/login"], ["today-officer", "officer", "/today"], ["case-narmada", "officer", "/cases?q=Narmada&status=OPEN", "first"],
  ["institution-360", "coordinator", "/institutions", "narmada"], ["overlap-explainer", "coordinator", "/overlaps", "firstcard"],
  ["dashboard", "management", "/dashboard"], ["cases", "officer", "/cases?status=OPEN"], ["admin", "admin", "/admin"],
  ["audit", "management", "/audit"], ["about", null, "/about"],
];
const widths = process.argv[3] === "narrow" ? [390] : process.argv[3] === "wide" ? [1440] : [1440, 390];
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome" });
for (const w of widths) {
  for (const [name, user, path, click] of PAGES) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
    const page = await ctx.newPage();
    if (user) {
      await page.request.post(`${WEB}/api/auth/demo-login`, { data: { username: user } });
      await page.request.post(`${WEB}/api/auth/tour-done`, { headers: { "X-Requested-With": "samanvay" } });
    }
    await page.goto(WEB + path);
    await page.waitForTimeout(900);
    if (click === "first") { await page.locator("tr.clickable:visible, .lcard:visible").first().click(); await page.waitForTimeout(900); }
    if (click === "narmada") { await page.getByText("Narmada Institute of Technology").first().click(); await page.waitForTimeout(900); }
    if (click === "firstcard") { await page.locator("main a.card").first().click(); await page.waitForTimeout(900); }
    await page.screenshot({ path: `${out}/${name}-${w}.png`, fullPage: true });
    await ctx.close();
  }
}
await browser.close();
console.log("shots saved to", out);
