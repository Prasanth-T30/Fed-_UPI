import { useCallback, useEffect, useRef, useState } from "react";
import { Pause, Play, RefreshCw, Trash2 } from "lucide-react";
import { api, inr } from "../services/api";
import { Card, ErrorNote, Page, Stat, TxnTable } from "../components/ui";

export default function LiveMonitor() {
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(true);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await api.transactions({ limit: 150 }));
      setErr("");
    } catch (error) {
      setErr(error.message);
      setRunning(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    clearInterval(timer.current);
    if (running) timer.current = setInterval(refresh, 3000);
    return () => clearInterval(timer.current);
  }, [refresh, running]);

  const flagged = rows.filter((row) => row.decision !== "ALLOW");
  const blocked = rows.filter((row) => row.decision === "BLOCK");
  const confirmed = rows.filter((row) => row.status === "confirmed_fraud");

  return (
    <Page
      title="Live monitor"
      sub="Recent transactions from uploads and API checks. No generated or predefined transactions are inserted."
      actions={<>
        <button className="btn ghost" onClick={refresh} disabled={loading}><RefreshCw size={16} /> Refresh</button>
        <button className="btn" onClick={() => setRunning((value) => !value)}>
          {running ? <><Pause size={16} /> Pause updates</> : <><Play size={16} /> Resume updates</>}
        </button>
        <button className="btn ghost" onClick={async () => { await api.clear(); setRows([]); }}><Trash2 size={16} /> Clear</button>
      </>}
    >
      <ErrorNote error={err} />
      <div className="grid stats">
        <Stat label="Recent transactions" value={rows.length} sub={running ? "refreshes every 3 seconds" : "updates paused"} />
        <Stat label="Flagged" value={flagged.length} tone="amber" sub="moderate and high risk" />
        <Stat label="Confirmed fraud" value={confirmed.length} tone="red" sub="analyst-confirmed cases" />
        <Stat label="High-risk value" value={inr(blocked.reduce((sum, row) => sum + row.amount, 0))} tone="red" />
      </div>
      <Card title="Transaction feed" hint={loading ? "Loading…" : "Uploaded and API-scored transactions only"}>
        <TxnTable rows={rows} />
      </Card>
    </Page>
  );
}
