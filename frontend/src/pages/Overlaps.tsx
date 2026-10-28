import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp, useAct, useLoad } from "../app";
import { Page } from "../components/Shell";
import { Empty, Modal, PageHead, RuleTag, ScoreMeter, Skeleton, SlaChip, Stamp } from "../components/ui";
import { day } from "../format";

type Pair = { key: string; a: number; b: number; a_ref: string; b_ref: string; a_unit: string; b_unit: string; score: number;
  parts: { institution: number; issue: number; time: number }; reasons: string[]; missing: string[]; duplicate_hint: boolean };
type Alert = { id: number; institution: { id: number; name: string; aicte_id: string }; units: string[]; score: number; pairs: Pair[];
  status: string; lead_unit: string | null; resolution: string; created_at: string; resolved_at: string | null };

export default function Overlaps() {
  const { t } = useApp();
  const [p, setP] = useSearchParams();
  const status = p.get("status") || "open";
  const { data } = useLoad<Alert[]>(`/overlaps?status=${status}`, [status]);
  return (
    <Page>
      <PageHead title={t("Overlap alerts")} sub={<>{t("Institutions where two or more units hold open cases that look related.")} <RuleTag /></>} />
      <div className="tabs" role="tablist">
        {[["open", "Open"], ["coordinated", "Coordinated"], ["dismissed", "Dismissed"], ["all", "All"]].map(([k, l]) =>
          <button key={k} role="tab" aria-selected={status === k} onClick={() => setP({ status: k })}>{t(l)}</button>)}
      </div>
      {!data ? <Skeleton /> : data.length ? <div className="stack">{data.map((a, i) => (
        <Link key={a.id} to={`/overlaps/${a.id}`} className="card" style={{ display: "block", color: "inherit", textDecoration: "none" }}>
          <div className="spread"><h2 style={{ margin: 0 }}>{a.institution.name}</h2>
            <span className="row">{a.status === "open" ? <Stamp label="Coordination required" kind="act" icon="link" quiet={i > 0} /> : <Stamp label={a.status} kind="done" />}<ScoreMeter score={a.score} /></span></div>
          <p className="small muted" style={{ margin: "4px 0" }}>{a.institution.aicte_id} · {t("Units")} {a.units.join(", ")} · {t("{n} case pairs", { n: a.pairs.length })}</p>
          <p className="small" style={{ margin: 0 }}>{a.status === "open" ? a.pairs[0].reasons.join(" | ") : a.resolution}</p>
        </Link>
      ))}</div> : <Empty>{t("No alerts here.")}</Empty>}
    </Page>
  );
}

type CaseLite = { id: number; case_id: string; unit: string; unit_name: string; officer: string | null; category: string; status_label: string;
  received_on: string; last_action: string; description: string; institution_name: string; raw_institution_text: string;
  institution: { aicte_id: string } | null; holder: { text: string }; sla: { days_left: number; pct_used: number; overdue: boolean } };
type Detail = Alert & { cases: Record<string, CaseLite>; can_resolve: boolean; unit_choices: { id: number; code: string }[] };

/** U1 overlap explainer: the two cases side by side, matched fields marked, the score in three parts with reasons and what is missing. */
export function OverlapDetail() {
  const { id } = useParams();
  const { t } = useApp();
  const { data: a, reload } = useLoad<Detail>(`/overlaps/${id}`, [id]);
  const { run, busy } = useAct();
  const [pi, setPi] = useState(0);
  const [decide, setDecide] = useState<null | { action: string; lead_unit_id?: number; merge_into?: number; title: string }>(null);
  const [reason, setReason] = useState("");
  if (!a) return <Page><Skeleton lines={8} /></Page>;
  const pair = a.pairs[pi];
  const A = a.cases[pair.a], B = a.cases[pair.b];
  const same = (f: (c: CaseLite) => string) => A && B && f(A) && f(A) === f(B);
  const submit = async () => {
    const r = await run(() => api(`/overlaps/${a.id}/resolve`, { body: { ...decide, reason } }), t("Decision recorded and both units informed."));
    if (r) { setDecide(null); setReason(""); reload(); }
  };
  return (
    <Page>
      <p className="small"><Link to="/overlaps">{t("Overlap alerts")}</Link> / {a.institution.name}</p>
      {a.status === "open" ? (
        <div className="banner" role="alert"><h2>{t("Potential Overlapping Cases - Coordination Required")}</h2>
          <p style={{ margin: 0 }}><Link to={`/institutions/${a.institution.id}`}>{a.institution.name}</Link> · {t("Units")} {a.units.join(", ")}</p></div>
      ) : <p className="ok-box"><b>{t(a.status === "coordinated" ? "Coordinated" : a.status === "dismissed" ? "Dismissed" : "Closed")}</b>{a.resolved_at && ` · ${day(a.resolved_at)}`}: {a.resolution}</p>}

      {a.pairs.length > 1 && <div className="tabs" role="tablist">{a.pairs.map((p, i) =>
        <button key={p.key} role="tab" aria-selected={pi === i} onClick={() => setPi(i)}>{p.a_ref} ↔ {p.b_ref} ({Math.round(p.score)})</button>)}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="spread"><h2 style={{ margin: 0 }}>{t("Why these cases were matched")}</h2><span className="row"><ScoreMeter score={pair.score} /><RuleTag /></span></div>
        <div className="parts" style={{ margin: "8px 0 12px" }}>
          <span>{t("Institution")} <b>{pair.parts.institution}</b>/40</span><span>{t("Issue")} <b>{pair.parts.issue}</b>/40</span><span>{t("Time")} <b>{pair.parts.time}</b>/20</span>
          {pair.duplicate_hint && <Stamp label="Possible duplicate" kind="wait" />}
        </div>
        <div className="grid2">
          <div><h3>{t("Evidence for")}</h3><ul className="why">{pair.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
          <div><h3>{t("Missing or against")}</h3>{pair.missing.length ? <ul className="why missing">{pair.missing.map((r, i) => <li key={i}>{r}</li>)}</ul>
            : <p className="muted small">{t("Nothing missing.")}</p>}</div>
        </div>
        <p className="small muted" style={{ marginTop: 10 }}>{t("The score ranks what to look at first. It is not a probability. A person decides.")}</p>
      </div>

      <div className="vs">
        {[A, B].map((c) => c && (
          <div className="card" key={c.id}>
            <div className="spread"><Link to={`/cases/${c.case_id}`}><h3 style={{ margin: 0 }}>{c.case_id}</h3></Link><SlaChip sla={c.sla} /></div>
            <p className="holder" style={{ margin: "6px 0 10px" }}>{c.holder.text}</p>
            <dl>
              <dt>{t("Institution")}</dt><dd><span className={same((x) => x.institution?.aicte_id || "") ? "hl" : ""}>{c.raw_institution_text || c.institution_name}</span>
                {c.institution && <div className="small muted">{c.institution.aicte_id}</div>}</dd>
              <dt>{t("Unit")}</dt><dd>{c.unit_name}</dd>
              <dt>{t("Category")}</dt><dd><span className={same((x) => x.category) ? "hl" : ""}>{t(c.category)}</span></dd>
              <dt>{t("Received")}</dt><dd>{day(c.received_on)}</dd>
              <dt>{t("Last action")}</dt><dd>{c.last_action ? t(c.last_action) : "—"}</dd>
              <dt>{t("Complaint")}</dt><dd className="small">{c.description}</dd>
            </dl>
          </div>
        ))}
      </div>

      {a.status === "open" && (a.can_resolve ? (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>{t("Coordinator's decision")}</h2>
          <div className="row">
            {a.unit_choices.map((u, i) => <button key={u.id} className={i === 0 ? "btn-primary" : "btn-strong"} onClick={() => setDecide({ action: "lead", lead_unit_id: u.id, title: t("Assign {u} as lead unit", { u: u.code }) })}>{t("Assign {u} as lead unit", { u: u.code })}</button>)}
            <button onClick={() => setDecide({ action: "link", title: t("Link cases for joint handling") })}>{t("Link cases")}</button>
            <button onClick={() => setDecide({ action: "merge", merge_into: A.id, title: t("Merge into {c}", { c: A.case_id }) })}>{t("Merge into {c}", { c: A.case_id })}</button>
            <button className="btn-danger" onClick={() => setDecide({ action: "dismiss", title: t("Dismiss: not an overlap") })}>{t("Dismiss with reason")}</button>
          </div>
        </div>
      ) : <p className="note" style={{ marginTop: 16 }}>{t("The Coordinator decides on this alert. You will get a message when it is resolved.")}</p>)}

      {decide && (
        <Modal title={decide.title} onClose={() => setDecide(null)}>
          <div className="field"><label htmlFor="dr">{t("Decision and reason (sent to both units, kept in the audit log)")}</label>
            <textarea id="dr" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("e.g. RB leads; PGRC keeps the complainant informed.")} /></div>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button onClick={() => setDecide(null)}>{t("Cancel")}</button>
            <button className="btn-primary" disabled={busy || reason.trim().length < 10} onClick={submit}>{t("Record decision")}</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}
