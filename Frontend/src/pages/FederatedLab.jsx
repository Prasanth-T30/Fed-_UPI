import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Play } from "lucide-react";
import { api, pct } from "../services/api";
import { Card, ErrorNote, Page, Stat } from "../components/ui";

const DEF = { model: "mlp", algorithm: "fedavg", rounds: 12, local_epochs: 2, lr: 0.01, batch_size: 256, mu: 0.01, dp_clip: 0, dp_noise: 0, secure_agg: false, dp_delta: 1e-5, full_comparison: false, promote: false };

export default function FederatedLab() {
  const [cfg, setCfg] = useState(DEF);
  const [st, setSt] = useState(null);
  const [err, setErr] = useState("");
  const poll = useRef();
  const [eps, setEps] = useState(null);
  useEffect(() => {
    if (!cfg.dp_clip || !cfg.dp_noise) return setEps(null);
    const t = setTimeout(() => {
      api.epsilon(cfg.dp_noise, cfg.rounds, cfg.dp_delta).then((j) => setEps(j.epsilon)).catch(() => setEps(null));
    }, 250);
    return () => clearTimeout(t);
  }, [cfg.dp_clip, cfg.dp_noise, cfg.rounds, cfg.dp_delta]);

  const refresh = () => api.fedStatus().then(setSt).catch((e) => setErr(e.message));
  useEffect(() => { refresh(); return () => clearInterval(poll.current); }, []);
  useEffect(() => {
    clearInterval(poll.current);
    if (st?.status === "running") poll.current = setInterval(refresh, 1000);
  }, [st?.status]);

  const start = async () => {
    setErr("");
    try { await api.fedTrain(cfg); refresh(); } catch (e) { setErr(e.message); }
  };
  const set = (k) => (e) => setCfg({ ...cfg, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.type === "number" ? Number(e.target.value) : e.target.value });
  const usePaperPreset = () => setCfg({
    ...cfg,
    model: "paper_mlp",
    algorithm: "fedavg",
    rounds: 20,
    local_epochs: 2,
    lr: 0.02,
    batch_size: 512,
    full_comparison: true,
  });
  const running = st?.status === "running";
  const rounds = (st?.rounds || []).filter((r) => r.stage?.endsWith("/clf") || r.stage?.endsWith("/paper_mlp"));
  const last = rounds[rounds.length - 1];

  return (
    <Page title="Federated lab" sub="Train the shared model across the five banks from the browser. Each round every bank trains locally and only weights are averaged.">
      <div className="grid two wide-left">
        <Card title="Training configuration">
          <div className="form">
            <button type="button" className="btn ghost" onClick={usePaperPreset} disabled={running}>Use research-paper preset</button>
            <label>Model
              <select value={cfg.model} onChange={set("model")}>
                <option value="mlp">Enhanced MLP (64-32)</option>
                <option value="paper_mlp">Paper MLP (single 16-unit hidden layer)</option>
              </select>
            </label>
            <label>Algorithm
              <select value={cfg.algorithm} onChange={set("algorithm")}>
                <option value="fedavg">FedAvg (McMahan 2017)</option>
                <option value="fedprox">FedProx (Li 2020) — robust to non-IID banks</option>
              </select>
            </label>
            <label>Communication rounds<input type="number" min="1" max="40" value={cfg.rounds} onChange={set("rounds")} /></label>
            <label>Local epochs per round<input type="number" min="1" max="5" value={cfg.local_epochs} onChange={set("local_epochs")} /></label>
            <label>Learning rate<input type="number" step="0.005" value={cfg.lr} onChange={set("lr")} /></label>
            <label>Mini-batch size<input type="number" min="32" max="2048" step="32" value={cfg.batch_size} onChange={set("batch_size")} /></label>
            {cfg.algorithm === "fedprox" && <label>FedProx μ<input type="number" step="0.01" value={cfg.mu} onChange={set("mu")} /></label>}
            <label>DP clip norm (0 = off)<input type="number" step="0.1" value={cfg.dp_clip} onChange={set("dp_clip")} /></label>
            <label>DP noise multiplier<input type="number" step="0.1" value={cfg.dp_noise} onChange={set("dp_noise")} disabled={!cfg.dp_clip} /></label>
            <label className="check"><input type="checkbox" checked={cfg.secure_agg} onChange={set("secure_agg")} /> Secure aggregation (pairwise masking — server sees only the sum)</label>
            <label>DP δ<input type="number" step="any" value={cfg.dp_delta} onChange={set("dp_delta")} disabled={!cfg.dp_clip} /></label>
            <div className="eps-box">
              <small>Privacy budget (client-level, RDP accountant)</small>
              <b>{!cfg.dp_clip || !cfg.dp_noise ? "No DP — ε = ∞" : eps == null ? "…" : `ε ≈ ${eps} at δ = ${cfg.dp_delta}`}</b>
              {eps > 10 && <span>ε above ~10 gives little formal protection; with only 5 banks, strong DP costs a lot of accuracy.</span>}
            </div>
            <label className="check"><input type="checkbox" checked={cfg.full_comparison} onChange={set("full_comparison")} /> Run all baselines (slower, ~1–2 min)</label>
            <label className="check"><input type="checkbox" checked={cfg.promote} onChange={set("promote")} /> Replace the production model with this run</label>
            <button className="btn" onClick={start} disabled={running}><Play size={16} /> {running ? "Training…" : "Start federated training"}</button>
          </div>
          <ErrorNote error={err || st?.error} />
        </Card>
        <Card title="Convergence" hint={running ? `${st.stage}` : st?.status}>
          {rounds.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={rounds}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="round" stroke="var(--muted)" /><YAxis domain={[0, 1]} stroke="var(--muted)" width={34} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} />
                <Legend />
                <Line dataKey="f1" name="F1 (val)" stroke="var(--accent)" strokeWidth={2} dot={false} />
                <Line dataKey="pr_auc" name="PR-AUC (val)" stroke="var(--green)" strokeWidth={2} dot={false} />
                <Line dataKey="recall" name="Recall" stroke="var(--amber)" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <div className="empty">Start a run to watch the global model improve round by round.</div>}
          {last && (
            <div className="grid stats mt">
              <Stat label="Round" value={`${last.round}`} /><Stat label="F1" value={pct(last.f1)} />
              <Stat label="Recall" value={pct(last.recall)} />
              {last.epsilon != null ? <Stat label="ε spent" value={last.epsilon} sub={`δ = ${cfg.dp_delta}`} /> : <Stat label="Upload / round" value={`${last.upload_kb} KB`} sub="weights only" />}
            </div>
          )}
        </Card>
      </div>
      {st?.status === "done" && st.result && (
        <Card title="Run result" hint={`${st.result.duration_sec}s · ${st.promoted ? "promoted to production" : "not promoted"}`}>
          <div className="table-wrap"><table>
            <thead><tr><th>Model</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th><th className="num">PR-AUC</th></tr></thead>
            <tbody>{Object.values(st.result.experiments).map((e) => (
              <tr key={e.label}><td>{e.label}</td><td className="num">{pct(e.metrics.precision)}</td><td className="num">{pct(e.metrics.recall)}</td><td className="num">{pct(e.metrics.f1)}</td><td className="num">{e.metrics.pr_auc.toFixed(3)}</td></tr>
            ))}</tbody>
          </table></div>
        </Card>
      )}
    </Page>
  );
}
