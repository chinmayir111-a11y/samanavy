import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../app";

/* ---------------------------------------------------------------- icons */
type IconName = "check" | "warn" | "x" | "clock" | "doc" | "dot" | "link";
export function Icon({ name, className }: { name: IconName; className?: string }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" width="1em" height="1em">
      {name === "check" && <path {...p} d="M5 12.5l4.5 4.5L19 7.5" />}
      {name === "warn" && <g {...p}><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17.5v.5" /></g>}
      {name === "x" && <g {...p}><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></g>}
      {name === "clock" && <g {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></g>}
      {name === "doc" && <g {...p}><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /></g>}
      {name === "dot" && <circle cx="12" cy="12" r="4" fill="currentColor" />}
      {name === "link" && <g {...p}><path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" /></g>}
    </svg>
  );
}

/* --------------------------------------------------------------- stamps */
// act  = needs action -> filled clay (one per group; `quiet` turns the rest to outlined)
// wait = waiting      -> outlined ink
// done = done/fine    -> dashed grey
export type Kind = "act" | "wait" | "done";
export function Stamp({ label, kind = "wait", quiet, icon }: { label: string; kind?: Kind; quiet?: boolean; icon?: IconName }) {
  const { t } = useApp();
  const cls = kind === "act" && quiet ? "wait" : kind;
  return <span className={`stamp ${cls}`}>{icon && <Icon name={icon} />}{t(label)}</span>;
}

export type Row = { status: string; status_label: string; has_overlap?: boolean; transfer_to?: string | null;
  sla: { overdue: boolean; days_left: number; label: string; stage: number } };

/** The stamp for a case: what matters most first (overdue, overlap, transfer, then status). */
export function caseStamp(r: Row): { label: string; kind: Kind; icon: IconName } {
  if (r.status === "DISPOSED") return { label: "Disposed", kind: "done", icon: "check" };
  if (r.sla.overdue) return { label: `${-r.sla.days_left} days overdue`, kind: "act", icon: "warn" };
  if (r.has_overlap) return { label: "Overlap", kind: "act", icon: "link" };
  if (r.transfer_to) return { label: `Transfer to ${r.transfer_to}`, kind: "wait", icon: "clock" };
  if (r.status === "ESCALATED") return { label: "Escalated", kind: "act", icon: "warn" };
  return { label: r.status_label, kind: "wait", icon: "clock" };
}

export function CaseStamp({ r, quiet }: { r: Row; quiet?: boolean }) {
  const { t } = useApp();
  const s = caseStamp(r);
  const m = s.label.match(/^(\d+) days overdue$/);
  return <Stamp label={m ? t("{n} days overdue", { n: m[1] }) : s.label} kind={s.kind} icon={s.icon} quiet={quiet} />;
}

/** U5 SLA countdown chip. */
export function SlaChip({ sla, done }: { sla: { days_left: number; pct_used: number; overdue: boolean }; done?: boolean }) {
  const { t } = useApp();
  if (done) return null;
  const text = sla.overdue ? t("{n} days past due", { n: -sla.days_left }) : sla.days_left === 0 ? t("Due today")
    : t("{n} days left", { n: sla.days_left });
  return (
    <span className={`chip ${sla.overdue ? "late" : sla.pct_used >= 75 ? "near" : ""}`} title={t("{p}% of the SLA used", { p: sla.pct_used })}>
      <Icon name="clock" /> {text}
    </span>
  );
}

/** "Rule-based matching" tag (U9): the score is never called AI. */
export function RuleTag() {
  const { t } = useApp();
  return <span className="tag-rule" title={t("Score from transparent rules: institution ID and name, category, text similarity and dates. Not machine learning.")}>{t("Rule-based matching")}</span>;
}

/* ---------------------------------------------------------- page bits */
export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="spread" style={{ marginBottom: 20, alignItems: "flex-start" }}>
      <div style={{ minWidth: 0, flex: "1 1 320px" }}>
        <h1>{title}</h1>
        {sub && <p className="muted" style={{ marginBottom: 0 }}>{sub}</p>}
      </div>
      {right && <div className="row">{right}</div>}
    </div>
  );
}

export function Skeleton({ lines = 4 }: { lines?: number }) {
  const { t } = useApp();
  return <div aria-busy="true" aria-label={t("Loading")}>{Array.from({ length: lines }).map((_, i) =>
    <div key={i} className="skel" style={{ width: `${90 - i * 12}%` }} />)}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty"><Art /><p style={{ marginTop: 12 }}>{children}</p></div>;
}

export function Modal({ title, children, onClose, wide }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const f = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", f);
    ref.current?.querySelector<HTMLElement>("textarea, input, select, button")?.focus();
    return () => document.removeEventListener("keydown", f);
  }, [onClose]);
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" style={wide ? { maxWidth: 760 } : undefined} role="dialog" aria-modal="true" aria-label={title} ref={ref} onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

/** Ask for a written reason, then run. Used for every decision that is logged. */
export function ReasonModal({ title, label, hint, button, min = 10, onDone, onClose, children }: {
  title: string; label: string; hint?: string; button: string; min?: number; children?: ReactNode;
  onDone: (text: string) => Promise<unknown>; onClose: () => void;
}) {
  const { t } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const short = text.trim().length < min;
  return (
    <Modal title={title} onClose={onClose}>
      {children}
      <div className="field">
        <label htmlFor="reason">{label}</label>
        <textarea id="reason" value={text} onChange={(e) => setText(e.target.value)} />
        {hint && <div className="hint">{hint}</div>}
      </div>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button onClick={onClose}>{t("Cancel")}</button>
        <button className="btn-primary" disabled={short || busy}
          onClick={async () => { setBusy(true); await onDone(text.trim()); setBusy(false); }}>{button}</button>
      </div>
      {short && text.length > 0 && <div className="hint">{t("Please write at least {n} characters. It is kept in the audit log.", { n: min })}</div>}
    </Modal>
  );
}

export function CountUp({ value }: { value: number }) {
  const [n, setN] = useState(value);
  const prev = useRef(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setN(value); return; }
    const from = prev.current, start = performance.now();
    prev.current = value;
    let raf = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 600);
      setN(Math.round(from + (value - from) * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{n.toLocaleString("en-IN")}</>;
}

/* ------------------------------------------------- 5-step progress strip */
export type Step = { n: number; label: string; state: "done" | "current" | "upcoming" };
export function ProgressStrip({ steps, now }: { steps: Step[]; now: string }) {
  const { t } = useApp();
  const cur = steps.find((x) => x.state === "current");
  return (
    <div className="pstrip">
      <ol className="pstrip-row" aria-label={t("Progress")}>
        {steps.map((x, i) => (
          <li key={x.n} className={`pstep ${x.state}`}>
            {i > 0 && <span className={`pline ${x.state !== "upcoming" ? "solid" : "dashed"}`} aria-hidden="true" />}
            <span className="pdot" role="img" aria-current={x.state === "current" ? "step" : undefined}
              aria-label={t("Step {n} of 5: {label}", { n: x.n, label: t(x.label) }) + (x.state === "done" ? t(", done") : x.state === "upcoming" ? t(", not yet") : "")}>
              {x.state === "done" ? <Icon name="check" /> : x.n}
            </span>
            <span className="plabel">{t(x.label)}</span>
            {x.state === "current" && <span className="pdetail">{now}</span>}
          </li>
        ))}
      </ol>
      <p className="pstrip-now" aria-hidden="true">
        {cur ? <><b>{t("Step {n} of 5: {label}", { n: cur.n, label: t(cur.label) })}.</b> {now}</> : <b>{t("All steps done.")}</b>}
      </p>
    </div>
  );
}

/* --------------------------------------------------------------- bars */
export function Bars({ rows, max }: { rows: { label: string; value: number; note?: string; hot?: boolean; to?: string }[]; max?: number }) {
  const m = Math.max(1, max ?? Math.max(...rows.map((r) => r.value)));
  return (
    <div className="bars" role="list">
      {rows.map((r, i) => {
        const inner = <>
          <span>{r.label}</span>
          <span className="track"><span className="fill" style={{ display: "block", width: `${(r.value / m) * 100}%` }} /></span>
          <span className="num" style={{ textAlign: "right" }}>{r.value}{r.note && <span className="muted small"> · {r.note}</span>}</span>
        </>;
        return r.to ? <Link role="listitem" to={r.to} key={i} className={`bar-row ${r.hot ? "overdue" : ""}`} style={{ color: "inherit", textDecoration: "none" }}>{inner}</Link>
          : <div role="listitem" key={i} className={`bar-row ${r.hot ? "overdue" : ""}`}>{inner}</div>;
      })}
    </div>
  );
}

/** Score as a short ink meter, clay only above the alert line. */
export function ScoreMeter({ score, line = 65 }: { score: number; line?: number }) {
  return (
    <span className="score" aria-label={`${Math.round(score)} / 100`}>
      <span className="score-n serif">{Math.round(score)}</span><span className="muted small">/100</span>
      <span className="meter" style={{ width: 90, display: "inline-flex", verticalAlign: "middle", marginLeft: 8 }}>
        <i style={{ width: `${score}%`, background: score >= line ? "var(--accent)" : "var(--ink-2)" }} />
      </span>
    </span>
  );
}

/* ----------------------------------------------- original line drawing */
export function Art({ size = 96 }: { size?: number }) {
  return (
    <svg viewBox="0 0 120 80" width={size} height={(size * 80) / 120} aria-hidden="true">
      <g fill="none" strokeWidth="1.8" strokeLinecap="round">
        <rect x="8" y="14" width="44" height="54" rx="3" stroke="#2D5A43" fill="#fff" />
        <rect x="68" y="14" width="44" height="54" rx="3" stroke="#2D5A43" fill="#fff" />
        {[0, 1, 2].map((i) => <path key={i} d={`M16 ${28 + i * 10}h28M76 ${28 + i * 10}h28`} stroke="#D9E0D9" />)}
        <path d="M52 41h16" stroke="#6E9580" strokeDasharray="3 3" />
        <circle cx="60" cy="41" r="6" stroke="#6E9580" fill="#F7F8F3" />
      </g>
    </svg>
  );
}
