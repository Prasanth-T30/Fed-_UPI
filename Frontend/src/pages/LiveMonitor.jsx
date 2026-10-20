import { useEffect, useRef, useState } from "react";
import { Play, Pause, Trash2, Zap } from "lucide-react";
import { api, inr } from "../services/api";
import { Card, ErrorNote, Page, Stat, TxnTable } from "../components/ui";

export default function LiveMonitor() {
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState("");
  const timer = useRef(null);

  const tick = async (n = 6) => {
    try {
      const r = await api.simulate(n);
      setRows((old) => [...r.results.reverse(), ...old].slice(0, 150));
      setErr("");
    } catch (e) { setErr(e.message); setRunning(false); }
  };
  useEffect(() => {
    api.transactions({ limit: 50 }).then(setRows).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => {
    if (running) timer.current = setInterval(() => tick(4), 2500);
    return () => clearInterval(timer.current);
  }, [running]);

  const withTruth = rows.filter((r) => r.ground_truth !== null && r.ground_truth !== undefined);
  const caught = withTruth.filter((r) => r.ground_truth === 1 && r.decision !== "ALLOW").length;
  const fraudTotal = withTruth.filter((r) => r.ground_truth === 1).length;
  const falseAlarms = withTruth.filter((r) => r.ground_truth === 0 && r.decision !== "ALLOW").length;
  const blocked = rows.filter((r) => r.decision === "BLOCK");

  return (
    <Page
      title="Live monitor"
      sub="Simulated UPI traffic from five banks, scored in real time by the federated model. Click a row to see why."
      actions={<>
        <button className="btn ghost" onClick={() => tick(20)}><Zap size={16} /> Burst of 20</button>
        <button className={`btn ${running ? "red" : ""}`} onClick={() => setRunning(!running)}>
          {running ? <><Pause size={16} /> Pause</> : <><Play size={16} /> Simulate traffic</>}
        </button>
        <button className="btn ghost" onClick={async () => { await api.clear(); setRows([]); }}><Trash2 size={16} /> Clear</button>
      </>}
    >
      <ErrorNote error={err} />
      <div className="grid stats">
        <Stat label="Scored" value={rows.length} />
        <Stat label="Fraud caught" value={`${caught} / ${fraudTotal}`} tone="green" sub="simulation ground truth" />
        <Stat label="False alarms" value={falseAlarms} tone="amber" />
        <Stat label="High-risk value" value={inr(blocked.reduce((a, r) => a + r.amount, 0))} tone="red" />
      </div>
      <Card title="Transaction feed"><TxnTable rows={rows} /></Card>
    </Page>
  );
}
