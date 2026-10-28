// No Smart India Hackathon logo, badge or name anywhere in what the website serves.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(__dirname, "..");
const BANNED = /smart\s*india\s*hackathon|\bSIH(\d{2,5})?\b|sih[-_ ]?(logo|badge)/i;

function files(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}

test("no SIH logo, badge or name in source, public assets, index.html or the built site", () => {
  const all = [...files(join(ROOT, "src")), ...files(join(ROOT, "public")), join(ROOT, "index.html"), ...files(join(ROOT, "dist"))]
    .filter((f) => !f.endsWith("no-sih.test.ts"));
  expect(all.length).toBeGreaterThan(20);
  const hits = all.filter((f) => /sih/i.test(f.split("/").pop()!) || (/\.(tsx?|jsx?|json|html|css|svg|txt|md)$/.test(f) && BANNED.test(readFileSync(f, "utf8"))));
  expect(hits).toEqual([]);
});
