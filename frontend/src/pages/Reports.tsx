import { useState } from "react";
import { download } from "../api";
import { useApp, useLoad } from "../app";
import { Page } from "../components/Shell";
import { PageHead, Skeleton } from "../components/ui";
import { day } from "../format";

type R = { key: string; title: string; head: string[]; rows: (string | number)[][]; as_of: string };

export default function Reports() {
  const { t, toast } = useApp();
  const list = useLoad<{ key: string; title: string }[]>("/reports").data;
  const [k, setK] = useState("unit");
  const { data } = useLoad<R>(`/reports/${k}`, [k]);
  const get = (fmt: "csv" | "pdf") => download(`/reports/${k}/${fmt}`, `samanvay-${k}.${fmt}`).catch((e) => toast(e.message, true));
  return (
    <Page>
      <PageHead title={t("Reports")} right={<><button onClick={() => get("csv")}>{t("Download CSV")}</button><button className="btn-strong" onClick={() => get("pdf")}>{t("Download PDF")}</button></>} />
      <div className="tabs" role="tablist">{list?.map((r) => <button key={r.key} role="tab" aria-selected={k === r.key} onClick={() => setK(r.key)}>{t(r.title)}</button>)}</div>
      {!data ? <Skeleton /> : <div className="card">
        <p className="small muted">{t("As of {d}. Synthetic data.", { d: day(data.as_of) })}</p>
        <div className="scroll-x"><table className="plain">
          <thead><tr>{data.head.map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
          <tbody>{data.rows.map((r, i) => <tr key={i}>{r.map((x, j) => <td key={j}>{String(x)}</td>)}</tr>)}</tbody>
        </table></div>
      </div>}
    </Page>
  );
}
