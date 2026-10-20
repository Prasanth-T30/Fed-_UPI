import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Card, ErrorNote, Page, TxnTable } from "../components/ui";
import ExportMenu from "../components/ExportMenu";

export default function Alerts() {
  const [rows, setRows] = useState([]);
  const [tab, setTab] = useState("open");
  const [err, setErr] = useState("");
  const load = () => api.transactions({ status: tab, limit: 200 }).then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [tab]);
  const act = async (id, status) => { await api.setStatus(id, status); load(); };
  return (
    <Page title="Alert queue" sub="Analysts confirm or dismiss flagged transactions. Confirmed labels are the feedback loop for the next federated retraining round."
      actions={<ExportMenu status={tab} decision="BLOCK,STEP_UP_AUTH" disabled={!rows.length} onError={setErr} label="Download" />}>
      <div className="chips">
        {[["open", "Open"], ["confirmed_fraud", "Confirmed fraud"], ["dismissed", "Dismissed"]].map(([k, l]) => (
          <button key={k} className={`chip ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      <ErrorNote error={err} />
      <Card><TxnTable rows={rows} onStatus={act} /></Card>
    </Page>
  );
}
