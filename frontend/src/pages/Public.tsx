import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useApp, useLoad } from "../app";
import type { CaseRow } from "../components/CaseList";
import { Page } from "../components/Shell";
import { PageHead, Skeleton, Stamp } from "../components/ui";
import { day } from "../format";

export function PublicCheck() {
  const { ref } = useParams();
  const { t } = useApp();
  const nav = useNavigate();
  const [q, setQ] = useState(ref || "");
  const [r, setR] = useState<{ case_id: string; institution: string; status: string; last_updated: string } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!ref) return;
    setErr(""); setR(null);
    api(`/public/check/${encodeURIComponent(ref)}`).then(setR).catch((e) => setErr(e.message));
  }, [ref]);
  return (
    <Page>
      <div style={{ maxWidth: 560 }}>
        <PageHead title={t("Check a complaint's status")} sub={t("Shows only the status and the date of the last update. Names, remarks and documents are never shown here.")} />
        <form className="row" onSubmit={(e) => { e.preventDefault(); nav(`/check/${q.trim().toUpperCase()}`); }}>
          <input aria-label={t("Case number")} value={q} onChange={(e) => setQ(e.target.value)} placeholder="PGRC-2026-0012" style={{ flex: "1 1 220px", width: "auto" }} />
          <button className="btn-primary">{t("Check")}</button>
        </form>
        {err && <p className="note" style={{ marginTop: 16 }}>{err}</p>}
        {r && <div className="card" style={{ marginTop: 16 }}>
          <dl className="dl"><dt>{t("Case")}</dt><dd className="num">{r.case_id}</dd><dt>{t("Institution")}</dt><dd>{r.institution}</dd>
            <dt>{t("Status")}</dt><dd><Stamp label={r.status} kind={r.status === "Disposed" ? "done" : "wait"} /></dd><dt>{t("Last updated")}</dt><dd>{day(r.last_updated)}</dd></dl>
          <p className="small muted" style={{ marginTop: 12 }}>{t("Synthetic demo record.")}</p>
        </div>}
      </div>
    </Page>
  );
}

export function Submit() {
  const { t } = useApp();
  const cats = useLoad<{ id: number; name: string }[]>("/public/categories").data;
  const [f, setF] = useState({ institution_text: "", category_id: "", description: "", name: "", email: "" });
  const [done, setDone] = useState<{ case_id: string; message: string } | null>(null);
  const [err, setErr] = useState("");
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    try { setDone(await api("/public/complaints", { body: { ...f, category_id: Number(f.category_id) } })); } catch (x: any) { setErr(x.message); }
  };
  return (
    <Page>
      <div style={{ maxWidth: 640 }}>
        <PageHead title={t("File a complaint about an institution")} sub={t("Demo form. It goes to the Public Grievance Redressal Cell's register.")} />
        {done ? <div className="todo"><div className="label">{t("Registered")}</div><div className="big">{done.message}</div>
          <Link className="btn btn-primary" to={`/check/${done.case_id}`}>{t("Check its status")}</Link></div> :
          <form className="card" onSubmit={send}>
            <div className="field"><label htmlFor="sn">{t("Institution name")}</label><input id="sn" value={f.institution_text} onChange={(e) => setF({ ...f, institution_text: e.target.value })} required />
              <div className="hint">{t("Write it as you know it. An officer will match it to the right institution.")}</div></div>
            <div className="field"><label htmlFor="sc">{t("What is it about?")}</label><select id="sc" value={f.category_id} onChange={(e) => setF({ ...f, category_id: e.target.value })} required>
              <option value="">{t("Choose")}</option>{cats?.map((c) => <option key={c.id} value={c.id}>{t(c.name)}</option>)}</select></div>
            <div className="field"><label htmlFor="sd">{t("Your complaint")}</label><textarea id="sd" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} required /></div>
            <div className="fields2">
              <div className="field"><label htmlFor="snm">{t("Your name (optional)")}</label><input id="snm" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
              <div className="field"><label htmlFor="sem">{t("Your email (optional)")}</label><input id="sem" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
            </div>
            <p className="small muted">{t("Your name and email are seen only by AICTE officers, never on the public status page.")}</p>
            {err && <p className="err">{err}</p>}
            <button className="btn-primary">{t("Submit complaint")}</button>
          </form>}
      </div>
    </Page>
  );
}

export function Calendar() {
  const { t } = useApp();
  const { data } = useLoad<CaseRow[]>("/cases?status=OPEN");
  const { clock } = useApp();
  const [off, setOff] = useState(0);
  if (!data || !clock) return <Page><Skeleton /></Page>;
  const base = new Date(clock.today);
  const m = new Date(base.getFullYear(), base.getMonth() + off, 1);
  const days = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
  const lead = (m.getDay() + 6) % 7;
  const key = (d: number) => `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const due: Record<string, CaseRow[]> = {};
  data.forEach((c) => (due[c.expected_disposal_on] ||= []).push(c));
  return (
    <Page>
      <PageHead title={t("Due-date calendar")} sub={t("Expected disposal dates of open cases.")}
        right={<><button onClick={() => setOff(off - 1)}>←</button><b>{m.toLocaleString("en-IN", { month: "long", year: "numeric" })}</b><button onClick={() => setOff(off + 1)}>→</button></>} />
      <div className="cal">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="dow">{t(d)}</div>)}
        {Array.from({ length: lead }).map((_, i) => <div key={"x" + i} />)}
        {Array.from({ length: days }).map((_, i) => {
          const k = key(i + 1), list = due[k] || [];
          return <div key={k} className={`day ${list.length ? "has" : ""} ${k === clock.today ? "today" : ""}`}>
            {i + 1}{list.slice(0, 3).map((c) => <Link key={c.id} className="amt" to={`/cases/${c.case_id}`}>{c.case_id}</Link>)}
            {list.length > 3 && <span className="small muted">+{list.length - 3}</span>}</div>;
        })}
      </div>
    </Page>
  );
}

export function About() {
  const { t } = useApp();
  const rows: [string, string, string][] = [
    ["Institutions, cases, officers", "Simulated", "12 fictional institutions named after rivers, about 120 synthetic cases, 11 demo accounts."],
    ["Connection to AICTE systems", "Not connected", "No live AICTE data. Integration points: CSV import and the REST API (/docs)."],
    ["Overlap detection", "Real, rule-based", "Institution ID, fuzzy name match (RapidFuzz), category, TF-IDF text similarity and dates. Scored 0-100 with reasons. Not AI."],
    ["Accuracy figures", "Real, on synthetic data", "Measured on a labelled synthetic set (docs/MATCHING_METHOD.md). Real-world accuracy is unknown until tested on AICTE data."],
    ["Email alerts", "Real", "Sent through a real mail server and logged; only demo plus-addresses receive them."],
    ["SMS", "Planned", "Not built. An SMS interface exists with a 'not configured' implementation."],
    ["Demo clock", "Simulated time", "Moves the system date forward so SLA alerts and escalations can be shown in minutes."],
    ["Audit log", "Real", "Hash-chained and append-only in the database; Verify recomputes every hash."],
    ["Hindi", "Partial", "Main screens translated; translation not yet reviewed by a native editor."],
  ];
  return (
    <Page>
      <PageHead title={t("What is real and what is simulated")} sub={t("SAMANVAY is a prototype for coordinating complaints about institutions across AICTE units.")} />
      <div className="card scroll-x" style={{ padding: 0 }}><table className="plain"><thead><tr><th>{t("Part")}</th><th>{t("Status")}</th><th>{t("Detail")}</th></tr></thead>
        <tbody>{rows.map(([a, b, c]) => <tr key={a}><td><b>{t(a)}</b></td><td><Stamp label={b} kind={b.startsWith("Real") ? "done" : "wait"} /></td><td>{t(c)}</td></tr>)}</tbody></table></div>
      <p className="small muted" style={{ marginTop: 14 }}>{t("Tagline: One institution. One view. No duplicate action.")}</p>
    </Page>
  );
}
