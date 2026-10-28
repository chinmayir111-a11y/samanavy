import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useApp, useAct, useLoad } from "../app";
import { Page } from "../components/Shell";
import { Empty, PageHead, Skeleton, Stamp } from "../components/ui";
import { dateTime } from "../format";

type Overview = { rules: Record<string, any>; users: { id: number; name: string; email: string; role: string; unit: string | null; active: boolean; invited: boolean }[];
  units: { id: number; code: string; name: string }[]; categories: { id: number; name: string; sla_days: number }[];
  email: { configured: boolean; provider: string }; sms: { label: string }; scheduler_heartbeat: string | null; last_daily_run: string | null };

const RULES: [string, string, string][] = [
  ["name_match_threshold", "Name match threshold (0-100)", "Typed institution names scoring at least this are suggested."],
  ["overlap_alert_threshold", "Overlap alert threshold (0-100)", "Case pairs scoring at least this raise an alert."],
  ["overlap_window_days", "Overlap window (days)", "Cases received further apart than this get no time points."],
  ["sla_alert_pcts", "SLA alert points (% of SLA)", "Comma separated. 100 = due day. Overdue is always alerted."],
  ["escalation_days", "Escalation ladder (days overdue)", "Unit Head, Coordinator, Management."],
];

export default function Admin() {
  const { t, refreshClock, clock } = useApp();
  const { data: d, reload } = useLoad<Overview>("/admin/overview");
  const { run, busy } = useAct();
  const [vals, setVals] = useState<Record<string, string>>({});
  const [inv, setInv] = useState({ name: "", email: "", role: "desk_officer", unit_id: "" });
  if (!d) return <Page><Skeleton lines={8} /></Page>;
  const show = (k: string) => vals[k] ?? (k === "sla_alert_pcts" ? d.rules[k].join(", ") : k === "escalation_days" ? ["1", "2", "3"].map((x) => d.rules[k][x]).join(", ") : String(d.rules[k]));
  const saveRules = () => {
    const out: Record<string, any> = {};
    for (const [k] of RULES) if (vals[k] !== undefined) {
      const nums = vals[k].split(",").map((x) => Number(x.trim()));
      out[k] = k === "sla_alert_pcts" ? nums : k === "escalation_days" ? { 1: nums[0], 2: nums[1], 3: nums[2] } : nums[0];
    }
    run(() => api("/admin/rules", { method: "PUT", body: { values: out } }), t("Rules saved and logged.")).then((r) => { if (r) { setVals({}); reload(); } });
  };
  const move = (body: any) => run(() => api<any>("/admin/clock", { body })).then((r) => {
    if (r) { refreshClock(); reload(); }
    return r;
  });
  return (
    <Page>
      <PageHead title={t("Admin")} sub={t("Rules, accounts and the demo clock. Every change goes to the audit log.")} />
      <div className="card" style={{ marginBottom: 18 }}>
        <h2>{t("Demo clock")}</h2>
        <p className="small muted">{t("Moves the system date forward and runs the daily SLA and escalation job at once, so reminders and escalations appear without waiting. One digest email per person.")}</p>
        <p>{t("Now: +{n} days", { n: clock?.offset_days ?? 0 })}</p>
        <div className="row">
          {[7, 30, 90].map((n) => <button key={n} className={n === 30 ? "btn-primary" : "btn-strong"} disabled={busy} onClick={() => move({ days: n }).then((r: any) => r && alert(t("+{n} days: {a} SLA alerts, {e} escalations, {m} digest emails.", { n, a: r.sla_alerts, e: r.escalations, m: r.digest_emails })))}>+{n} {t("days")}</button>)}
          <button disabled={busy} onClick={() => move({ reset: true })}>{t("Back to today")}</button>
          <Link className="btn btn-quiet" to="/emails">{t("Open the email log")}</Link>
        </div>
      </div>
      <div className="grid2">
        <div className="card">
          <h2>{t("Matching and alert rules")}</h2>
          {RULES.map(([k, l, h]) => <div className="field" key={k}><label htmlFor={k}>{t(l)}</label>
            <input id={k} value={show(k)} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} /><div className="hint">{t(h)}</div></div>)}
          <button className="btn-primary" disabled={busy || !Object.keys(vals).length} onClick={saveRules}>{t("Save rules")}</button>
        </div>
        <div className="card">
          <h2>{t("Categories and SLA days")}</h2>
          <table className="plain"><tbody>{d.categories.map((c) => <tr key={c.id}><td>{t(c.name)}</td><td style={{ width: 110 }}>
            <input type="number" min={1} max={365} defaultValue={c.sla_days} aria-label={t("SLA days for {c}", { c: c.name })}
              onBlur={(e) => Number(e.target.value) !== c.sla_days && run(() => api(`/admin/categories/${c.id}`, { method: "PUT", body: { sla_days: Number(e.target.value) } }), t("SLA saved (new cases)."))} /></td></tr>)}</tbody></table>
          <h3 style={{ marginTop: 16 }}>{t("Channels")}</h3>
          <p className="small">{t("Email")}: {d.email.configured ? t("configured ({p})", { p: d.email.provider }) : t("not configured: messages are logged, not sent")}</p>
          <p className="small">{t("SMS")}: <Stamp label="SMS planned" kind="wait" /> {t(d.sms.label)}</p>
          <p className="small">{t("Scheduler heartbeat")}: {d.scheduler_heartbeat ? dateTime(d.scheduler_heartbeat) : t("not running")}</p>
        </div>
      </div>
      <div className="card" style={{ marginTop: 18 }}>
        <h2>{t("Accounts")}</h2>
        <p className="small muted">{t("Officers cannot sign up. Invite them here; they get an email link to choose a password.")}</p>
        <div className="filters">
          <div><label htmlFor="in">{t("Name")}</label><input id="in" value={inv.name} onChange={(e) => setInv({ ...inv, name: e.target.value })} /></div>
          <div><label htmlFor="ie">{t("Email")}</label><input id="ie" type="email" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} /></div>
          <div><label htmlFor="ir">{t("Role")}</label><select id="ir" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}>
            {["desk_officer", "unit_head", "coordinator", "management", "admin"].map((r) => <option key={r} value={r}>{t(r.replace("_", " "))}</option>)}</select></div>
          <div><label htmlFor="iu">{t("Unit")}</label><select id="iu" value={inv.unit_id} onChange={(e) => setInv({ ...inv, unit_id: e.target.value })}>
            <option value="">—</option>{d.units.map((u) => <option key={u.id} value={u.id}>{u.code}</option>)}</select></div>
          <button className="btn-strong" disabled={busy || !inv.name || !inv.email} onClick={() => run(() => api<any>("/admin/invite", { body: { ...inv, unit_id: Number(inv.unit_id) || null } }))
            .then((r) => { if (r) { alert(t("Invitation saved. Email: {s}", { s: r.email_status })); setInv({ name: "", email: "", role: "desk_officer", unit_id: "" }); reload(); } })}>{t("Send invitation")}</button>
        </div>
        <div className="scroll-x"><table className="plain"><thead><tr><th>{t("Name")}</th><th>{t("Email")}</th><th>{t("Role")}</th><th>{t("Unit")}</th><th></th></tr></thead>
          <tbody>{d.users.map((u) => <tr key={u.id}><td>{u.name}</td><td className="small">{u.email}</td><td>{t(u.role.replace("_", " "))}</td><td>{u.unit || "—"}</td>
            <td>{u.invited ? <Stamp label="Invited" kind="wait" /> : !u.active ? <Stamp label="Disabled" kind="done" /> : null}
              <button className="btn-quiet small" onClick={() => run(() => api(`/admin/users/${u.id}/active`, { method: "POST" })).then((r) => r && reload())}>{u.active ? t("Disable") : t("Enable")}</button></td></tr>)}</tbody></table></div>
      </div>
      <PendingLinks />
      <RegionTable />
    </Page>
  );
}

function PendingLinks() {
  const { t } = useApp();
  const { data, reload } = useLoad<{ id: number; name: string; email: string; user_type: string; institution: string; aicte_id: string }[]>("/admin/links");
  const { run } = useAct();
  return (
    <div className="card" style={{ marginTop: 18 }}>
      <h2>{t("College links waiting for approval")}</h2>
      <p className="small muted">{t("People who typed an AICTE ID already on the register, or college staff, stay pending until you confirm.")}</p>
      {!data?.length ? <p className="muted">{t("Nothing waiting.")}</p> : <table className="plain"><tbody>{data.map((u) => <tr key={u.id}>
        <td>{u.name}<div className="small muted">{u.email} · {t(u.user_type)}</div></td><td>{u.institution}<div className="small muted">{u.aicte_id}</div></td>
        <td><button className="btn-strong" onClick={() => run(() => api(`/admin/links/${u.id}`, { body: { approve: true } }), t("Approved.")).then(reload)}>{t("Approve")}</button>{" "}
          <button onClick={() => run(() => api(`/admin/links/${u.id}`, { body: { approve: false } }), t("Rejected.")).then(reload)}>{t("Reject")}</button></td></tr>)}</tbody></table>}
    </div>
  );
}

function RegionTable() {
  const { t } = useApp();
  const { data, reload } = useLoad<{ regions: Record<string, { region: string; basis: string }>; names: string[]; states: string[] }>("/admin/regions");
  const { run } = useAct();
  if (!data) return null;
  return (
    <details className="card geo" style={{ marginTop: 18 }}>
      <summary><b>{t("AICTE region for each state")}</b> <span className="small muted">· {t("rows marked 'confirm' are not yet checked against aicte-india.org")}</span></summary>
      <div className="scroll-x"><table className="plain"><thead><tr><th>{t("State")}</th><th>{t("Region")}</th><th>{t("Source")}</th></tr></thead>
        <tbody>{data.states.map((st) => { const r = data.regions[st] || { region: "", basis: "confirm" }; return <tr key={st}><td>{st}</td>
          <td><select aria-label={t("Region for {s}", { s: st })} value={r.region} onChange={(e) => run(() => api("/admin/regions", { method: "PUT", body: { regions: { [st]: { region: e.target.value } } } }), t("Saved and logged.")).then(reload)}>
            <option value="">—</option>{data.names.map((n) => <option key={n}>{n}</option>)}</select></td>
          <td className="small">{r.basis === "confirm" ? <span className="stamp act">{t("confirm")}</span> : t(r.basis)}</td></tr>; })}</tbody></table></div>
    </details>
  );
}

type Mail = { id: number; to: string; subject: string; kind: string; status: string; detail: string; attempts: number; created_at: string; sent_at: string | null };

export function Emails() {
  const { me, t } = useApp();
  const { data, reload } = useLoad<Mail[]>("/emails");
  const { run, busy } = useAct();
  return (
    <Page>
      <PageHead title={t("Email log")} sub={t("Every email the system tried to send, with the result. Failed emails are retried once automatically.")}
        right={<>{me?.role === "admin" && <button disabled={busy} onClick={() => run(() => api<any>("/emails/test", { method: "POST" })).then((r) => { if (r) { alert(`${r.status}: ${r.detail}`); reload(); } })}>{t("Send a test email")}</button>}<button onClick={reload}>{t("Refresh")}</button></>} />
      {!data ? <Skeleton /> : data.length ? <div className="card scroll-x" style={{ padding: 0 }}><table className="plain">
        <thead><tr><th>{t("When")}</th><th>{t("To")}</th><th>{t("Subject")}</th><th>{t("Result")}</th><th></th></tr></thead>
        <tbody>{data.map((m) => <tr key={m.id} className={m.status === "FAILED" ? "bad-row" : ""}><td className="small">{dateTime(m.created_at)}</td><td className="small">{m.to}</td><td>{m.subject}</td>
          <td><Stamp label={m.status === "SENT" ? "Delivered to mail server" : m.status === "FAILED" ? "Failed" : m.status === "QUEUED" ? "Queued" : "Logged only"} kind={m.status === "FAILED" ? "act" : m.status === "SENT" ? "done" : "wait"} quiet />
            <div className="small muted">{m.detail}{m.attempts > 1 && ` · ${t("{n} attempts", { n: m.attempts })}`}</div></td>
          <td>{me?.role === "admin" && m.status !== "SENT" && <button className="btn-quiet small" disabled={busy} onClick={() => run(() => api(`/emails/${m.id}/resend`, { method: "POST" })).then(() => reload())}>{t("Resend")}</button>}</td></tr>)}</tbody>
      </table></div> : <Empty>{t("No emails yet. Move the demo clock or create a case to trigger alerts.")}</Empty>}
    </Page>
  );
}

type AuditRow = { id: number; at: string; actor: string; action: string; summary: string; hash: string };

export function Audit() {
  const { t } = useApp();
  const { data } = useLoad<AuditRow[]>("/audit");
  const [v, setV] = useState<{ ok: boolean; checked: number; broken_id: number | null; reason: string } | null>(null);
  const { run, busy } = useAct();
  return (
    <Page>
      <PageHead title={t("Audit log")} sub={t("Append-only. Each entry's hash covers the one before it, so any silent change breaks the chain.")}
        right={<button className="btn-primary" disabled={busy} onClick={() => run(() => api<any>("/audit/verify", { method: "POST" })).then(setV)}>{t("Verify")}</button>} />
      {v && <p className={v.ok ? "ok-box" : "banner"} role="status"><b>{v.ok ? t("Chain intact.") : t("Chain broken at entry #{n}.", { n: v.broken_id })}</b> {t("{n} entries checked.", { n: v.checked })} {v.reason}</p>}
      {!data ? <Skeleton /> : <div className="card scroll-x" style={{ padding: 0 }}><table className="plain">
        <thead><tr><th>#</th><th>{t("When")}</th><th>{t("Who")}</th><th>{t("What")}</th><th>{t("Hash")}</th></tr></thead>
        <tbody>{data.map((r) => <tr key={r.id} className={v && !v.ok && v.broken_id === r.id ? "bad-row" : ""}><td>{r.id}</td><td className="small">{dateTime(r.at)}</td><td className="small">{r.actor}</td><td>{r.summary}</td><td className="small muted num">{r.hash}…</td></tr>)}</tbody>
      </table></div>}
    </Page>
  );
}

type Note = { id: number; title: string; body: string; case_id: string | null; alert_id: number | null; at: string; read: boolean };

export function Inbox() {
  const { t } = useApp();
  const { data, reload } = useLoad<Note[]>("/inbox");
  const { run } = useAct();
  return (
    <Page>
      <PageHead title={t("Inbox")} sub={t("In-app messages always arrive, even when email is down.")}
        right={data?.some((n) => !n.read) ? <button onClick={() => run(() => api("/inbox/read", { method: "POST" })).then(reload)}>{t("Mark all read")}</button> : undefined} />
      {!data ? <Skeleton /> : data.length ? <div className="card" style={{ padding: 0 }}>{data.map((n) => (
        <div key={n.id} className="lcard" style={!n.read ? { boxShadow: "inset 3px 0 0 var(--primary)" } : undefined}>
          <div className="spread"><b>{n.title}</b><span className="small muted">{dateTime(n.at)}</span></div>
          <div className="small" style={{ whiteSpace: "pre-line" }}>{n.body}</div>
          {n.alert_id ? <Link className="small" to={`/overlaps/${n.alert_id}`}>{t("Open the alert")}</Link> : n.case_id && <Link className="small" to={`/cases/${n.case_id}`}>{t("Open {c}", { c: n.case_id })}</Link>}
        </div>))}</div> : <Empty>{t("No messages.")}</Empty>}
    </Page>
  );
}
