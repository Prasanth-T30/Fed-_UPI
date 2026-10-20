import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { api, inr, pct } from "../services/api";
import { Card, ErrorNote, Page, Stat, TxnTable } from "../components/ui";

export default function Dashboard() {
  const [o, setO] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const load = () => {
    api.overview().then(setO).catch((e) => setErr(e.message));
    api.transactions({ limit: 8 }).then(setRecent).catch(() => {});
  };
  useEffect(load, []);
  if (!o) return <Page title="Dashboard"><ErrorNote error={err} /></Page>;
  const m = o.model?.metrics;
  const mix = [
    { name: "Low risk", v: o.allowed, c: "var(--green)" },
    { name: "Moderate", v: o.step_up, c: "var(--amber)" },
    { name: "High risk", v: o.blocked, c: "var(--red)" },
  ];
  return (
    <Page
      title="Fraud operations overview"
      sub="Privacy-preserving UPI fraud detection: five banks train one shared model without sharing a single transaction."
      actions={<Link className="btn" to="/monitor">Start live monitor →</Link>}
    >
      <div className="grid stats">
        <Stat label="Transactions scored" value={o.total.toLocaleString()} />
        <Stat label="High risk (above ₹99,999)" value={o.blocked} tone="red" sub={inr(o.blocked_amount) + " held"} />
        <Stat label="Moderate risk" value={o.step_up} tone="amber" sub="step-up authentication" />
        <Stat label="Open alerts" value={o.open_alerts} sub={`${o.confirmed_fraud} confirmed by analysts`} />
      </div>
      <div className="grid two">
        <Card title="Risk score stream" hint="last 60 scored transactions">
          {o.recent.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={o.recent.map((r, i) => ({ i, score: r.risk_score }))}>
                <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity={0.5} /><stop offset="100%" stopColor="var(--accent)" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="i" hide /><YAxis domain={[0, 100]} stroke="var(--muted)" width={30} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} />
                <Area type="monotone" dataKey="score" stroke="var(--accent)" fill="url(#g)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div className="empty">Nothing scored yet — open <Link to="/monitor">Live Monitor</Link> and press “Simulate traffic”.</div>}
        </Card>
        <Card title="Risk tier mix">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={mix}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--muted)" /><YAxis stroke="var(--muted)" width={30} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)" }} />
              <Bar dataKey="v" radius={[6, 6, 0, 0]}>{mix.map((d) => <Cell key={d.name} fill={d.c} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      {m && (
        <Card title="Production model (held-out test set)" hint={`${o.model.dataset === "paysim" ? "PaySim (real public data)" : "Synthetic UPI"} · ${o.model.algorithm.toUpperCase()} · ${o.model.rounds} rounds · ${o.model.banks.length} banks · trained ${o.model.trained_at}`}>
          <div className="grid stats">
            <Stat label="Precision" value={pct(m.precision)} /><Stat label="Recall" value={pct(m.recall)} />
            <Stat label="F1" value={pct(m.f1)} /><Stat label="PR-AUC" value={m.pr_auc.toFixed(3)} sub={`ROC-AUC ${m.roc_auc.toFixed(3)}`} />
          </div>
          <div className="banks">
            {o.model.banks.map((b) => (
              <div key={b.bank}><b>{b.bank}</b><span>{b.rows.toLocaleString()} rows</span><small>{pct(b.fraud_rate)} fraud</small></div>
            ))}
          </div>
        </Card>
      )}
      <Card title="Latest decisions"><TxnTable rows={recent} compact /></Card>
    </Page>
  );
}
