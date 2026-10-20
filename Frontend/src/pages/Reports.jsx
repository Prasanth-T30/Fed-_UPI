import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Card, ErrorNote, Page, Stat, TxnTable } from "../components/ui";
import ExportMenu from "../components/ExportMenu";

const SCOPES = [
  ["BLOCK,STEP_UP_AUTH", "All flagged", "High and moderate risk transactions"],
  ["BLOCK", "High risk only", "Payments above ₹99,999"],
  ["STEP_UP_AUTH", "Moderate risk only", "₹70,000–99,999, repeat payments, or model-flagged"],
  ["ALLOW", "Low risk", "Everything below the thresholds"],
];
const STATUS = [["", "Any review status"], ["open", "Open"], ["confirmed_fraud", "Confirmed fraud"], ["dismissed", "Dismissed"]];

export default function Reports() {
  const [scope, setScope] = useState(SCOPES[0][0]);
  const [status, setStatus] = useState("");
  const [dataset, setDataset] = useState("");
  const [datasets, setDatasets] = useState([]);
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  useEffect(() => { api.datasets().then(setDatasets).catch(() => {}); }, []);
  useEffect(() => {
    // the list endpoint filters one decision at a time; fetch each selected decision
    const q = (d) => api.transactions({ decision: d, ...(status && { status }), limit: 200 });
    Promise.all(scope.split(",").map(q)).then((r) => setRows(r.flat().sort((a, b) => b.id - a.id)
      .filter((t) => !dataset || String(t.dataset_id) === dataset))).catch((e) => setErr(e.message));
  }, [scope, status, dataset]);

  return (
    <Page title="Downloads" sub="Export detected fraud for audits, case files or onward analysis — as Excel, CSV, Word, PDF or JSON."
      actions={<ExportMenu decision={scope} status={status || undefined} datasetId={dataset || undefined} disabled={!rows.length} onError={setErr} label="Download report" />}>
      <ErrorNote error={err} />
      <Card title="What to include">
        <div className="filters">
          <label>Risk decision
            <select value={scope} onChange={(e) => setScope(e.target.value)}>{SCOPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Analyst review
            <select value={status} onChange={(e) => setStatus(e.target.value)}>{STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Source
            <select value={dataset} onChange={(e) => setDataset(e.target.value)}>
              <option value="">All transactions</option>
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
            </select>
          </label>
        </div>
        <p className="muted small mt">{SCOPES.find((s) => s[0] === scope)[2]}. The download contains every matching transaction, not just the preview below.</p>
      </Card>
      <div className="grid stats">
        <Stat label="Matching (preview)" value={rows.length >= 200 ? "200+" : rows.length} />
        <Stat label="High risk" value={rows.filter((r) => r.decision === "BLOCK").length} tone="red" />
        <Stat label="Moderate" value={rows.filter((r) => r.decision === "STEP_UP_AUTH").length} tone="amber" />
      </div>
      <Card title="Preview"><TxnTable rows={rows.slice(0, 50)} compact /></Card>
    </Page>
  );
}
