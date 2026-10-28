// Layout audit: every page at phone, tablet and laptop widths. Fails on horizontal page scroll
// or any visible element sticking out of the screen. node scripts/fit-check.mjs
import { chromium } from "@playwright/test";
const WEB = process.env.WEB || "http://localhost:5173";
const WIDTHS = [320, 360, 390, 768, 1024, 1280, 1440];
const PAGES = [
  [null, "/login"], [null, "/signup"], [null, "/verify?email=a@b.co"], [null, "/check/RB-2026-0001"], [null, "/about"], [null, "/forgot"],
  ["student", "/welcome"], ["student", "/file"], ["student", "/my"],
  ["officer", "/today"], ["officer", "/cases?status=OPEN"], ["officer", "/cases/RB-2026-0023"], ["officer", "/institutions"],
  ["officer", "/institutions/1"], ["coordinator", "/overlaps"], ["coordinator", "/overlaps/1"], ["management", "/dashboard"],
  ["management", "/reports"], ["admin", "/admin"], ["admin", "/emails"], ["management", "/audit"], ["officer", "/inbox"], ["officer", "/calendar"],
];
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome" });
let bad = 0;
for (const [user, path] of PAGES) {
  const ctx = await browser.newContext();
  if (user) {
    await ctx.request.post(`${WEB}/api/auth/demo-login`, { data: { username: user } });
    await ctx.request.post(`${WEB}/api/auth/tour-done`, { headers: { "X-Requested-With": "samanvay" } });
  }
  const page = await ctx.newPage();
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto(WEB + path); await page.waitForTimeout(700);
    const r = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const scroll = document.documentElement.scrollWidth - vw;
      const out = [];
      for (const el of document.querySelectorAll("body *")) {
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden" || el.closest(".scroll-x, .sr-only, .skip, [aria-hidden=true]")) continue;
        const b = el.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) continue;
        let box = el.parentElement;
        while (box && box !== document.body && !["hidden", "clip"].includes(getComputedStyle(box).overflowX)) box = box.parentElement;
        if (box && box !== document.body && !el.closest(".stamp") && !box.closest(".scroll-x")) {
          const p = box.getBoundingClientRect();
          if (b.right > p.right + 2 && b.left < p.right) out.push(`clipped ${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]} in ${box.tagName.toLowerCase()}.${(box.className || "").toString().split(" ")[0]}`);
        }
        if (b.right > vw + 1 || b.left < -1) out.push(`${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]} ${Math.round(b.left)}..${Math.round(b.right)}`);
      }
      return { scroll, out: out.slice(0, 4) };
    });
    if (r.scroll > 0 || r.out.length) { bad++; console.log(`BAD ${w}px ${path}: page scroll ${r.scroll}px; ${r.out.join(" | ")}`); }
  }
  await ctx.close();
}
await browser.close();
console.log(bad ? `${bad} page/width combinations need fixing` : `All ${PAGES.length} pages fit at ${WIDTHS.join(", ")} px`);
process.exit(bad ? 1 : 0);
