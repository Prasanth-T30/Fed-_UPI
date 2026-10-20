import { useEffect, useRef, useState } from "react";
import { Database, Download, RefreshCw, Trash2, Upload } from "lucide-react";
import { api, bytes } from "../services/api";
import { Card, Empty, ErrorNote, Page, Stat, TxnTable } from "../components/ui";
import ExportMenu from "../components/ExportMenu";

const COLS = "amount_inr, amount_to_average_ratio, transaction_hour, account_age_days, transactions_last_hour, minutes_since_last_transaction, failed_login_attempts_24h, upi_pin_failures_24h, is_new_device, is_new_beneficiary, is_collect_request, is_weekend, merchant_category";

export default function Datasets() {
  const [list, setList] = useState([]);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef();
  const load = () => api.datasets().then(setList).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const send = async (file) => {
    if (!file) return;
    setBusy("upload"); setErr("");
    try { setRes(await api.upload(file)); load(); } catch (e) { setErr(e.message); }
    setBusy("");
    if (input.current) input.current.value = "";
  };
  const rescore = async (id) => {
    setBusy(`r${id}`); setErr("");
    try { setRes(await api.rescore(id)); load(); } catch (e) { setErr(e.message); }
    setBusy("");
  };
  const remove = async (id) => {
    if (!confirm("Delete this dataset and its scored results?")) return;
    try { await api.deleteDataset(id); if (res?.dataset?.id === id) setRes(null); load(); } catch (e) { setErr(e.message); }
  };

  return (
    <Page title="Upload & datasets" sub="Upload Excel, CSV, JSON or Word-table files. They are stored in your library and scored by the federated model straight away.">
      <Card>
        <div className={`drop ${drag ? "over" : ""}`} onClick={() => input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}>
          <Upload size={26} />
          <b>{busy === "upload" ? "Uploading and scoring…" : "Drop a file here, or click to browse"}</b>
          <span>.xlsx · .csv · .json · .docx (table) · .tsv — up to 10 MB / 20,000 rows</span>
          <small>Required columns: {COLS}. Recommended: sender_id, receiver_id, timestamp (to detect repeated payments to the same receiver). Optional: transaction_id, bank, is_fraud. merchant_category must be p2p, merchant or investment.</small>
          <input ref={input} type="file" hidden accept=".csv,.xlsx,.xlsm,.json,.docx,.txt,.tsv" onChange={(e) => send(e.target.files[0])} />
        </div>
        <ErrorNote error={err} />
      </Card>

      {res && (
        <>
          <div className="grid stats">
            <Stat label="Rows scored" value={res.rows.toLocaleString()} sub={res.dataset.filename} />
            <Stat label="High risk" value={res.counts.BLOCK || 0} tone="red" />
            <Stat label="Moderate risk" value={res.counts.STEP_UP_AUTH || 0} tone="amber" />
            <Stat label="Low risk" value={res.counts.ALLOW || 0} tone="green" />
          </div>
          <Card title="Flagged transactions in this file" hint={res.rows > 300 ? "showing first 300 rows" : ""}
            className="with-action" action={<ExportMenu datasetId={res.dataset.id} disabled={!res.flagged} onError={setErr} label={res.flagged ? `Download ${res.flagged} flagged` : "Nothing flagged"} />}>
            <TxnTable rows={res.results} />
          </Card>
        </>
      )}

      <Card title="Dataset library" hint={`${list.length} stored`}>
        {!list.length ? <Empty><Database size={22} /><br />No datasets yet. Upload one above.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>File</th><th className="num">Rows</th><th className="num">Flagged</th><th>Size</th><th>Uploaded</th><th /></tr></thead>
            <tbody>{list.map((d) => (
              <tr key={d.id}>
                <td><b>{d.filename}</b></td><td className="num">{d.rows.toLocaleString()}</td>
                <td className="num">{d.flagged}</td><td>{bytes(d.size_bytes)}</td>
                <td>{new Date(d.created_at).toLocaleString()}</td>
                <td><div className="btn-row end">
                  <ExportMenu datasetId={d.id} disabled={!d.flagged} label="Fraud" onError={setErr} />
                  <button className="icon-btn" title="Download original file" onClick={() => api.downloadOriginal(d.id).catch((e) => setErr(e.message))}><Download size={16} /></button>
                  <button className="icon-btn" title="Re-score with current model" disabled={busy === `r${d.id}`} onClick={() => rescore(d.id)}><RefreshCw size={16} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => remove(d.id)}><Trash2 size={16} /></button>
                </div></td>
              </tr>))}
            </tbody>
          </table></div>
        )}
      </Card>
    </Page>
  );
}
