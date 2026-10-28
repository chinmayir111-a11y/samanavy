import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { api } from "../api";
import { useApp, type Role } from "../app";
import { day } from "../format";

// At most four items per role; everything else is in the account menu.
const NAV: Record<Role, [string, string][]> = {
  desk_officer: [["/today", "Today's register"], ["/cases", "Cases"], ["/institutions", "Institutions"], ["/overlaps", "Overlaps"]],
  unit_head: [["/today", "Today's register"], ["/cases", "Cases"], ["/institutions", "Institutions"], ["/overlaps", "Overlaps"]],
  coordinator: [["/today", "Today's register"], ["/overlaps", "Overlaps"], ["/institutions", "Institutions"], ["/cases", "Cases"]],
  management: [["/dashboard", "Dashboard"], ["/reports", "Reports"], ["/institutions", "Institutions"], ["/audit", "Audit log"]],
  admin: [["/admin", "Admin"], ["/emails", "Email log"], ["/audit", "Audit log"], ["/dashboard", "Dashboard"]],
  college: [["/file", "File a complaint"], ["/my", "My complaints"]],
};
const MENU: Record<Role, [string, string][]> = {
  desk_officer: [["/dashboard", "Dashboard"], ["/calendar", "Due-date calendar"], ["/reports", "Reports"], ["/audit", "Audit log"]],
  unit_head: [["/dashboard", "Dashboard"], ["/calendar", "Due-date calendar"], ["/reports", "Reports"], ["/audit", "Audit log"]],
  coordinator: [["/dashboard", "Dashboard"], ["/reports", "Reports"], ["/emails", "Email log"], ["/audit", "Audit log"]],
  management: [["/cases", "Cases"], ["/overlaps", "Overlaps"], ["/emails", "Email log"]],
  admin: [["/cases", "Cases"], ["/institutions", "Institutions"], ["/reports", "Reports"]],
  college: [["/welcome", "Home"]],
};

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" fill="#122619" />
      <circle cx="12" cy="16" r="6" fill="none" stroke="#F7F8F3" strokeWidth="2" />
      <circle cx="20" cy="16" r="6" fill="none" stroke="#7FA18C" strokeWidth="2" /></svg>
  );
}

export function DemoBar() {
  const { clock, t } = useApp();
  return (
    <div className="demo-bar" role="status">
      <div className="wrap">
        <b>{t("Synthetic data")}</b>
        {clock && clock.offset_days > 0 && <span><b>{t("DEMO CLOCK")}</b> {t("System date {date} (+{n} days).", { date: day(clock.today), n: clock.offset_days })}</span>}
      </div>
    </div>
  );
}

export function Toasts() {
  const { toasts } = useApp();
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((x) => <div key={x.id} className={`toast ${x.bad ? "bad" : ""}`} role={x.bad ? "alert" : "status"}>{x.text}</div>)}
    </div>
  );
}

export function LangSwitch() {
  const { lang, setLang } = useApp();
  return (
    <div className="lang" role="group" aria-label="Language / भाषा">
      <button aria-pressed={lang === "en"} lang="en" onClick={() => setLang("en")} aria-label="English">EN</button>
      <button aria-pressed={lang === "hi"} lang="hi" onClick={() => setLang("hi")} aria-label="हिंदी">हि</button>
    </div>
  );
}

function UserMenu() {
  const { me, t, signOut, setTour } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    const f = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("click", f);
    return () => document.removeEventListener("click", f);
  }, []);
  if (!me) return null;
  const initials = me.name.split(" ").map((x) => x[0]).join("").slice(0, 2);
  return (
    <div className="rel" ref={ref}>
      <button aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(!open)} aria-label={t("Account menu for {name}", { name: me.name })}>
        <span className="serif" style={{ fontWeight: 600 }}>{initials}</span>
      </button>
      {open && (
        <div className="menu" role="menu">
          <div style={{ padding: "8px 12px" }}><b>{me.name}</b><div className="small muted">{t(me.title)}</div></div>
          {MENU[me.role].map(([to, k]) => <Link key={to} role="menuitem" to={to}>{t(k)}</Link>)}
          <Link role="menuitem" to="/about">{t("About this demo")}</Link>
          {me.role !== "college" && <button role="menuitem" onClick={() => { setOpen(false); setTour(true); }}>{t("Show the 60-second tour")}</button>}
          <button role="menuitem" onClick={signOut}>{t("Sign out")}</button>
        </div>
      )}
    </div>
  );
}

function InboxLink() {
  const { me, t } = useApp();
  const [n, setN] = useState(0);
  const loc = useLocation();
  useEffect(() => {
    if (!me || me.role === "college") return;
    api<{ read: boolean }[]>("/inbox").then((r) => setN(r.filter((x) => !x.read).length)).catch(() => {});
  }, [me, loc.pathname]);
  if (!me || me.role === "college") return null;
  return <Link className="btn icon-btn" to="/inbox" aria-label={t("Messages, {n} unread", { n })}>{t("Inbox")}{n > 0 && <span className="count">{n}</span>}</Link>;
}

export function Header() {
  const { me, t, large, setLarge, lang } = useApp();
  return (
    <header className="top">
      <div className="wrap">
        <Link to={me ? "/" : "/login"} className="brand" aria-label={t("SAMANVAY home")}>
          <Logo />
          <span>SAMANVAY<small>{t("One institution. One view. No duplicate action.")}</small></span>
        </Link>
        {me && NAV[me.role] && (
          <nav className="main" aria-label={t("Main")}>
            {NAV[me.role].map(([to, k]) => <NavLink key={to} to={to}>{t(k)}</NavLink>)}
          </nav>
        )}
        <div className="tools">
          {lang === "hi" && <span className="pill-hi">{t("Hindi translation under review")}</span>}
          <LangSwitch />
          <button className="icon-btn" aria-pressed={large} onClick={() => setLarge(!large)} aria-label={t("Larger text")}>A+</button>
          <InboxLink />
          <UserMenu />
          {!me && <Link className="btn btn-quiet" to="/login">{t("Sign in")}</Link>}
        </div>
      </div>
    </header>
  );
}

const TOUR = [
  { title: "Today's register", text: "The cases that need you today, most urgent first. The box at the top says what to do now." },
  { title: "One institution, one view", text: "Open any institution to see every case across RB, PGRC, AB and Legal Cell, who holds each one and for how long." },
  { title: "Overlap alerts", text: "When two units handle the same institution, SAMANVAY shows why it thinks so, with a score from transparent rules. People decide." },
  { title: "Conflict guard", text: "Before a show-cause notice or penalty, you see other units' open cases on the institution. You can continue; your reason is logged." },
  { title: "Deadlines and the log", text: "SLA chips count down; overdue cases move up the ladder by email. Every action is chained in the audit log, which anyone can verify." },
];

export function Tour() {
  const { me, tour, setTour, setMe, t } = useApp();
  const [i, setI] = useState(0);
  useEffect(() => { if (tour) setI(0); }, [tour]);
  if (!tour || !me || me.role === "college") return null;
  const done = () => {
    setTour(false);
    if (!me.tour_done) { api("/auth/tour-done", { method: "POST" }).catch(() => {}); setMe({ ...me, tour_done: true }); }
  };
  const s = TOUR[i];
  return (
    <div className="modal-back">
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("Guided tour")}>
        <p className="small muted">{t("Step {n} of {total} · about 60 seconds", { n: i + 1, total: TOUR.length })}</p>
        <h2>{t(s.title)}</h2>
        <p>{t(s.text)}</p>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 16 }}>
          <button className="btn-quiet" onClick={done}>{t("Skip tour")}</button>
          <div className="row">
            {i > 0 && <button onClick={() => setI(i - 1)}>{t("Back")}</button>}
            {i < TOUR.length - 1 ? <button className="btn-primary" autoFocus onClick={() => setI(i + 1)}>{t("Next")}</button>
              : <button className="btn-primary" autoFocus onClick={done}>{t("Start using SAMANVAY")}</button>}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Page({ children }: { children: ReactNode }) {
  const { t, me } = useApp();
  if (me?.role === "college") return <main id="main"><div className="wrap">{children}</div></main>;
  return (
    <>
      <main id="main"><div className="wrap">{children}</div></main>
      <footer className="sig"><div className="wrap">{t("Every change is chained in the audit log.")} <Link to="/audit">{t("Verify the log")}</Link>.</div></footer>
    </>
  );
}
