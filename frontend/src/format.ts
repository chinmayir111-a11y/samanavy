// Indian number formatting and plain dates: ₹ 50,00,000 and 14 Dec 2026.
export function rupees(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const s = Math.round(Math.abs(n)).toString();
  const out = s.length > 3 ? s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + s.slice(-3) : s;
  return (n < 0 ? "-" : "") + "₹ " + out;
}
export function crore(n: number, t: (k: string, p?: any) => string = (k, p) => k.replace("{n}", p.n)): string {
  if (n >= 1e7) return `₹ ${t("{n} crore", { n: (n / 1e7).toFixed(2) })}`;
  if (n >= 1e5) return `₹ ${t("{n} lakh", { n: (n / 1e5).toFixed(1) })}`;
  return rupees(n);
}
const MONTHS: Record<string, string[]> = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  hi: ["जन॰", "फ़र॰", "मार्च", "अप्रैल", "मई", "जून", "जुल॰", "अग॰", "सित॰", "अक्टू॰", "नव॰", "दिस॰"],
};
let LANG: "en" | "hi" = "en";
/** Set by the app when the language changes, so dates follow the EN | हि switch. */
export function setFormatLang(l: "en" | "hi") { LANG = l; }
export function day(d: string | null | undefined): string {
  if (!d) return "—";
  const [y, m, dd] = d.slice(0, 10).split("-").map(Number);
  return `${dd} ${MONTHS[LANG][m - 1]} ${y}`;
}
export function dateTime(d: string | null | undefined): string {
  if (!d) return "—";
  const x = new Date(d);
  return `${x.getDate()} ${MONTHS[LANG][x.getMonth()]} ${x.getFullYear()}, ${x.toLocaleTimeString(LANG === "hi" ? "hi-IN" : "en-IN", { hour: "2-digit", minute: "2-digit" })}`;
}
export function plural(n: number, one: string, many?: string) {
  return `${n} ${n === 1 ? one : many || one + "s"}`;
}
