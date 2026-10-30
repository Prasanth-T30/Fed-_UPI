import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, AreaChart, Area } from "recharts";
import { api, pct } from "../services/api";
import { Badge, Card, ErrorNote, Page, Stat } from "../components/ui";

const tip = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--line)", color: "var(--chart-text)" },
  labelStyle: { color: "var(--chart-text)" },
  itemStyle: { color: "var(--chart-text)" },
};

export default function ModelInsights() {
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.report().then(setR).catch((e) => setErr(e.message)); }, []);
  if (!r) return <Page title="Model insights"><ErrorNote error={err} /></Page>;
  const f = r.final, m = f.metrics, ex = Object.entries(r.experiments);
  const hist = f.score_hist.bins.map((b, i) => ({ bin: `${Math.round(b * 100)}`, legit: f.score_hist.legit[i], fraud: f.score_hist.fraud[i] }));
  const fedHist = r.experiments.federated.history, proxHist = r.experiments.fedprox?.history;
  const conv = fedHist.map((h, i) => ({ round: h.round, FedAvg: h.pr_auc, FedProx: proxHist?.[i]?.pr_auc }));
  return (
    <Page title="Model insights" sub={`Evaluation on a held-out test split (${r.dataset.test.toLocaleString()} transactions, ${pct(r.dataset.fraud_rate)} fraud). Threshold chosen on validation data only.`}>
      <div className="grid stats">
        <Stat label="Precision" value={pct(m.precision)} sub={`${m.fp} false alarms`} />
        <Stat label="Recall" value={pct(m.recall)} sub={`${m.fn} frauds missed`} />
        <Stat label="F1" value={pct(m.f1)} /><Stat label="PR-AUC" value={m.pr_auc.toFixed(3)} sub={`ROC-AUC ${m.roc_auc.toFixed(3)}`} />
      </div>

      <Card title="Federated vs centralized vs local-only" hint="same data, same test set">
        <div className="table-wrap"><table>
          <thead><tr><th>Approach</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th><th className="num">PR-AUC</th><th className="num">ROC-AUC</th><th className="num">Privacy</th></tr></thead>
          <tbody>{ex.map(([k, e]) => (
            <tr key={k} className={k === "federated" ? "hl" : ""}>
              <td>{e.label} {k === "federated" && <Badge tone="blue">main</Badge>}</td>
              <td className="num">{pct(e.metrics.precision)}</td><td className="num">{pct(e.metrics.recall)}</td>
              <td className="num">{pct(e.metrics.f1)}</td><td className="num">{e.metrics.pr_auc.toFixed(3)}</td><td className="num">{e.metrics.roc_auc.toFixed(3)}</td>
              <td className="num">{e.epsilon ? `ε ${e.epsilon}` : e.secagg ? "SecAgg" : "—"}</td>
            </tr>))}
          </tbody>
        </table></div>
        <p className="muted small">The ensemble row is the production scorer (federated MLP + federated autoencoder, weight {f.ensemble_weight}). Differences of ~1 point are within seed noise; the claim is that federated training approaches centralized quality without pooling data and beats banks working alone.</p>
      </Card>

      <div className="grid two">
        <Card title="Precision–recall curve">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={f.pr_curve}>
              <CartesianGrid stroke="var(--line)" /><XAxis dataKey="recall" type="number" domain={[0, 1]} stroke="var(--muted)" /><YAxis domain={[0, 1]} stroke="var(--muted)" width={34} />
              <Tooltip {...tip} /><Line dataKey="precision" stroke="var(--accent)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Score distribution" hint="fraud vs legitimate (log counts)">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hist}><CartesianGrid stroke="var(--line)" vertical={false} /><XAxis dataKey="bin" stroke="var(--muted)" /><YAxis scale="sqrt" stroke="var(--muted)" width={40} />
              <Tooltip {...tip} /><Legend /><Bar dataKey="legit" fill="var(--green)" /><Bar dataKey="fraud" fill="var(--red)" /></BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="What drives the fraud score" hint="mean |gradient × input| on true fraud">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={f.importance} layout="vertical" margin={{ left: 120 }}>
              <XAxis type="number" hide /><YAxis type="category" dataKey="feature" stroke="var(--muted)" width={120} tick={{ fontSize: 12 }} />
              <Tooltip {...tip} formatter={(v) => pct(v)} /><Bar dataKey="importance" fill="var(--accent)" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Recall by fraud typology">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={f.by_scenario}><CartesianGrid stroke="var(--line)" vertical={false} /><XAxis dataKey="scenario" stroke="var(--muted)" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 1]} stroke="var(--muted)" width={34} /><Tooltip {...tip} formatter={(v) => pct(v)} /><Bar dataKey="recall" fill="var(--amber)" radius={[6, 6, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="FedAvg vs FedProx convergence" hint="validation PR-AUC per round">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={conv}><CartesianGrid stroke="var(--line)" /><XAxis dataKey="round" stroke="var(--muted)" /><YAxis domain={[0, 1]} stroke="var(--muted)" width={34} />
              <Tooltip {...tip} /><Legend /><Line dataKey="FedAvg" stroke="var(--accent)" dot={false} strokeWidth={2} /><Line dataKey="FedProx" stroke="var(--amber)" dot={false} strokeWidth={2} /></LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Per-bank test performance" hint="non-IID banks: different fraud rates & typologies">
          <div className="table-wrap"><table>
            <thead><tr><th>Bank</th><th className="num">Fraud</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th></tr></thead>
            <tbody>{f.per_bank.map((b) => <tr key={b.bank}><td>{b.bank}</td><td className="num">{b.fraud}/{b.rows}</td><td className="num">{pct(b.precision)}</td><td className="num">{pct(b.recall)}</td><td className="num">{pct(b.f1)}</td></tr>)}</tbody>
          </table></div>
        </Card>
      </div>
      {f.policy && (
        <Card title="Risk policy results" hint="rules + federated model on the held-out test set">
          <div className="grid stats">
            {f.policy.tiers.map((t) => (
              <Stat key={t.tier} label={`${t.tier === "HIGH" ? "High" : t.tier === "MODERATE" ? "Moderate" : "Low"} risk`}
                value={t.transactions.toLocaleString()} tone={t.tier === "HIGH" ? "red" : t.tier === "MODERATE" ? "amber" : "green"}
                sub={`${t.fraud} real fraud · avg risk ${t.mean_risk_pct ?? "–"}%`} />
            ))}
            <Stat label="Flagged precision / recall" value={`${pct(f.policy.flagged_precision, 0)} / ${pct(f.policy.flagged_recall, 0)}`} sub="moderate + high tiers" />
          </div>
          <div className="table-wrap mt"><table>
            <thead><tr><th>Rule</th><th className="num">Transactions</th><th className="num">Real fraud</th></tr></thead>
            <tbody>{Object.entries(f.policy.triggers).map(([k, v]) => (
              <tr key={k}><td>{{ model: "Federated model flags it", repeat: "Repeated payments to same receiver (24h)", burst: "Burst of payments by user (1h)", moderate_amount: "₹70,000–99,999", high_amount: "Above ₹99,999" }[k]}</td>
                <td className="num">{v.flagged}</td><td className="num">{v.fraud}</td></tr>))}
            </tbody>
          </table></div>
          <p className="small muted mt">Policy: high risk is reserved for payments above ₹99,999, so the model alone can only raise a smaller payment to moderate. {f.policy.high_amount_legit} legitimate high-value payments in this test set are high risk because of the amount rule alone.</p>
        </Card>
      )}
      <Card title="Privacy accounting">
        <div className="grid stats">
          <Stat label="Raw rows to server" value={r.privacy.raw_rows_sent_to_server} tone="green" />
          <Stat label="Params / bank / round" value={r.privacy.params_per_update.toLocaleString()} />
          <Stat label="Secure aggregation" value={r.privacy.secure_aggregation ? "On" : "Off"} sub={r.privacy.secagg_stats ? `sum error ${r.privacy.secagg_stats.secagg_max_error.toExponential(1)}` : ""} tone={r.privacy.secure_aggregation ? "green" : ""} />
          <Stat label="Production DP budget" value={r.privacy.dp.enabled ? `ε ${r.privacy.dp.epsilon}` : "none"} sub={r.privacy.dp.enabled ? `δ ${r.privacy.dp.delta}` : "see DP rows above"} />
        </div>
        <p className="small mt">{r.privacy.note} Strong client-level DP is expensive with only five banks: the table above shows the measured accuracy/ε trade-off.</p>
      </Card>
    </Page>
  );
}
