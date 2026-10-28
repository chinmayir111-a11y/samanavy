import { Link } from "react-router-dom";
import { useApp, useLoad } from "../app";
import { CaseList, type CaseRow } from "../components/CaseList";
import { Page } from "../components/Shell";
import { Empty, PageHead, Skeleton } from "../components/ui";

type Today = { rows: CaseRow[]; need_count: number; overdue: number; open_alerts: number; unmatched: number; what_now: string };

function whatNow(d: Today, coord: boolean, t: (k: string, p?: any) => string) {
  const parts = [];
  if (d.need_count) parts.push(d.need_count === 1 ? t("1 case needs action today") : t("{n} cases need action today", { n: d.need_count }));
  if (coord && d.open_alerts) parts.push(t("{n} overlap alerts to decide", { n: d.open_alerts }));
  if (d.unmatched) parts.push(t("{n} typed institution names to confirm", { n: d.unmatched }));
  return parts.length ? parts.join(", ") + "." : t("Nothing urgent today. Your register is up to date.");
}

export default function TodayPage() {
  const { me, t } = useApp();
  const { data } = useLoad<Today>("/today");
  const title = me?.role === "coordinator" ? t("Coordination desk") : t("Today's register");
  return (
    <Page>
      <PageHead title={title} sub={me?.unit ? `${me.name} · ${me.unit.name}` : me?.name}
        right={me?.role !== "coordinator" ? <Link className="btn btn-strong" to="/cases?new=1">{t("Register a case")}</Link> : undefined} />
      {!data ? <Skeleton /> : <>
        <div className="todo" style={{ marginBottom: 20 }}>
          <div className="label">{t("What to do now")}</div>
          <div className="big">{whatNow(data, me?.role === "coordinator", t)}</div>
          <div className="row">
            {data.open_alerts > 0 && <Link className="btn btn-primary" to="/overlaps">{t("Open overlap alerts ({n})", { n: data.open_alerts })}</Link>}
            {data.overdue > 0 && <Link className="btn" to="/cases?overdue=1&status=OPEN">{t("Overdue cases ({n})", { n: data.overdue })}</Link>}
            {data.unmatched > 0 && <Link className="btn" to="/cases?status=OPEN&q=">{t("Names to confirm ({n})", { n: data.unmatched })}</Link>}
          </div>
        </div>
        <h2>{t("Most urgent first")}</h2>
        {data.rows.length ? <CaseList rows={data.rows} /> : <Empty>{t("No open cases with you. Well done.")}</Empty>}
      </>}
    </Page>
  );
}
