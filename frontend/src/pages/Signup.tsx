import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp, type Me } from "../app";
import { PasswordInput } from "./Login";

export type Place = { city: string; district: string; sub_region: string; state: string; region: string; line: string };
export type Resolved = Place & { status: "matched" | "ambiguous" | "none"; source: string; choices: Place[]; pin: string };
export type Picked = { city?: string; district: string; state: string; source: "picked" | "manual" } | null;

const TYPES = ["Student", "Faculty", "Parent", "Institution staff", "Other"];

export function strength(pw: string): { score: number; label: string } {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[A-Za-z]/.test(pw) && /\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return { score: s, label: ["Too short", "Weak", "Fair", "Good", "Strong"][s] };
}

/** "Pune, Pune district, Maharashtra, Western region. Is this right? [Yes] [Change]" */
export function LocationConfirm({ city, pin, onChange }: { city: string; pin: string; onChange: (p: { picked: Picked; ok: boolean; line: string }) => void }) {
  const { t } = useApp();
  const [r, setR] = useState<Resolved | null>(null);
  const [mode, setMode] = useState<"ask" | "yes" | "change">("ask");
  const [states, setStates] = useState<string[]>([]);
  const [dists, setDists] = useState<string[]>([]);
  const [st, setSt] = useState("");
  const [di, setDi] = useState("");
  const cb = useRef(onChange);
  cb.current = onChange;
  useEffect(() => {
    if (!city.trim() && pin.replace(/\D/g, "").length < 6) { setR(null); return; }
    const id = setTimeout(() => {
      api<Resolved>(`/public/location?city=${encodeURIComponent(city)}&pin=${encodeURIComponent(pin)}`).then((x) => {
        setR(x); setMode("ask"); cb.current({ picked: null, ok: false, line: x.line || "" });
      }).catch(() => setR(null));
    }, 350);
    return () => clearTimeout(id);
  }, [city, pin]);
  useEffect(() => { if (mode === "change" || r?.status === "none") api<string[]>("/public/states").then(setStates).catch(() => {}); }, [mode, r?.status]);
  useEffect(() => { if (st) api<string[]>(`/public/districts?state=${encodeURIComponent(st)}`).then(setDists).catch(() => {}); }, [st]);
  if (!r) return null;
  const choose = (p: Place) => { setMode("yes"); cb.current({ picked: { city: p.city, district: p.district, state: p.state, source: "picked" }, ok: true, line: p.line }); };
  const manual = (
    <div className="fields2" style={{ marginTop: 8 }}>
      <div className="field"><label htmlFor="lst">{t("State")}</label>
        <select id="lst" value={st} onChange={(e) => { setSt(e.target.value); setDi(""); }}><option value="">{t("Choose")}</option>{states.map((s) => <option key={s}>{s}</option>)}</select></div>
      <div className="field"><label htmlFor="ldi">{t("District")}</label>
        <select id="ldi" value={di} disabled={!st} onChange={(e) => { setDi(e.target.value); if (e.target.value) { setMode("yes"); cb.current({ picked: { city: city.trim(), district: e.target.value, state: st, source: "manual" }, ok: true, line: `${city.trim() || e.target.value}, ${e.target.value} district, ${st}` }); } }}>
          <option value="">{t("Choose")}</option>{dists.map((d) => <option key={d}>{d}</option>)}</select></div>
    </div>
  );
  return (
    <div className="loc" role="status" aria-live="polite" data-testid="location">
      {r.status === "matched" && mode !== "change" && (
        <p style={{ margin: 0 }}><b>{r.line}.</b>{mode === "ask" ? <> {t("Is this right?")}{" "}
          <button type="button" className="btn-strong small" onClick={() => { setMode("yes"); cb.current({ picked: null, ok: true, line: r.line }); }}>{t("Yes")}</button>{" "}
          <button type="button" className="small" onClick={() => setMode("change")}>{t("Change")}</button></> : <> <span className="muted">✓ {t("Confirmed")}</span> <button type="button" className="btn-quiet small" onClick={() => setMode("change")}>{t("Change")}</button></>}
          {r.source === "pin" && <span className="small muted"> · {t("found from the PIN code")}</span>}</p>
      )}
      {r.status === "ambiguous" && mode !== "yes" && <>
        <p style={{ margin: "0 0 6px" }}>{t("There is more than one place called {c}. Which one?", { c: r.choices[0]?.city || city })}</p>
        <div className="stack-tight">{r.choices.map((c) => <button type="button" key={c.line} onClick={() => choose(c)} style={{ width: "100%", justifyContent: "flex-start" }}>{c.district}, {c.state}</button>)}</div>
        <button type="button" className="btn-quiet small" onClick={() => setMode("change")}>{t("None of these")}</button>
      </>}
      {r.status === "ambiguous" && mode === "yes" && <p style={{ margin: 0 }}>✓ {t("Confirmed")} <button type="button" className="btn-quiet small" onClick={() => setMode("change")}>{t("Change")}</button></p>}
      {(r.status === "none" || mode === "change") && <>
        <p style={{ margin: 0 }}>{r.status === "none" ? t("We could not find this place. Please choose your state and district.") : t("Choose your state and district.")}</p>
        {manual}
      </>}
    </div>
  );
}

type College = { id: number; name: string; city: string; state: string };

export function CollegePicker({ value, onPick }: { value: { id: number | null; name: string; notListed: boolean }; onPick: (v: { id: number | null; name: string; notListed: boolean }) => void }) {
  const { t } = useApp();
  const [list, setList] = useState<College[]>([]);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (value.id || value.name.trim().length < 2) { setList([]); setOpen(false); return; }
    const id = setTimeout(() => api<College[]>(`/public/colleges?q=${encodeURIComponent(value.name)}`).then((x) => { setList(x); setOpen(true); }).catch(() => {}), 250);
    return () => clearTimeout(id);
  }, [value.name, value.id]);
  return (
    <div className="rel">
      <input id="college" role="combobox" aria-expanded={open} aria-autocomplete="list" autoComplete="off" value={value.name}
        onChange={(e) => onPick({ id: null, name: e.target.value, notListed: false })} placeholder={t("Start typing, e.g. Narmada Institute")} />
      {open && !value.id && !value.notListed && value.name.trim().length >= 2 && (
        <div className="menu" role="listbox" style={{ left: 0, right: 0, top: 48 }}>
          {list.map((c) => <button type="button" role="option" aria-selected={false} key={c.id} onClick={() => { onPick({ id: c.id, name: c.name, notListed: false }); setOpen(false); }}>
            <span>{c.name}<span className="small muted"> · {c.city}{c.state ? `, ${c.state}` : ""}</span></span></button>)}
          <button type="button" role="option" aria-selected={false} onClick={() => { onPick({ id: null, name: value.name, notListed: true }); setOpen(false); }}><b>{t("My college is not listed")}</b></button>
        </div>
      )}
      {value.id && <p className="hint">✓ {t("Found on the AICTE register.")} <button type="button" className="btn-quiet small" onClick={() => onPick({ id: null, name: "", notListed: false })}>{t("Change")}</button></p>}
      {value.notListed && <p className="hint">{t("We will add your college as new. AICTE will check it.")}</p>}
    </div>
  );
}

export default function Signup() {
  const { t } = useApp();
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [f, setF] = useState({ name: "", email: "", mobile: "", password: "", user_type: "", aicte_id: "", city: "", pin: "" });
  const [college, setCollege] = useState<{ id: number | null; name: string; notListed: boolean }>({ id: null, name: "", notListed: false });
  const [loc, setLoc] = useState<{ picked: Picked; ok: boolean; line: string }>({ picked: null, ok: false, line: "" });
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const up = (k: string, v: string) => { setF({ ...f, [k]: v }); setErrs({ ...errs, [k]: "" }); };
  const pw = strength(f.password);

  const check1 = () => {
    const e: Record<string, string> = {};
    if (f.name.trim().length < 2) e.name = t("Please write your full name.");
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(f.email.trim())) e.email = t("This does not look like an email address.");
    if (f.mobile && !/^(\+91[\s-]?)?[6-9]\d{9}$/.test(f.mobile.trim())) e.mobile = t("Mobile number should be 10 digits, starting with 6, 7, 8 or 9.");
    if (f.password.length < 8 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) e.password = t("Use at least 8 characters, with letters and a number.");
    if (!f.user_type) e.user_type = t("Tell us who you are.");
    setErrs(e);
    return !Object.keys(e).length;
  };
  const submit = async () => {
    const e: Record<string, string> = {};
    if (!college.id && college.name.trim().length < 3 && !f.aicte_id.trim()) e.college = t("Type your college's name.");
    if (f.pin && !/^\d{6}$/.test(f.pin)) e.pin = t("A PIN code has 6 digits.");
    setErrs(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      await api("/auth/signup", { body: { name: f.name, email: f.email, mobile: f.mobile, password: f.password, user_type: f.user_type,
        college_id: college.id, college_name: college.id ? "" : college.name, aicte_id: f.aicte_id, city_entered: f.city, pin: f.pin,
        picked: loc.picked } });
      nav(`/verify?email=${encodeURIComponent(f.email.trim().toLowerCase())}`);
    } catch (x: any) {
      const field = x.detail?.field;
      if (["name", "email", "password", "user_type", "mobile"].includes(field)) setStep(1);
      setErrs({ [field || "form"]: t(x.message) });
    } finally { setBusy(false); }
  };
  const fe = (k: string) => errs[k] ? <p className="err" id={`${k}-err`}>{errs[k]}</p> : null;

  return (
    <main id="main" className="center-page">
      <div className="auth-card card wide" data-testid="signup">
        <p className="small muted" aria-live="polite">{t("Step {n} of 2", { n: step })}</p>
        <div className="steps-head" aria-hidden="true"><span className={step === 1 ? "on" : "done"}>{t("About you")}</span><span className={step === 2 ? "on" : ""}>{t("Your college")}</span></div>
        {step === 1 ? <>
          <h1>{t("About you")}</h1>
          <div className="field"><label htmlFor="sn">{t("Full name")}</label><input id="sn" value={f.name} onChange={(e) => up("name", e.target.value)} aria-invalid={!!errs.name || undefined} />{fe("name")}</div>
          <div className="field"><label htmlFor="se">{t("Email")}</label><input id="se" type="email" value={f.email} onChange={(e) => up("email", e.target.value)} aria-invalid={!!errs.email || undefined} />
            <div className="hint">{t("We send a 6-digit code here to check it is yours.")}</div>{fe("email")}</div>
          <div className="field"><label htmlFor="sm">{t("Mobile (optional)")}</label><input id="sm" inputMode="tel" value={f.mobile} onChange={(e) => up("mobile", e.target.value)} />
            <div className="hint">{t("Only AICTE officers can see it. We do not send SMS yet.")}</div>{fe("mobile")}</div>
          <div className="field"><label htmlFor="sp">{t("Password")}</label><PasswordInput id="sp" value={f.password} onChange={(v) => up("password", v)} auto="new-password" invalid={!!errs.password} />
            {f.password && <div className="hint" aria-live="polite">{t("Strength")}: <b>{t(pw.label)}</b></div>}
            <div className="hint">{t("At least 8 characters, with letters and a number.")}</div>{fe("password")}</div>
          <fieldset className="field"><legend>{t("I am a:")}</legend>
            <div className="radio-row">{TYPES.map((x) => <label key={x}><input type="radio" name="ut" checked={f.user_type === x} onChange={() => up("user_type", x)} />{t(x)}</label>)}</div>{fe("user_type")}</fieldset>
          <button className="btn-primary btn-big" style={{ width: "100%" }} onClick={() => check1() && setStep(2)}>{t("Next")}</button>
        </> : <>
          <h1>{t("Your college")}</h1>
          <div className="field"><label htmlFor="college">{t("College name")}</label>
            <CollegePicker value={college} onPick={(v) => { setCollege(v); setErrs({ ...errs, college: "" }); }} />
            <div className="hint">{t("Pick it from the list as you type. If it is not there, choose \"My college is not listed\".")}</div>{fe("college")}</div>
          <div className="field"><label htmlFor="sa">{t("AICTE ID (optional)")}</label><input id="sa" value={f.aicte_id} onChange={(e) => up("aicte_id", e.target.value)} placeholder="1-1234567890" />
            <details className="hint"><summary>{t("Where do I find this?")}</summary>{t("It is printed on the college's AICTE approval letter and on the college website's 'Mandatory disclosure' page. Leave it empty if you do not know it.")}</details></div>
          <div className="fields2">
            <div className="field"><label htmlFor="sc">{t("City or town")}</label><input id="sc" value={f.city} onChange={(e) => up("city", e.target.value)} placeholder={t("e.g. Pune")} />
              <div className="hint">{t("Where the college is. Old names like Poona or Bombay are fine.")}</div></div>
            <div className="field"><label htmlFor="spn">{t("PIN code (optional)")}</label><input id="spn" inputMode="numeric" maxLength={6} value={f.pin} onChange={(e) => up("pin", e.target.value.replace(/\D/g, ""))} />
              <div className="hint">{t("If you give it, we use it to find the place.")}</div>{fe("pin")}</div>
          </div>
          <LocationConfirm city={f.city} pin={f.pin} onChange={setLoc} />
          {errs.form && <p className="err" role="alert">{errs.form}</p>}
          <div className="row" style={{ marginTop: 16 }}>
            <button onClick={() => setStep(1)}>{t("Back")}</button>
            <button className="btn-primary btn-big" style={{ flex: 1 }} disabled={busy} onClick={submit}>{t("Create my account")}</button>
          </div>
          <p className="small muted" style={{ marginTop: 8 }}>{t("Your place helps AICTE send the complaint to the right office. It never stops you from signing up.")}</p>
        </>}
        <p className="small" style={{ marginTop: 14 }}>{t("Already have an account?")} <Link to="/login">{t("Sign in")}</Link></p>
      </div>
    </main>
  );
}

export function Verify() {
  const { t, setMe } = useApp();
  const nav = useNavigate();
  const [q] = useSearchParams();
  const email = q.get("email") || "";
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [wait, setWait] = useState(60);
  useEffect(() => { const id = setInterval(() => setWait((w) => Math.max(0, w - 1)), 1000); return () => clearInterval(id); }, []);
  const finish = (u: Me) => { setMe(u); nav("/welcome", { replace: true }); };
  useEffect(() => {
    const token = q.get("token");
    if (token) api<{ user: Me }>("/auth/verify", { body: { token } }).then((r) => finish(r.user)).catch((x) => setErr(x.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <main id="main" className="center-page">
      <div className="auth-card card">
        <h1>{t("Check your email")}</h1>
        <p>{t("We sent a 6-digit code to {e}. It works for 30 minutes.", { e: email })}</p>
        <form onSubmit={async (e) => { e.preventDefault(); setErr(""); try { finish((await api<{ user: Me }>("/auth/verify", { body: { email, code } })).user); } catch (x: any) { setErr(x.message); } }}>
          <div className="field"><label htmlFor="vc">{t("6-digit code")}</label>
            <input id="vc" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} style={{ fontSize: "1.4rem", letterSpacing: ".3em" }} /></div>
          {err && <p className="err" role="alert">{t(err)}</p>}
          {msg && <p className="note">{t(msg)}</p>}
          <button className="btn-primary btn-big" style={{ width: "100%" }} disabled={code.length !== 6}>{t("Verify and continue")}</button>
        </form>
        <p className="small" style={{ marginTop: 12 }}>
          {wait > 0 ? t("You can ask for a new code in {n} seconds.", { n: wait }) :
            <button className="btn-quiet small" onClick={async () => { setErr(""); try { setMsg((await api<{ message: string }>("/auth/resend", { body: { email } })).message); setWait(60); } catch (x: any) { setErr(x.message); } }}>{t("Send a new code")}</button>}
        </p>
        <p className="small muted">{t("Did not get it? Check the spam folder. You can ask for up to 5 codes an hour.")}</p>
      </div>
    </main>
  );
}

export function Welcome() {
  const { me, t } = useApp();
  return (
    <main id="main" className="center-page">
      <div className="auth-card card wide" style={{ textAlign: "center" }}>
        <h1>{t("What do you want to do?")}</h1>
        {me?.institution && <p className="muted">{me.institution.name}{me.institution.link === "pending" && ` · ${t("link waiting for AICTE to confirm")}`}</p>}
        <div className="big-choices">
          <Link className="btn btn-primary btn-huge" to="/file">{t("File a complaint")}</Link>
          <Link className="btn btn-strong btn-huge" to="/my">{t("Track my complaint")}</Link>
        </div>
      </div>
    </main>
  );
}
