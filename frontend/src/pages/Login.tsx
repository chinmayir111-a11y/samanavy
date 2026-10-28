import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp, type Me } from "../app";
import { Logo } from "../components/Shell";
import { HOME } from "../home";

type Demo = { username: string; name: string; title: string; role: string; unit: string | null; sees: string };
const ROLE: Record<string, string> = { desk_officer: "Desk Officer", unit_head: "Unit Head", coordinator: "Coordinator",
  management: "Management", admin: "Admin", college: "College user" };

export function PasswordInput({ id, value, onChange, auto, invalid }: { id: string; value: string; onChange: (v: string) => void; auto: string; invalid?: boolean }) {
  const { t } = useApp();
  const [show, setShow] = useState(false);
  return (
    <div className="pw">
      <input id={id} type={show ? "text" : "password"} autoComplete={auto} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={invalid || undefined} />
      <button type="button" className="btn-quiet" onClick={() => setShow(!show)} aria-pressed={show} aria-controls={id}>{show ? t("Hide") : t("Show")}</button>
    </div>
  );
}

/** Sign in first. Order: logo + line, sign-in form, create-account link, demo dropdown, quiet links. */
export default function Login() {
  const { me, setMe, t, setTour } = useApp();
  const nav = useNavigate();
  const [q] = useSearchParams();
  const [demo, setDemo] = useState<Demo[]>([]);
  const [pick, setPick] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ text: string; code?: string } | null>(null);
  useEffect(() => { api<Demo[]>("/auth/demo-accounts").then(setDemo).catch(() => {}); }, []);
  useEffect(() => { if (me) nav(HOME[me.role], { replace: true }); }, [me, nav]);

  const done = (u: Me) => { setMe(u); if (!u.tour_done && u.role !== "college") setTour(true); nav(HOME[u.role], { replace: true }); };
  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) { setErr({ text: t("Type your email and password.") }); return; }
    setBusy(true); setErr(null);
    try { done((await api<{ user: Me }>("/auth/login", { body: { email, password } })).user); }
    catch (x: any) { setErr({ text: x.message, code: x.code }); } finally { setBusy(false); }
  };
  const chosen = demo.find((d) => d.username === pick);
  const oneTap = async () => {
    if (!chosen) return;
    try { done((await api<{ user: Me }>("/auth/demo-login", { body: { username: chosen.username } })).user); }
    catch (x: any) { setErr({ text: x.message }); }
  };

  return (
    <main id="main" className="center-page">
      <div className="auth-card card">
        <div className="auth-brand"><Logo size={40} /><div><div className="serif" style={{ fontSize: "1.4rem", fontWeight: 600, letterSpacing: ".06em" }}>SAMANVAY</div>
          <p className="muted" style={{ margin: 0 }}>{t("Every complaint about a college, in one place.")}</p></div></div>
        {q.get("expired") && <p className="note">{t("Your session ended. Please sign in again.")}</p>}
        <form onSubmit={signIn} noValidate data-testid="signin">
          <div className="field"><label htmlFor="em">{t("Email")}</label>
            <input id="em" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div className="field">
            <div className="spread"><label htmlFor="pw">{t("Password")}</label><Link className="small" to="/forgot">{t("Forgot password")}</Link></div>
            <PasswordInput id="pw" value={password} onChange={setPassword} auto="current-password" />
          </div>
          {err && <p className="err" role="alert">{t(err.text)}{err.code === "unverified" && <> <Link to={`/verify?email=${encodeURIComponent(email)}`}>{t("Enter the code")}</Link></>}</p>}
          <button className="btn-primary" style={{ width: "100%" }} disabled={busy}>{t("Sign in")}</button>
        </form>
        <p style={{ marginTop: 14 }}>{t("New here?")} <Link to="/signup">{t("Create an account")}</Link></p>
        <p className="small muted" style={{ margin: 0 }}>{t("Officers are added by the AICTE admin.")}</p>
        {demo.length > 0 && <>
          <div className="or">{t("or")}</div>
          <div className="field" data-testid="demo">
            <label htmlFor="demo">{t("Try a demo account")}</label>
            <select id="demo" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">{t("Choose a role")}</option>
              {demo.map((d) => <option key={d.username} value={d.username}>{[t(ROLE[d.role]), d.name, d.unit].filter(Boolean).join(", ")}</option>)}
            </select>
            {chosen && <p className="hint">{t("You will see:")} {t(chosen.sees)}</p>}
          </div>
          <button className="btn-strong" style={{ width: "100%" }} disabled={!chosen} onClick={oneTap}>{t("Continue as this role")}</button>
          <p className="small muted" style={{ marginTop: 6 }}>{t("No password needed for demo accounts.")}</p>
        </>}
      </div>
      <p className="small auth-links"><Link to="/check">{t("Check a complaint's status")}</Link> · <Link to="/about">{t("What is real and what is simulated")}</Link></p>
    </main>
  );
}

export function SetPassword() {
  const { setMe, t } = useApp();
  const nav = useNavigate();
  const [q] = useSearchParams();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const r = await api<{ user: Me }>("/auth/set-password", { body: { token: q.get("token") || "", password: pw } });
      setMe(r.user); nav(HOME[r.user.role], { replace: true });
    } catch (x: any) { setErr(x.message); }
  };
  return (
    <main id="main" className="center-page">
      <div className="auth-card card">
        <h1>{t("Choose your password")}</h1>
        <form onSubmit={go}>
          <div className="field"><label htmlFor="np">{t("New password")}</label>
            <PasswordInput id="np" value={pw} onChange={setPw} auto="new-password" />
            <div className="hint">{t("At least 8 characters, with letters and a number.")}</div></div>
          {err && <p className="err" role="alert">{t(err)}</p>}
          <button className="btn-primary">{t("Save and sign in")}</button>
        </form>
      </div>
    </main>
  );
}

export function Forgot() {
  const { t } = useApp();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  return (
    <main id="main" className="center-page">
      <div className="auth-card card">
        <h1>{t("Forgot password")}</h1>
        <p className="muted">{t("We will email you a link to choose a new password.")}</p>
        <form onSubmit={async (e) => { e.preventDefault(); setMsg((await api<{ message: string }>("/auth/forgot", { body: { email } }).catch((x) => ({ message: x.message }))).message); }}>
          <div className="field"><label htmlFor="fe">{t("Email")}</label><input id="fe" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          {msg && <p className="note">{t(msg)}</p>}
          <button className="btn-primary" disabled={!email.trim()}>{t("Send the link")}</button>
        </form>
        <p className="small" style={{ marginTop: 12 }}><Link to="/login">{t("Back to sign in")}</Link></p>
      </div>
    </main>
  );
}
