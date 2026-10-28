import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp, useLoad } from "../app";
import { CaseList, type CaseRow } from "../components/CaseList";
import { Page } from "../components/Shell";
import { Empty, Modal, PageHead, Skeleton } from "../components/ui";

export type Meta = { units: { id: number; code: string; name: string }[]; categories: { id: number; name: string; sla_days: number }[];
  action_types: { name: string; regulatory: boolean }[]; officers: { id: number; name: string; unit_id: number; role: string }[];
  regions: string[]; institutions: { id: number; name: string; aicte_id: string; city: string }[] };

const KEYS = ["q", "unit", "region", "category", "status", "date_from", "date_to", "overdue", "has_overlap"];

export default function Cases() {
  const { me, t } = useApp();
  const [p, setP] = useSearchParams();
  const meta = useLoad<Meta>("/meta").data;
  const qs = useMemo(() => {
    const u = new URLSearchParams();
    KEYS.forEach((k) => { const v = p.get(k); if (v) u.set(k, k === "overdue" || k === "has_overlap" ? "true" : v); });
    return u.toString();
  }, [p]);
  const { data, loading } = useLoad<CaseRow[]>(`/cases?${qs}`, [qs]);
  const [q, setQ] = useState(p.get("q") || "");
  useEffect(() => setQ(p.get("q") || ""), [p]);
  const set = (k: string, v: string) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); setP(n, { replace: true }); };
  const canCreate = me?.role === "desk_officer" || me?.role === "unit_head";

  return (
    <Page>
      <PageHead title={t("Cases")} sub={t("Filters are kept in the address bar, so you can share this exact view.")}
        right={canCreate ? <button className="btn-primary" onClick={() => set("new", "1")}>{t("Register a case")}</button> : undefined} />
      <form className="filters" onSubmit={(e) => { e.preventDefault(); set("q", q.trim()); }} role="search">
        <div className="wide"><label htmlFor="q">{t("Institution, AICTE ID or case number")}</label>
          <input id="q" value={q} onChange={(e) => setQ(e.target.value)} onBlur={() => set("q", q.trim())} placeholder={t("e.g. Narmada, 1-SYN-4410021, RB-2026-0012")} /></div>
        <Sel id="unit" label={t("Unit")} value={p.get("unit")} onChange={(v) => set("unit", v)} options={meta?.units.map((u) => [u.code, u.code]) ?? []} />
        <Sel id="region" label={t("Region")} value={p.get("region")} onChange={(v) => set("region", v)} options={meta?.regions.map((r) => [r, t(r)]) ?? []} />
        <Sel id="category" label={t("Category")} value={p.get("category")} onChange={(v) => set("category", v)} options={meta?.categories.map((c) => [c.name, t(c.name)]) ?? []} />
        <Sel id="status" label={t("Status")} value={p.get("status")} onChange={(v) => set("status", v)}
          options={[["OPEN", t("All open")], ["RECEIVED", t("Received")], ["UNDER_PROCESS", t("Under process")], ["TRANSFERRED", t("Transferred")], ["ESCALATED", t("Escalated")], ["DISPOSED", t("Disposed")]]} />
        <div><label htmlFor="df">{t("Received from")}</label><input id="df" type="date" value={p.get("date_from") || ""} onChange={(e) => set("date_from", e.target.value)} /></div>
        <div><label htmlFor="dt">{t("Received to")}</label><input id="dt" type="date" value={p.get("date_to") || ""} onChange={(e) => set("date_to", e.target.value)} /></div>
        <div className="checks">
          <label><input type="checkbox" checked={!!p.get("overdue")} onChange={(e) => set("overdue", e.target.checked ? "1" : "")} />{t("Overdue only")}</label>
          <label><input type="checkbox" checked={!!p.get("has_overlap")} onChange={(e) => set("has_overlap", e.target.checked ? "1" : "")} />{t("Has overlap")}</label>
        </div>
      </form>
      {loading && !data ? <Skeleton /> : data && data.length ? <>
        <p className="small muted">{t("{n} cases", { n: data.length })}{[...p.keys()].some((k) => KEYS.includes(k)) && <> · <button className="btn-quiet small" onClick={() => setP({}, { replace: true })}>{t("Clear filters")}</button></>}</p>
        <CaseList rows={data} />
      </> : <Empty>{t("No cases match these filters.")}</Empty>}
      {p.get("new") && meta && <NewCase meta={meta} onClose={() => set("new", "")} />}
    </Page>
  );
}

function Sel({ id, label, value, onChange, options }: { id: string; label: string; value: string | null; onChange: (v: string) => void; options: string[][] }) {
  const { t } = useApp();
  return <div><label htmlFor={id}>{label}</label>
    <select id={id} value={value || ""} onChange={(e) => onChange(e.target.value)}><option value="">{t("All")}</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>;
}

function NewCase({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const { t, toast } = useApp();
  const nav = useNavigate();
  const [f, setF] = useState({ institution_id: "", raw_institution_text: "", category_id: "", description: "", received_on: "", source_ref: "", priority: "Normal" });
  const [typed, setTyped] = useState(false);
  const [busy, setBusy] = useState(false);
  const up = (k: string, v: string) => setF({ ...f, [k]: v });
  const save = async () => {
    setBusy(true);
    try {
      const r = await api<{ case_id: string; suggestion_status: string }>("/cases", { body: {
        ...f, institution_id: typed ? null : Number(f.institution_id) || null, raw_institution_text: typed ? f.raw_institution_text : "",
        category_id: Number(f.category_id), received_on: f.received_on || null } });
      toast(t("Registered as {id}.", { id: r.case_id }));
      nav(`/cases/${r.case_id}`);
    } catch (e: any) { toast(e.message, true); } finally { setBusy(false); }
  };
  return (
    <Modal title={t("Register a case")} onClose={onClose} wide>
      <div className="field">
        <div className="radio-row" role="radiogroup">
          <label><input type="radio" checked={!typed} onChange={() => setTyped(false)} />{t("Pick the institution")}</label>
          <label><input type="radio" checked={typed} onChange={() => setTyped(true)} />{t("Type the name as written in the complaint")}</label>
        </div>
      </div>
      {typed ? <div className="field"><label htmlFor="raw">{t("Institution name as written")}</label>
        <input id="raw" value={f.raw_institution_text} onChange={(e) => up("raw_institution_text", e.target.value)} placeholder="Kaveri Inst. of Engg & Tech" />
        <div className="hint">{t("SAMANVAY will suggest the matching institution for you to confirm.")}</div></div>
        : <div className="field"><label htmlFor="inst">{t("Institution")}</label>
          <select id="inst" value={f.institution_id} onChange={(e) => up("institution_id", e.target.value)}><option value="">{t("Choose")}</option>
            {meta.institutions.map((i) => <option key={i.id} value={i.id}>{i.name} · {i.aicte_id}</option>)}</select></div>}
      <div className="fields2">
        <div className="field"><label htmlFor="cat">{t("Category")}</label>
          <select id="cat" value={f.category_id} onChange={(e) => up("category_id", e.target.value)}><option value="">{t("Choose")}</option>
            {meta.categories.map((c) => <option key={c.id} value={c.id}>{t(c.name)} ({t("{n} days", { n: c.sla_days })})</option>)}</select></div>
        <div className="field"><label htmlFor="rec">{t("Received on")}</label><input id="rec" type="date" value={f.received_on} onChange={(e) => up("received_on", e.target.value)} />
          <div className="hint">{t("Leave empty for today.")}</div></div>
        <div className="field"><label htmlFor="ref">{t("Your unit's file number")}</label><input id="ref" value={f.source_ref} onChange={(e) => up("source_ref", e.target.value)} /></div>
        <div className="field"><label htmlFor="pri">{t("Priority")}</label>
          <select id="pri" value={f.priority} onChange={(e) => up("priority", e.target.value)}>{["Normal", "High", "Urgent"].map((x) => <option key={x} value={x}>{t(x)}</option>)}</select></div>
      </div>
      <div className="field"><label htmlFor="desc">{t("What is the complaint?")}</label>
        <textarea id="desc" value={f.description} onChange={(e) => up("description", e.target.value)} /></div>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button onClick={onClose}>{t("Cancel")}</button>
        <button className="btn-primary" disabled={busy || !f.category_id || f.description.trim().length < 15 || (typed ? !f.raw_institution_text.trim() : !f.institution_id)} onClick={save}>{t("Register")}</button>
      </div>
    </Modal>
  );
}
