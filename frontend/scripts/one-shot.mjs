// node scripts/one-shot.mjs <user|-> <path> <width> <file>
import { chromium } from "@playwright/test";
const [user, path, w, file] = process.argv.slice(2);
const WEB = process.env.WEB || "http://localhost:5173";
const b = await chromium.launch({ channel: "chrome" });
const ctx = await b.newContext({ viewport: { width: Number(w), height: 900 } });
if (user !== "-") { await ctx.request.post(`${WEB}/api/auth/demo-login`, { data: { username: user } });
  await ctx.request.post(`${WEB}/api/auth/tour-done`, { headers: { "X-Requested-With": "samanvay" } }); }
const p = await ctx.newPage(); await p.goto(WEB + path); await p.waitForTimeout(900);
await p.screenshot({ path: file }); await b.close();
