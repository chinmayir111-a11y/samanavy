import { useNavigate } from "react-router-dom";
import { useApp } from "../app";
import { day } from "../format";
import { CaseStamp, SlaChip, caseStamp, type Row } from "./ui";

export type CaseRow = Row & {
  id: number; case_id: string; institution_name: string; institution: { id: number; aicte_id: string } | null;
  suggestion_status: string; received_on: string; category: string; unit: string; officer: string | null;
  last_action: string; last_action_on: string | null; next_action: string; expected_disposal_on: string;
  holder: { unit: string; officer: string | null; days: number; text: string };
  sla: Row["sla"] & { pct_used: number; age: number; bucket: string };
};

/** Register-style list: a table on wide screens, cards on phones. One filled stamp per list. */
export function CaseList({ rows, showUnit = true }: { rows: CaseRow[]; showUnit?: boolean }) {
  const { t } = useApp();
  const nav = useNavigate();
  const first = rows.findIndex((r) => caseStamp(r).kind === "act");
  const open = (r: CaseRow) => nav(`/cases/${r.case_id}`);
  return (
    <div className="card ledger-wrap" style={{ padding: 0, overflow: "hidden" }}>
      <table className="ledger">
        <thead><tr>
          <th>{t("Case")}</th><th>{t("Institution")}</th><th>{t("Category")}</th>
          {showUnit && <th>{t("Who is acting now")}</th>}<th>{t("Last action")}</th><th>{t("Due")}</th><th>{t("Status")}</th>
        </tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id} className="clickable" onClick={() => open(r)}>
              <td><a href={`/cases/${r.case_id}`} onClick={(e) => { e.preventDefault(); open(r); }}><b className="num">{r.case_id}</b></a>
                <div className="sub">{t("Received")} {day(r.received_on)}</div></td>
              <td>{r.institution_name}{r.suggestion_status === "suggested" && <div className="sub">{t("Typed name, not confirmed")}</div>}</td>
              <td>{t(r.category)}</td>
              {showUnit && <td><span className="holder"><b>{r.holder.unit}</b> · {r.holder.officer || t("not assigned")} · {t("{n} days", { n: r.holder.days })}</span></td>}
              <td>{r.last_action ? t(r.last_action) : <span className="muted">{t("None yet")}</span>}
                {r.last_action_on && <div className="sub">{day(r.last_action_on)}</div>}</td>
              <td><SlaChip sla={r.sla} done={r.status === "DISPOSED"} />{r.status === "DISPOSED" && <span className="muted small">{day(r.expected_disposal_on)}</span>}</td>
              <td><CaseStamp r={r} quiet={i !== first} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ledger-cards">
        {rows.map((r, i) => (
          <div key={r.id} className="lcard" onClick={() => open(r)} role="link" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && open(r)}>
            <div className="spread"><b className="num">{r.case_id}</b><CaseStamp r={r} quiet={i !== first} /></div>
            <div>{r.institution_name}</div>
            <div className="small muted">{t(r.category)} · {r.holder.unit} · {r.holder.officer || t("not assigned")} · {t("{n} days", { n: r.holder.days })}</div>
            <div style={{ marginTop: 4 }}><SlaChip sla={r.sla} done={r.status === "DISPOSED"} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
