import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiBase } from "../api";
import { useApp, useLoad } from "../app";
import { Page } from "../components/Shell";
import { Empty, ProgressStrip, Skeleton, type Step } from "../components/ui";
import { dateTime, day } from "../format";

type Cat = { key: string; label: string; example: string };
type Draft = { category_key: string; description: string; happened_on: string };
const DRAFT = "smv_complaint_draft";
export const MIN_CHARS = 20;
export const MAX_MB = 5;
const OK_TYPES = [".pdf", ".jpg", ".jpeg", ".png"];

function loadDraft(): Draft {
  try { return { category_key: "", description: "", happened_on: "", ...JSON.parse(localStorage.getItem(DRAFT) || "{}") }; }
  catch { return { category_key: "", description: "", happened_on: "" }; }
}

/** Plain-language checks shared by the wizard and its tests. */
export function stepProblems(step: number, d: Draft, files: File[], t: (k: string, p?: any) => string): string[] {
  const out: string[] = [];
  if (step === 1) {
    if (!d.category_key) out.push(t("Choose what the complaint is about."));
    if (d.description.trim().length < MIN_CHARS) out.push(t("Please write at least {n} characters so the officer understands the problem.", { n: MIN_CHARS }));
    if (d.happened_on && d.happened_on > new Date().toISOString().slice(0, 10)) out.push(t("The date cannot be in the future."));
  }
  if (step === 2) {
    if (files.length > 5) out.push(t("Up to 5 files."));
    for (const f of files) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!OK_TYPES.includes(ext)) out.push(t("'{f}': only PDF, JPG and PNG files can be added.", { f: f.name }));
      else if (f.size > MAX_MB * 1024 * 1024) out.push(t("'{f}' is larger than {n} MB.", { f: f.name, n: MAX_MB }));
    }
  }
  return out;
}

export function FileComplaint() {
  const { me, t, toast } = useApp();
  const nav = useNavigate();
  const cats = useLoad<Cat[]>("/my/categories").data;
  const [step, setStep] = useState(1);
  const [d, setD] = useState<Draft>(loadDraft);
  const [files, setFiles] = useState<File[]>([]);
  const [shown, setShown] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { try { localStorage.setItem(DRAFT, JSON.stringify(d)); } catch { /* autosave is a convenience */ } }, [d]);
  useEffect(() => { setShown((x) => (x.length ? stepProblems(step, d, files, t) : x)); }, [d, files, step, t]);
  const next = () => { const p = stepProblems(step, d, files, t); setShown(p); if (!p.length) setStep(step + 1); };
  const submit = async () => {
    setBusy(true);
    try {
      const r = await api<{ reference: string }>("/my/complaints", { body: { ...d, happened_on: d.happened_on || null } });
      if (files.length) {
        const fd = new FormData();
        files.forEach((f) => fd.append("files", f));
        await api(`/my/complaints/${r.reference}/files`, { form: fd }).catch((e) => toast(t("Complaint saved, but a file was not added: {m}", { m: e.message }), true));
      }
      try { localStorage.removeItem(DRAFT); } catch { /* ignore */ }
      nav(`/my/${r.reference}/done`);
    } catch (e: any) { setShown([e.message]); } finally { setBusy(false); }
  };
  const cat = cats?.find((c) => c.key === d.category_key);
  return (
    <Page>
      <div className="wizard" data-testid="wizard">
        <p className="small muted">{t("Step {n} of 3", { n: step })} · {t("Your answers are saved on this device as you type.")}</p>
        <div className="steps-head" aria-hidden="true">{["What happened?", "Proof (optional)", "Check and submit"].map((x, i) =>
          <span key={x} className={step === i + 1 ? "on" : step > i + 1 ? "done" : ""}>{t(x)}</span>)}</div>
        {step === 1 && <>
          <h1>{t("What happened?")}</h1>
          <fieldset className="field"><legend>{t("What is it about?")}</legend>
            <div className="cat-grid">{cats?.map((c) => (
              <label key={c.key} className={`cat ${d.category_key === c.key ? "on" : ""}`}>
                <input type="radio" name="cat" checked={d.category_key === c.key} onChange={() => setD({ ...d, category_key: c.key })} />
                <b>{t(c.label)}</b><span className="small muted">{t(c.example)}</span>
              </label>))}</div></fieldset>
          <div className="field"><label htmlFor="desc">{t("Tell us the problem in your own words")}</label>
            <textarea id="desc" rows={6} value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} aria-describedby="desc-count" />
            <div className="hint" id="desc-count">{d.description.trim().length < MIN_CHARS ? t("{n} more characters needed", { n: MIN_CHARS - d.description.trim().length }) : t("{n} characters", { n: d.description.trim().length })} · {t("Say what happened, when, and who was involved. Do not include passwords or bank details.")}</div></div>
          <div className="field" style={{ maxWidth: 260 }}><label htmlFor="when">{t("When did it happen? (optional)")}</label>
            <input id="when" type="date" value={d.happened_on} onChange={(e) => setD({ ...d, happened_on: e.target.value })} /></div>
        </>}
        {step === 2 && <>
          <h1>{t("Proof (optional)")}</h1>
          <p className="muted">{t("Photos of receipts, notices or letters help. You can skip this.")}</p>
          <div className="field"><label htmlFor="files">{t("Add files: PDF, JPG or PNG, up to {n} MB each, 5 files at most", { n: MAX_MB })}</label>
            <input id="files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              onChange={(e) => { const list = Array.from(e.target.files || []); setFiles(list); setShown(stepProblems(2, d, list, t)); }} /></div>
          {files.length > 0 && <ul className="small">{files.map((f) => <li key={f.name}>{f.name} · {(f.size / 1024 / 1024).toFixed(2)} MB</li>)}</ul>}
        </>}
        {step === 3 && <>
          <h1>{t("Check and submit")}</h1>
          <dl className="dl card">
            <dt>{t("About")}</dt><dd>{cat ? t(cat.label) : "—"}</dd>
            <dt>{t("What happened")}</dt><dd style={{ whiteSpace: "pre-line" }}>{d.description}</dd>
            {d.happened_on && <><dt>{t("When")}</dt><dd>{day(d.happened_on)}</dd></>}
            <dt>{t("Files")}</dt><dd>{files.length ? files.map((f) => f.name).join(", ") : t("None")}</dd>
            <dt>{t("College")}</dt><dd>{me?.institution?.name || "—"}{me?.institution?.city && <span className="muted"> · {me.institution.city}{me.institution.state ? `, ${me.institution.state}` : ""}</span>}</dd>
          </dl>
          <p className="note" style={{ marginTop: 12 }}>{t("Who can see this: only AICTE officers handling it. The college is not shown your name by SAMANVAY. The public status page shows only the status, never your name or words.")}</p>
        </>}
        {shown.length > 0 && <div className="err-box" role="alert">{shown.map((s) => <p key={s} className="err" style={{ margin: 0 }}>{s}</p>)}</div>}
        <div className="row" style={{ marginTop: 18 }}>
          {step > 1 && <button className="btn-big" onClick={() => { setShown([]); setStep(step - 1); }}>{t("Back")}</button>}
          {step < 3 ? <button className="btn-primary btn-big" style={{ flex: 1 }} onClick={next}>{step === 2 && !files.length ? t("Skip and continue") : t("Next")}</button>
            : <button className="btn-primary btn-big" style={{ flex: 1 }} disabled={busy} onClick={submit}>{t("Submit complaint")}</button>}
        </div>
      </div>
    </Page>
  );
}

export function ComplaintDone() {
  const { ref } = useParams();
  const { t } = useApp();
  return (
    <Page>
      <div className="wizard" style={{ textAlign: "center" }}>
        <p className="label-caps">{t("Your complaint is registered")}</p>
        <h1 className="num" style={{ fontSize: "2rem" }} data-testid="reference">{ref}</h1>
        <img src={`${apiBase}/public/qr/${ref}.svg`} alt={t("QR code to check the status of {r}", { r: ref })} width={150} height={150} style={{ margin: "8px auto", display: "block" }} />
        <p className="small muted">{t("Keep this number. Scan the code to check the status from any phone.")}</p>
        <div className="card" style={{ textAlign: "left", margin: "16px 0" }}>
          <h2>{t("What happens next")}</h2>
          <ol className="next3">
            <li>{t("Received: it is in AICTE's register now.")}</li>
            <li>{t("It is given to the AICTE unit that handles this kind of complaint.")}</li>
            <li>{t("We will email you each time it moves.")}</li>
          </ol>
        </div>
        <Link className="btn btn-primary btn-big" to={`/my/${ref}`}>{t("Track this complaint")}</Link>
      </div>
    </Page>
  );
}

type Mine = { reference: string; about: string; college: string; received_on: string; status: string };

export function MyComplaints() {
  const { t } = useApp();
  const { data } = useLoad<Mine[]>("/my/complaints");
  return (
    <Page>
      <div className="spread" style={{ marginBottom: 16 }}><h1>{t("My complaints")}</h1><Link className="btn btn-primary" to="/file">{t("File a complaint")}</Link></div>
      {!data ? <Skeleton /> : data.length ? <div className="card" style={{ padding: 0 }}>{data.map((c) => (
        <Link key={c.reference} to={`/my/${c.reference}`} className="lcard" style={{ display: "block", color: "inherit", textDecoration: "none" }}>
          <div className="spread"><b className="num">{c.reference}</b><span className="stamp wait">{t(c.status)}</span></div>
          <div>{t(c.about)} · {c.college}</div><div className="small muted">{t("Sent on {d}", { d: day(c.received_on) })}</div>
        </Link>))}</div> : <Empty>{t("You have not filed a complaint yet.")}</Empty>}
    </Page>
  );
}

type Track = { reference: string; about: string; description: string; college: string; received_on: string; status: string; unit: string;
  days_waiting: number; age: number; steps: Step[]; messages: { at: string; text: string }[]; files: string[] };

export function TrackComplaint() {
  const { ref } = useParams();
  const { t } = useApp();
  const { data: c } = useLoad<Track>(`/my/complaints/${ref}`, [ref]);
  if (!c) return <Page><Skeleton lines={6} /></Page>;
  const now = c.status === "Closed" ? t("Closed") : t("With the {u}, {n} days", { u: t(c.unit), n: c.days_waiting });
  return (
    <Page>
      <p className="small"><Link to="/my">{t("My complaints")}</Link> / {c.reference}</p>
      <h1 className="num">{c.reference}</h1>
      <p>{t(c.about)} · {c.college} · {t("sent on {d}", { d: day(c.received_on) })}</p>
      <div className="todo"><div className="label">{t("Where it is now")}</div>
        <div className="big" style={{ marginBottom: 0 }}>{t(c.status)}. {c.status !== "Closed" && t("It is with the {u} and has waited {n} days there.", { u: t(c.unit), n: c.days_waiting })}</div></div>
      <ProgressStrip steps={c.steps} now={now} />
      <div className="grid2" style={{ marginTop: 16 }}>
        <div className="card"><h2>{t("Messages")}</h2>
          <ol className="timeline">{c.messages.map((m, i) => <li key={i}><div className="small muted">{dateTime(m.at)}</div><div>{t(m.text)}</div></li>)}</ol></div>
        <div className="card"><h2>{t("What you told us")}</h2><p style={{ whiteSpace: "pre-line" }}>{c.description}</p>
          {c.files.length > 0 && <p className="small muted">{t("Files")}: {c.files.join(", ")}</p>}
          <p className="small"><Link to={`/check/${c.reference}`}>{t("Public status page")}</Link> <span className="muted">· {t("shows status only")}</span></p></div>
      </div>
    </Page>
  );
}
