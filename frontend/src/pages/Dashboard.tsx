import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useApp, useLoad } from "../app";
import { Page } from "../components/Shell";
import { Bars, CountUp, PageHead, Skeleton } from "../components/ui";
import { day } from "../format";

type D = {
  today: string; disposal_rate: number; disposed_in_time_pct: number; avg_open_age: number;
  totals: Record<string, number>; ageing: { bucket: string; count: number }[];
  workload: { unit: string; open: number; overdue: number; disposed: number }[];
  institutions: { id: number | null; name: string; region: string; open: number; overdue: number; units: string[] }[];
  alerts: { open: number; coordinated: number; dismissed: number };
  by_state: { state: string; region: string; institutions: number; open: number;
    cities: { city: string; district: string; open: number; institutions: { id: number; name: string; open: number; verified: boolean }[] }[] }[];
};
const KPI: [string, string, string][] = [["received", "Total received", "/cases"], ["pending", "Pending", "/cases?status=OPEN"],
  ["under_process", "Under process", "/cases?status=UNDER_PROCESS"], ["disposed", "Disposed", "/cases?status=DISPOSED"],
  ["transferred", "Transferred", "/cases?status=TRANSFERRED"], ["escalated", "Escalated", "/cases?status=ESCALATED"],
  ["overdue", "Overdue", "/cases?overdue=1&status=OPEN"], ["open_alerts", "Open overlap alerts", "/overlaps"]];

export default function Dashboard() {
  const { t } = useApp();
  const { data: d, reload } = useLoad<D>("/dashboard");
  useEffect(() => { const id = setInterval(reload, 30000); return () => clearInterval(id); }, [reload]);
  if (!d) return <Page><Skeleton lines={8} /></Page>;
  return (
    <Page>
      <PageHead title={t("Dashboard")} sub={t("As of {d}. Refreshes every 30 seconds.", { d: day(d.today) })} />
      <div className="kpis eight">
        {KPI.map(([k, l, to]) => (
          <Link key={k} to={to} className="kpi" style={{ textDecoration: "none", ...(k === "overdue" && d.totals[k] ? { borderColor: "var(--accent)" } : {}) }}>
            <div className="n" style={k === "overdue" && d.totals[k] ? { color: "var(--accent)" } : undefined}><CountUp value={d.totals[k]} /></div>
            <div className="l">{t(l)}</div>
          </Link>
        ))}
      </div>
      <div className="kpis" style={{ marginTop: 12 }}>
        <div className="kpi"><div className="n">{d.disposal_rate}%</div><div className="l">{t("Disposal rate")}</div></div>
        <div className="kpi"><div className="n">{d.disposed_in_time_pct}%</div><div className="l">{t("Disposed within SLA")}</div></div>
        <div className="kpi"><div className="n">{d.avg_open_age}</div><div className="l">{t("Average age of open cases (days)")}</div></div>
        <div className="kpi"><div className="n">{d.alerts.coordinated}</div><div className="l">{t("Overlaps coordinated")}</div></div>
      </div>
      <div className="grid2" style={{ marginTop: 20 }}>
        <div className="card">
          <h2>{t("Unit-wise workload (open cases)")}</h2>
          <Bars rows={d.workload.map((w) => ({ label: w.unit, value: w.open, note: t("{n} overdue", { n: w.overdue }), to: `/cases?unit=${w.unit}&status=OPEN` }))} />
        </div>
        <div className="card">
          <h2>{t("Case ageing (open)")}</h2>
          <Bars rows={d.ageing.map((a) => ({ label: t("{b} days", { b: a.bucket }), value: a.count, hot: a.bucket === "60+" }))} />
        </div>
      </div>
      <div className="card" style={{ marginTop: 20 }}>
        <h2>{t("Institution-wise status (open cases)")}</h2>
        <div className="scroll-x"><table className="plain">
          <thead><tr><th>{t("Institution")}</th><th>{t("Region")}</th><th>{t("Open")}</th><th>{t("Overdue")}</th><th>{t("Units involved")}</th></tr></thead>
          <tbody>{d.institutions.map((i) => (
            <tr key={i.name}><td>{i.id ? <Link to={`/institutions/${i.id}`}>{i.name}</Link> : i.name}</td><td>{t(i.region)}</td><td>{i.open}</td>
              <td style={i.overdue ? { color: "var(--accent)", fontWeight: 700 } : undefined}>{i.overdue}</td>
              <td>{i.units.join(", ")}{i.units.length > 1 && <span className="muted small"> · {t("more than one unit")}</span>}</td></tr>
          ))}</tbody>
        </table></div>
      </div>
      <div className="card" style={{ marginTop: 20 }}>
        <h2>{t("By state and city")}</h2>
        <p className="small muted">{t("Every institution on the register, including colleges added by people signing up (marked new).")}</p>
        {d.by_state.map((s) => (
          <details key={s.state} className="geo">
            <summary><b>{s.state}</b> <span className="muted small">· {s.region ? t("{r} region", { r: t(s.region) }) : t("region not set")} · {t("{n} institutions", { n: s.institutions })} · {t("{n} open cases", { n: s.open })}</span></summary>
            <table className="plain"><tbody>{s.cities.map((c) => <tr key={c.city}><td><b>{c.city}</b>{c.district && <div className="small muted">{t("{d} district", { d: c.district })}</div>}</td>
              <td>{c.institutions.map((i) => <div key={i.id}><Link to={`/institutions/${i.id}`}>{i.name}</Link>{!i.verified && <span className="small muted"> · {t("new, not yet checked")}</span>} <span className="small muted">· {i.open}</span></div>)}</td>
              <td>{c.open}</td></tr>)}</tbody></table>
          </details>
        ))}
      </div>
    </Page>
  );
}
