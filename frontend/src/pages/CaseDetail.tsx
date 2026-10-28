import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiBase } from "../api";
import { useApp, useAct, useLoad } from "../app";
import type { CaseRow } from "../components/CaseList";
import { Page } from "../components/Shell";
import { CaseStamp, Modal, ProgressStrip, ReasonModal, RuleTag, ScoreMeter, SlaChip, Skeleton, Stamp, type Step } from "../components/ui";
import { dateTime, day } from "../format";
import type { Meta } from "./Cases";

type Pair = { score: number; reasons: string[]; missing: string[]; a_ref: string; b_ref: string };
type Event = { id: number; at: string; kind: string; actor: string; unit: string | null; action_type: string; remarks: string; attachment: string | null; meta: any };
type Detail = CaseRow & {
  description: string; complainant: string | null; source: string; unit_name: string; escalation_level: number; source_ref: string; priority: string; sla_days: number;
  suggestion: { score: number; reasons: string[]; institution: { id: number; name: string; aicte_id: string; city: string } } | null;
  raw_institution_text: string; transfer_reason: string; disposal_note: string; steps: Step[]; events: Event[];
  alerts: { id: number; status: string; score: number; units: string[]; pairs: Pair[]; resolution: string }[];
  links: { case_id: string; unit: string; kind: string; reason: string }[];
  related: (CaseRow & { pair: Pair | null })[];
  recommendation: { action: string; rule: string; evidence: string[]; kind: string } | null;
  can_edit: boolean; can_decide_transfer: boolean;
};
type Conflict = { action_type: string; cases: { case_id: string; unit: string; officer: string | null; category: string; status: string; last_action: string; received_on: string }[] };

const KIND: Record<string, string> = {
  received: "Received", assigned: "Assigned", action: "Action", remark: "Remark", transfer_requested: "Transfer asked",
  transfer_accepted: "Transfer accepted", transfer_rejected: "Transfer returned", escalated: "Escalated", linked: "Linked",
  merged: "Merged", overlap: "Overlap", conflict_acknowledged: "Conflict acknowledged", institution_confirmed: "Institution confirmed",
  institution_rejected: "Suggestion rejected", sla_alert: "SLA alert", disposed: "Disposed",
};

export default function CaseDetail() {
  const { ref } = useParams();
  const { t, toast } = useApp();
  const { data: c, reload } = useLoad<Detail>(`/cases/${ref}`, [ref]);
  const meta = useLoad<Meta>("/meta").data;
  const { run, busy } = useAct();
  const [modal, setModal] = useState<"" | "action" | "transfer" | "escalate" | "dispose" | "remark" | "assign" | "return">("");
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [form, setForm] = useState({ action_type: "", remarks: "", next_action: "", suggested: "" });
  if (!c) return <Page><Skeleton lines={8} /></Page>;

  const done = (msg: string) => { setModal(""); setConflict(null); toast(msg); reload(); };
  const openAlert = c.alerts.find((a) => a.status === "open");
  const regulatory = meta?.action_types.find((a) => a.name === form.action_type)?.regulatory;

  const recordAction = async (ack = "") => {
    try {
      await api(`/cases/${c.case_id}/action`, { body: { ...form, ack_reason: ack } });
      done(t("Action recorded."));
    } catch (e: any) {
      if (e.status === 409 && e.detail?.code === "conflict") { setConflict(e.detail); setModal(""); }
      else toast(e.message, true);
    }
  };
  const useRec = () => {
    if (!c.recommendation) return;
    const r = c.recommendation;
    if (r.kind === "escalate") return setModal("escalate");
    if (r.kind === "assign") return setModal("assign");
    if (r.kind === "dispose") return setModal("dispose");
    setForm({ action_type: r.action, remarks: "", next_action: "", suggested: r.action });
    setModal("action");
  };

  return (
    <Page>
      <p className="small"><Link to="/cases">{t("Cases")}</Link> / {c.case_id}</p>
      <div className="spread" style={{ alignItems: "flex-start" }}>
        <div style={{ minWidth: 0, flex: "1 1 400px" }}>
          <h1 className="num">{c.case_id} <CaseStamp r={c} /></h1>
          <p style={{ marginBottom: 4 }}>
            {c.institution ? <Link to={`/institutions/${c.institution.id}`}><b>{c.institution_name}</b></Link> : <b>{c.raw_institution_text}</b>}
            {c.institution && <span className="muted"> · {c.institution.aicte_id}</span>} · {t(c.category)}
          </p>
          <p className="holder"><b>{t("Who is acting now")}:</b> {c.holder.text}</p>
        </div>
        <div className="row"><SlaChip sla={c.sla} done={c.status === "DISPOSED"} /><span className="small muted">{t("Expected disposal")} {day(c.expected_disposal_on)}</span></div>
      </div>

      {openAlert && (
        <div className="banner" role="alert">
          <h2>{t("Potential Overlapping Cases - Coordination Required")}</h2>
          <p style={{ margin: "4px 0" }}>{t("Units {u} have open cases on this institution.", { u: openAlert.units.join(", ") })} {t("Score")} <b>{Math.round(openAlert.score)}/100</b> <RuleTag /></p>
          <p className="small" style={{ margin: "4px 0 8px" }}>{openAlert.pairs[0].reasons.join(" | ")}</p>
          <Link to={`/overlaps/${openAlert.id}`}>{t("See the side-by-side explanation")} →</Link>
        </div>
      )}

      {c.suggestion && <Suggestion c={c} onDone={(m) => done(m)} />}

      <ProgressStrip steps={c.steps} now={c.holder.text} />

      <div className="grid2" style={{ marginTop: 16 }}>
        <div className="stack">
          {c.recommendation && c.status !== "DISPOSED" && (
            <div className="rec">
              <div className="small muted" style={{ textTransform: "uppercase", letterSpacing: ".06em", fontWeight: 700 }}>{t("Suggested next step")} · {t("rule")} {c.recommendation.rule.split(" ")[0]}</div>
              <p className="serif" style={{ fontSize: "1.1rem", margin: "4px 0" }}>{t(c.recommendation.action)}</p>
              <ul className="small" style={{ margin: "0 0 8px", paddingLeft: 18 }}>{c.recommendation.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
              {c.can_edit && c.recommendation.kind !== "info" && c.recommendation.kind !== "transfer" &&
                <div className="row"><button className="btn-strong" onClick={useRec}>{t("Use this")}</button><span className="small muted">{t("or choose any other action below. You decide.")}</span></div>}
            </div>
          )}

          {(c.can_edit || c.can_decide_transfer) && c.status !== "DISPOSED" && (
            <div className="card">
              <h2>{t("Act on this case")}</h2>
              {c.can_decide_transfer ? <div className="row">
                <p style={{ width: "100%" }}>{t("Transfer asked to your unit")}: {c.transfer_reason}</p>
                <button className="btn-primary" disabled={busy} onClick={() => run(() => api(`/cases/${c.case_id}/transfer/decide`, { body: { accept: true } }), t("Transfer accepted.")).then((r) => r && reload())}>{t("Accept transfer")}</button>
                <button onClick={() => setModal("return")}>{t("Return it")}</button>
              </div> : c.transfer_to ? <p className="muted">{t("Waiting for {u} to accept the transfer.", { u: c.transfer_to })}</p> : (
                <div className="row">
                  <button className="btn-primary" onClick={() => { setForm({ action_type: "", remarks: "", next_action: "", suggested: c.recommendation?.action || "" }); setModal("action"); }}>{t("Record action")}</button>
                  <button onClick={() => setModal("assign")}>{t("Assign")}</button>
                  <button onClick={() => setModal("remark")}>{t("Add remark or file")}</button>
                  <button onClick={() => setModal("transfer")}>{t("Transfer")}</button>
                  <button onClick={() => setModal("escalate")}>{t("Escalate")}</button>
                  <button className="btn-danger" onClick={() => setModal("dispose")}>{t("Dispose")}</button>
                </div>
              )}
            </div>
          )}

          <div className="card">
            <h2>{t("History")}</h2>
            <ol className="timeline">
              {c.events.map((e) => (
                <li key={e.id}>
                  <div className="small muted">{dateTime(e.at)} · {e.unit} · {e.actor}</div>
                  <div><b>{t(KIND[e.kind] || e.kind)}</b>{e.action_type && <>: {t(e.action_type)}</>}</div>
                  {e.remarks && <div className={e.kind === "conflict_acknowledged" ? "note small" : "small"}>{e.kind === "conflict_acknowledged" && <b>{t("Reason given:")} </b>}{e.remarks}</div>}
                  {e.meta?.suggested && <div className="small muted">{e.meta.followed ? t("Followed the suggested step.") : t("Suggested step was '{s}'; officer chose differently.", { s: e.meta.suggested })}</div>}
                  {e.attachment && <a className="small" href={`${apiBase}/cases/${c.case_id}/attachment/${e.id}`}>{e.attachment}</a>}
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>{t("Case details")}</h2>
            <dl className="dl">
              <dt>{t("Received")}</dt><dd>{day(c.received_on)} · {t(c.source)}</dd>
              <dt>{t("Unit file no.")}</dt><dd>{c.source_ref || "—"}</dd>
              <dt>{t("Unit")}</dt><dd>{c.unit_name}</dd>
              <dt>{t("Officer")}</dt><dd>{c.officer || t("not assigned")}</dd>
              <dt>{t("Status")}</dt><dd>{t(c.status_label)}{c.escalation_level > 0 && ` · ${t("escalation level {n}", { n: c.escalation_level })}`}</dd>
              <dt>{t("Last action")}</dt><dd>{c.last_action ? `${t(c.last_action)} · ${day(c.last_action_on)}` : "—"}</dd>
              <dt>{t("Next action")}</dt><dd>{c.next_action || "—"}</dd>
              <dt>{t("SLA")}</dt><dd>{t("{n} days", { n: c.sla_days })} · {t("{p}% used", { p: c.sla.pct_used })}</dd>
              <dt>{t("Priority")}</dt><dd>{t(c.priority)}</dd>
              {c.complainant && <><dt>{t("Complainant")}</dt><dd>{c.complainant} <span className="small muted">({t("never shown publicly")})</span></dd></>}
            </dl>
            <h3 style={{ marginTop: 16 }}>{t("Complaint")}</h3>
            <p>{c.description}</p>
            {c.disposal_note && <p className="ok-box"><b>{t("Decision")}:</b> {c.disposal_note}</p>}
          </div>

          {c.related.length > 0 && (
            <div className="card">
              <h2>{t("Other open cases on this institution")}</h2>
              {c.related.map((r) => (
                <div key={r.id} style={{ padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                  <div className="spread"><Link to={`/cases/${r.case_id}`}><b>{r.case_id}</b></Link>{r.pair && <ScoreMeter score={r.pair.score} />}</div>
                  <div className="small">{t(r.category)} · {r.holder.text}</div>
                  {r.pair && <div className="small muted">{r.pair.reasons.slice(0, 2).join(" | ")}</div>}
                </div>
              ))}
            </div>
          )}
          {c.links.length > 0 && <div className="card"><h2>{t("Linked cases")}</h2>
            {c.links.map((l) => <p key={l.case_id} className="small"><Link to={`/cases/${l.case_id}`}><b>{l.case_id}</b></Link> ({l.unit}) · {t(l.kind.replace("_", " "))}</p>)}</div>}
        </div>
      </div>

      {modal === "action" && meta && (
        <Modal title={t("Record action")} onClose={() => setModal("")}>
          <div className="field"><label htmlFor="at">{t("What was done")}</label>
            <select id="at" value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
              <option value="">{t("Choose")}</option>
              {meta.action_types.map((a) => <option key={a.name} value={a.name}>{t(a.name)}{a.regulatory ? ` (${t("regulatory")})` : ""}</option>)}
            </select>
            {regulatory && <div className="hint">{t("Regulatory action: SAMANVAY first checks whether another unit is handling this institution.")}</div>}</div>
          <div className="field"><label htmlFor="rm">{t("Remarks")}</label><textarea id="rm" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} /></div>
          <div className="field"><label htmlFor="na">{t("Next action (optional)")}</label><input id="na" value={form.next_action} onChange={(e) => setForm({ ...form, next_action: e.target.value })} /></div>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button onClick={() => setModal("")}>{t("Cancel")}</button>
            <button className="btn-primary" disabled={!form.action_type} onClick={() => recordAction()}>{t("Save")}</button>
          </div>
        </Modal>
      )}
      {conflict && (
        <ReasonModal title={t("Another unit is handling this institution")} label={t("Why are you continuing? (kept in the audit log and sent to the other unit)")}
          button={t("Acknowledge and continue")} onClose={() => setConflict(null)} onDone={(r) => recordAction(r)}>
          <p className="problem">{t("Before you record '{a}', note that these cases are open in other units:", { a: t(conflict.action_type) })}</p>
          <table className="plain" style={{ margin: "10px 0 16px" }}>
            <thead><tr><th>{t("Case")}</th><th>{t("Unit")}</th><th>{t("Category")}</th><th>{t("Last action")}</th></tr></thead>
            <tbody>{conflict.cases.map((x) => <tr key={x.case_id}><td><Link to={`/cases/${x.case_id}`} target="_blank">{x.case_id}</Link></td>
              <td>{x.unit}{x.officer && <div className="small muted">{x.officer}</div>}</td><td>{t(x.category)}</td><td>{x.last_action ? t(x.last_action) : "—"}</td></tr>)}</tbody>
          </table>
          <p className="small muted">{t("SAMANVAY never blocks you. You decide; the reason is recorded.")}</p>
        </ReasonModal>
      )}
      {modal === "assign" && meta && (
        <Modal title={t("Assign an officer")} onClose={() => setModal("")}>
          <div className="stack">{meta.officers.filter((o) => o.unit_id === meta.units.find((u) => u.code === c.unit)?.id).map((o) =>
            <button key={o.id} style={{ width: "100%", justifyContent: "flex-start" }} onClick={() => run(() => api(`/cases/${c.case_id}/assign`, { body: { officer_id: o.id } }), t("Assigned.")).then((r) => r && done(t("Assigned.")))}>{o.name}</button>)}</div>
        </Modal>
      )}
      {modal === "remark" && <RemarkModal refId={c.case_id} onClose={() => setModal("")} onDone={() => done(t("Remark added."))} />}
      {modal === "transfer" && meta && <TransferModal meta={meta} c={c} onClose={() => setModal("")} onDone={() => done(t("Transfer asked. The receiving head must accept it."))} />}
      {modal === "escalate" && <ReasonModal title={t("Escalate")} label={t("Why escalate?")} button={t("Escalate")} onClose={() => setModal("")}
        onDone={(r) => run(() => api(`/cases/${c.case_id}/escalate`, { body: { reason: r } })).then((x) => x && done(t("Escalated.")))} />}
      {modal === "dispose" && <ReasonModal title={t("Dispose of the case")} label={t("Decision")} button={t("Dispose")} onClose={() => setModal("")}
        onDone={(r) => run(() => api(`/cases/${c.case_id}/dispose`, { body: { reason: r } })).then((x) => x && done(t("Case disposed.")))} />}
      {modal === "return" && <ReasonModal title={t("Return the transfer")} label={t("Why does this case not belong to your unit?")} button={t("Return")} onClose={() => setModal("")}
        onDone={(r) => run(() => api(`/cases/${c.case_id}/transfer/decide`, { body: { accept: false, note: r } })).then((x) => x && done(t("Transfer returned.")))} />}
    </Page>
  );
}

function Suggestion({ c, onDone }: { c: Detail; onDone: (m: string) => void }) {
  const { t } = useApp();
  const { run, busy } = useAct();
  const s = c.suggestion!;
  const go = (accept: boolean) => run(() => api(`/cases/${c.case_id}/confirm-institution`, { body: { accept, institution_id: s.institution.id } }))
    .then((r) => r && onDone(accept ? t("Institution confirmed. The typed name is saved as an alias.") : t("Suggestion rejected.")));
  return (
    <div className="suggest" style={{ marginBottom: 16 }}>
      <div className="spread"><b>{t("Suggested institution")}</b><span><ScoreMeter score={s.score} line={88} /> <RuleTag /></span></div>
      <p style={{ margin: "6px 0" }}>{t("Typed")}: <span className="hl">{c.raw_institution_text}</span> → <b>{s.institution.name}</b> ({s.institution.aicte_id}, {s.institution.city})</p>
      <ul className="why small">{s.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
      {c.can_edit && <div className="row" style={{ marginTop: 10 }}>
        <button className="btn-primary" disabled={busy} onClick={() => go(true)}>{t("Confirm match")}</button>
        <button disabled={busy} onClick={() => go(false)}>{t("Not this institution")}</button>
      </div>}
    </div>
  );
}

function RemarkModal({ refId, onClose, onDone }: { refId: string; onClose: () => void; onDone: () => void }) {
  const { t } = useApp();
  const { run, busy } = useAct();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <Modal title={t("Add remark or file")} onClose={onClose}>
      <div className="field"><label htmlFor="rt">{t("Remark")}</label><textarea id="rt" value={text} onChange={(e) => setText(e.target.value)} /></div>
      <div className="field"><label htmlFor="rf">{t("Attachment (PDF, image, text; up to 5 MB)")}</label><input id="rf" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} /></div>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button onClick={onClose}>{t("Cancel")}</button>
        <button className="btn-primary" disabled={busy || (!text.trim() && !file)} onClick={() => {
          const f = new FormData(); f.append("text", text); if (file) f.append("file", file);
          run(() => api(`/cases/${refId}/remark`, { form: f })).then((r) => r && onDone());
        }}>{t("Save")}</button>
      </div>
    </Modal>
  );
}

function TransferModal({ meta, c, onClose, onDone }: { meta: Meta; c: Detail; onClose: () => void; onDone: () => void }) {
  const { t } = useApp();
  const { run } = useAct();
  const [to, setTo] = useState("");
  return (
    <ReasonModal title={t("Transfer to another unit")} label={t("Reason for the transfer")} button={t("Ask for transfer")} onClose={onClose}
      onDone={(r) => to ? run(() => api(`/cases/${c.case_id}/transfer`, { body: { to_unit_id: Number(to), reason: r } })).then((x) => x && onDone()) : Promise.resolve()}>
      <div className="field"><label htmlFor="tu">{t("To unit")}</label>
        <select id="tu" value={to} onChange={(e) => setTo(e.target.value)}><option value="">{t("Choose")}</option>
          {meta.units.filter((u) => u.code !== c.unit).map((u) => <option key={u.id} value={u.id}>{u.code} · {t(u.name)}</option>)}</select>
        <div className="hint">{t("The head of the receiving unit must accept. Until then the case shows as Transferred.")}</div></div>
      <Stamp label="Transfer needs acceptance" kind="wait" />
    </ReasonModal>
  );
}
