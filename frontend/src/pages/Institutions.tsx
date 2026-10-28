import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApp, useLoad } from "../app";
import { CaseList, type CaseRow } from "../components/CaseList";
import { Page } from "../components/Shell";
import { Empty, PageHead, RuleTag, Skeleton, Stamp } from "../components/ui";
import { dateTime, day } from "../format";

type Inst = { id: number; name: string; aicte_id: string; city: string; region: string; state: string; open: number; units: string[];
  overdue: number; alerts: number; summary: string };

export default function Institutions() {
  const { t } = useApp();
  const [q, setQ] = useState("");
  const { data } = useLoad<Inst[]>("/institutions");
  const rows = (data || []).filter((i) => !q || (i.name + i.aicte_id + i.city).toLowerCase().includes(q.toLowerCase()));
  const first = rows.findIndex((i) => i.alerts > 0);
  return (
    <Page>
      <PageHead title={t("Institutions")} sub={t("What is AICTE doing about each college right now?")} />
      <div className="field" style={{ maxWidth: 420 }}><label htmlFor="iq">{t("Find an institution")}</label>
        <input id="iq" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Name, AICTE ID or city")} /></div>
      {!data ? <Skeleton /> : (
        <div className="card" style={{ padding: 0 }}>
          {rows.map((i, n) => (
            <Link key={i.id} to={`/institutions/${i.id}`} className="lcard" style={{ display: "block", color: "inherit", textDecoration: "none" }}>
              <div className="spread"><b>{i.name}</b>
                {i.alerts > 0 ? <Stamp label="Overlap" kind="act" icon="link" quiet={n !== first} /> : i.open === 0 ? <Stamp label="Nothing pending" kind="done" /> : null}</div>
              <div className="small muted">{i.aicte_id} · {i.city}, {i.state} · {t(i.region)}</div>
              <div className="small" style={{ marginTop: 4 }}>{i.summary}</div>
            </Link>
          ))}
        </div>
      )}
    </Page>
  );
}

type Alert = { id: number; status: string; score: number; units: string[]; pairs: { reasons: string[] }[]; resolution: string; lead_unit: string | null };
type I360 = {
  institution: { id: number; name: string; aicte_id: string; city: string; state: string; region: string; address: string; pin: string; kind: string; aliases: string[] };
  summary: string; alerts: Alert[]; cases: CaseRow[]; by_unit: Record<string, Record<string, number>>;
  pending_actions: { case_id: string; unit: string; next_action: string; holder: string }[];
  decisions: { case_id: string; unit: string; on: string; note: string }[];
  conflicts: { case_id: string; at: string; actor: string; action_type: string; remarks: string }[];
  heat: { case_id: string; unit: string; age: number; bucket: string; overdue: boolean }[];
  timeline: { id: number; case_id: string; at: string; kind: string; actor: string; unit: string; action_type: string; remarks: string }[];
};
const BUCKET: Record<string, string> = { "0-15": "b0", "16-30": "b1", "31-60": "b2", "60+": "b3" };

export function Institution360() {
  const { id } = useParams();
  const { t } = useApp();
  const { data: d } = useLoad<I360>(`/institutions/${id}`, [id]);
  const [tab, setTab] = useState<"open" | "all" | "timeline" | "decisions">("open");
  if (!d) return <Page><Skeleton lines={8} /></Page>;
  const i = d.institution;
  const open = d.cases.filter((c) => c.status !== "DISPOSED");
  const openAlerts = d.alerts.filter((a) => a.status === "open");
  return (
    <Page>
      <p className="small"><Link to="/institutions">{t("Institutions")}</Link> / {i.name}</p>
      <PageHead title={i.name} sub={`${i.aicte_id} · ${i.kind} · ${i.city}, ${i.state} ${i.pin} · ${t(i.region)} ${t("region")}`} />
      <div className="todo" style={{ marginBottom: 18 }}>
        <div className="label">{t("Right now")}</div>
        <div className="big" style={{ marginBottom: 6 }}>{d.summary}</div>
        {i.aliases.length > 0 && <div className="small">{t("Also written as")}: {i.aliases.join(" · ")}</div>}
      </div>
      {openAlerts.map((a) => (
        <div key={a.id} className="banner" role="alert">
          <h2>{t("Potential Overlapping Cases - Coordination Required")}</h2>
          <p style={{ margin: "4px 0" }}>{t("Units")} {a.units.join(", ")} · {t("Score")} <b>{Math.round(a.score)}/100</b> <RuleTag /></p>
          <p className="small" style={{ margin: "4px 0 8px" }}>{a.pairs[0].reasons.join(" | ")}</p>
          <Link to={`/overlaps/${a.id}`}>{t("Explain and decide")} →</Link>
        </div>
      ))}
      <div className="grid2">
        <div className="card">
          <h2>{t("Ageing of open cases")}</h2>
          {d.heat.length ? <div className="heat" aria-label={t("Each box is an open case; darker is older, red is overdue")}>
            {d.heat.map((h) => <Link key={h.case_id} to={`/cases/${h.case_id}`} className={h.overdue ? "late" : BUCKET[h.bucket]} title={`${h.case_id} · ${h.age} ${t("days")}`}>{h.unit} {h.age}d</Link>)}
          </div> : <p className="muted">{t("No open cases.")}</p>}
          <p className="small muted" style={{ marginTop: 8 }}>{t("Each box is an open case: darker is older, red is overdue.")}</p>
        </div>
        <div className="card">
          <h2>{t("Cases by unit")}</h2>
          <table className="plain"><thead><tr><th>{t("Unit")}</th><th>{t("Open")}</th><th>{t("Disposed")}</th></tr></thead>
            <tbody>{Object.entries(d.by_unit).map(([u, s]) => <tr key={u}><td><b>{u}</b></td>
              <td>{Object.entries(s).filter(([k]) => k !== "DISPOSED").reduce((a, [, v]) => a + v, 0)}</td><td>{s.DISPOSED || 0}</td></tr>)}</tbody></table>
        </div>
      </div>
      {(d.pending_actions.length > 0 || d.conflicts.length > 0) && (
        <div className="card" style={{ marginTop: 18 }}>
          <h2>{t("Pending actions and coordination issues")}</h2>
          <table className="plain"><tbody>
            {d.pending_actions.map((p) => <tr key={p.case_id}><td><Link to={`/cases/${p.case_id}`}>{p.case_id}</Link></td><td>{p.holder}</td><td>{p.next_action || <span className="muted">{t("No next action written")}</span>}</td></tr>)}
            {d.conflicts.map((c, n) => <tr key={"c" + n} className="bad-row"><td><Link to={`/cases/${c.case_id}`}>{c.case_id}</Link></td><td>{t("Conflict acknowledged")} · {day(c.at)}</td><td>{t(c.action_type)}: {c.remarks}</td></tr>)}
          </tbody></table>
        </div>
      )}
      <div className="tabs" role="tablist" style={{ marginTop: 24 }}>
        {([["open", t("Open cases ({n})", { n: open.length })], ["all", t("All cases ({n})", { n: d.cases.length })], ["timeline", t("Timeline")], ["decisions", t("Past decisions ({n})", { n: d.decisions.length })]] as const)
          .map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "open" && (open.length ? <CaseList rows={open} /> : <Empty>{t("No open cases.")}</Empty>)}
      {tab === "all" && <CaseList rows={d.cases} />}
      {tab === "timeline" && <div className="card"><ol className="timeline">{d.timeline.map((e) => (
        <li key={e.id}><div className="small muted">{dateTime(e.at)} · {e.unit} · {e.actor}</div>
          <div><Link to={`/cases/${e.case_id}`}>{e.case_id}</Link> · {e.action_type ? t(e.action_type) : e.remarks}</div></li>))}</ol></div>}
      {tab === "decisions" && <div className="card">{d.decisions.length ? <table className="plain"><tbody>{d.decisions.map((x) =>
        <tr key={x.case_id}><td><Link to={`/cases/${x.case_id}`}>{x.case_id}</Link></td><td>{x.unit}</td><td>{day(x.on)}</td><td>{x.note}</td></tr>)}</tbody></table>
        : <p className="muted">{t("No decisions yet.")}</p>}</div>}
    </Page>
  );
}
