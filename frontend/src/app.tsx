import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./i18n/en.json";
import hi from "./i18n/hi.json";
import { api, setExpiredHandler } from "./api";
import { setFormatLang } from "./format";

export type Role = "desk_officer" | "unit_head" | "coordinator" | "management" | "admin" | "college";
export type Me = { id: number; username: string; email: string; name: string; title: string; role: Role;
  unit: { id: number; code: string; name: string } | null; tour_done: boolean; user_type?: string;
  institution?: { id: number; name: string; link: string; city: string; state: string } | null };
type Toast = { id: number; text: string; bad?: boolean };
type Clock = { offset_days: number; today: string; real_today: string; demo_mode: boolean };

export type T = (k: string, params?: Record<string, string | number | null | undefined>) => string;
type Ctx = {
  me: Me | null; setMe: (m: Me | null) => void; signOut: () => void; loading: boolean;
  lang: "en" | "hi"; setLang: (l: "en" | "hi") => void; t: T;
  /** A sentence written by the server: Hindi template for `key` if there is one, else the server's English text. */
  ts: (key: string | undefined, params: Record<string, any> | undefined, text: string) => string;
  large: boolean; setLarge: (b: boolean) => void;
  toast: (text: string, bad?: boolean) => void; toasts: Toast[];
  clock: Clock | null; refreshClock: () => void;
  tour: boolean; setTour: (b: boolean) => void;
};
const DICT: Record<string, Record<string, string>> = { en, hi };

/** Translate a key. Missing Hindi falls back to English; a missing key falls
 * back to `fallback` (or the key itself only as a last resort in development). */
export function translate(lang: "en" | "hi", k: string, params?: Record<string, any>, fallback?: string): string {
  let s = DICT[lang][k] ?? (en as Record<string, string>)[k] ?? fallback ?? k;
  if (params) for (const [p, v] of Object.entries(params)) s = s.split(`{${p}}`).join(v == null ? "" : String(v));
  return s;
}

export function serverText(lang: "en" | "hi", key: string | undefined, params: Record<string, any> | undefined, text: string): string {
  if (lang === "en" || !key || !(key in DICT.hi)) return text;
  return translate(lang, key, params);
}

const AppCtx = createContext<Ctx>({
  me: null, setMe: () => {}, signOut: () => {}, loading: false, lang: "en", setLang: () => {},
  t: (k, p) => translate("en", k, p), ts: (_k, _p, text) => text, large: false, setLarge: () => {}, toast: () => {}, toasts: [], clock: null,
  refreshClock: () => {}, tour: false, setTour: () => {},
});
export const useApp = () => useContext(AppCtx);
function pref(k: string, d: string) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }
function save(k: string, v: string) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [lang, setLangS] = useState<"en" | "hi">(() => { const l = pref("smv_lang", "en") === "hi" ? "hi" : "en"; setFormatLang(l); return l; });
  const [large, setLargeS] = useState(pref("smv_large", "0") === "1");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [clock, setClock] = useState<Clock | null>(null);
  const [tour, setTour] = useState(false);

  useEffect(() => { document.documentElement.lang = lang; save("smv_lang", lang); }, [lang]);
  const setLang = useCallback((l: "en" | "hi") => { setFormatLang(l); setLangS(l); }, []);
  useEffect(() => { document.documentElement.classList.toggle("large", large); save("smv_large", large ? "1" : "0"); }, [large]);
  const refreshClock = useCallback(() => { api<Clock>("/public/clock").then(setClock).catch(() => {}); }, []);
  useEffect(() => { refreshClock(); }, [refreshClock]);
  useEffect(() => {
    api<{ user: Me | null }>("/auth/session").then(({ user }) => { setMe(user); if (user && !user.tour_done) setTour(true); })
      .catch(() => setMe(null)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    setExpiredHandler(() => {
      setMe(null);
      if (!window.location.pathname.startsWith("/login")) window.location.href = "/login?expired=1";
    });
  }, []);

  const toast = useCallback((text: string, bad = false) => {
    const id = Date.now() + Math.random();
    setToasts((x) => [...x, { id, text, bad }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), bad ? 7000 : 4000);
  }, []);
  const t = useCallback<T>((k, p) => translate(lang, k, p), [lang]);
  const ts = useCallback((k: string | undefined, p: Record<string, any> | undefined, text: string) => serverText(lang, k, p, text), [lang]);
  const signOut = useCallback(() => {
    api("/auth/logout", { method: "POST" }).catch(() => {}).finally(() => { setMe(null); window.location.href = "/login?signedout=1"; });
  }, []);

  const value = useMemo(() => ({
    me, setMe, signOut, loading, lang, setLang, t, ts, large, setLarge: setLargeS, toast, toasts, clock,
    refreshClock, tour, setTour,
  }), [me, signOut, loading, lang, setLang, t, ts, large, toast, toasts, clock, refreshClock, tour]);
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

/** Load data with a loading flag and a toast on failure. Nothing fails silently. */
export function useLoad<T>(path: string | null, deps: unknown[] = []) {
  const { toast } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    api<T>(path).then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live) { setError(e.message); toast(e.message, true); } })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, n, ...deps]);
  return { data, setData, error, loading, reload: () => setN((x) => x + 1) };
}

/** Run an action, toast the result, return the response (or null). */
export function useAct() {
  const { toast } = useApp();
  const [busy, setBusy] = useState(false);
  const run = useCallback(async <T,>(fn: () => Promise<T>, ok?: string): Promise<T | null> => {
    setBusy(true);
    try {
      const r = await fn();
      if (ok) toast(ok);
      return r;
    } catch (e: any) {
      toast(e.message || "That did not work.", true);
      return null;
    } finally { setBusy(false); }
  }, [toast]);
  return { run, busy };
}
