import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock3, Database,
  Network, RefreshCw, ScanSearch, ShieldAlert, Upload,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, inr, pct } from "../services/api";
import { Card, Page, Stat, TxnTable } from "../components/ui";

const QuickAction = ({ to, icon: Icon, title, text }) => (
  <Link className="quick-action" to={to}>
    <span className="quick-icon"><Icon size={19} /></span>
    <span><b>{title}</b><small>{text}</small></span>
    <ArrowRight size={17} />
  </Link>
);

const Kpi = ({ icon: Icon, label, value, detail, tone = "blue" }) => (
  <article className={`kpi ${tone}`}>
    <div className="kpi-top"><span className="kpi-icon"><Icon size={18} /></span><small>{label}</small></div>
    <strong>{value}</strong>
    <p>{detail}</p>
  </article>
);

const LoadingDashboard = () => (
  <div className="dashboard-loading" aria-label="Loading dashboard">
    <div className="grid stats">
      {[0, 1, 2, 3].map((n) => <div className="skeleton stat-skeleton" key={n} />)}
    </div>
    <div className="grid two">
      <div className="skeleton chart-skeleton" />
      <div className="skeleton chart-skeleton" />
    </div>
  </div>
);

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summary, transactions] = await Promise.all([
        api.overview(), api.transactions({ limit: 8 }),
      ]);
      setOverview(summary);
      setRecent(transactions);
    } catch (e) {
      setError(e.message || "Dashboard data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <Page title="Fraud operations overview" sub="Loading the latest risk and alert activity…">
        <LoadingDashboard />
      </Page>
    );
  }

  if (!overview) {
    return (
      <Page title="Fraud operations overview" sub="Monitor suspicious UPI transactions from one place.">
        <Card className="dashboard-error">
          <AlertTriangle size={28} />
          <div><h3>Dashboard data is unavailable</h3><p>{error}</p></div>
          <button className="btn" onClick={load}><RefreshCw size={15} /> Retry</button>
        </Card>
        <Card title="Continue working">
          <div className="quick-grid">
            <QuickAction to="/upload" icon={Upload} title="Upload a dataset" text="Score transactions for possible fraud" />
            <QuickAction to="/check" icon={ScanSearch} title="Check a transaction" text="Run an individual risk assessment" />
            <QuickAction to="/monitor" icon={Activity} title="Live monitor" text="Review the transaction stream" />
          </div>
        </Card>
      </Page>
    );
  }

  const o = overview;
  const model = o.model;
  const metrics = model?.metrics;
  const totalFlagged = o.blocked + o.step_up;
  const flaggedRate = o.total ? totalFlagged / o.total : 0;
  const labelledFraud = o.label_accuracy.caught + o.label_accuracy.missed;
  const captureRate = labelledFraud ? o.label_accuracy.caught / labelledFraud : 0;
  const riskMix = [
    { name: "Low", value: o.allowed, color: "var(--green)" },
    { name: "Moderate", value: o.step_up, color: "var(--amber)" },
    { name: "High", value: o.blocked, color: "var(--red)" },
  ];

  return (
    <Page
      title="Fraud operations overview"
      sub="Monitor risk, review alerts and understand how the federated fraud model is performing."
      actions={<button className="btn ghost" onClick={load}><RefreshCw size={15} /> Refresh</button>}
    >
      <section className="dashboard-hero premium">
        <div className="hero-grid" />
        <div className="hero-copy">
          <span className="eyebrow"><i /> Federated protection live</span>
          <h2>{o.open_alerts ? `${o.open_alerts.toLocaleString()} cases require attention` : "Your risk queue is clear"}</h2>
          <p>The shared model has screened <b>{o.total.toLocaleString()}</b> payments while transaction data remains inside each institution.</p>
          <div className="hero-actions">
            <Link className="btn light" to={o.open_alerts ? "/alerts" : "/monitor"}>
              {o.open_alerts ? "Review priority cases" : "Open live monitor"} <ArrowRight size={16} />
            </Link>
            <Link className="hero-link" to="/check">Check a transaction</Link>
          </div>
        </div>
        <div className="hero-status">
          <div className="status-ring"><span>{pct(1 - flaggedRate, 1)}</span><small>cleared</small></div>
          <div><small>Network status</small><b><i /> 5 banks connected</b><span>{model ? `${model.algorithm.toUpperCase()} · model ready` : "Awaiting trained model"}</span></div>
        </div>
      </section>

      <div className="dashboard-kpis">
        <Kpi icon={Activity} label="Transactions screened" value={o.total.toLocaleString()} detail="Uploads and live checks" />
        <Kpi icon={ShieldAlert} label="High risk blocked" value={o.blocked.toLocaleString()} detail={`${inr(o.blocked_amount)} protected`} tone="red" />
        <Kpi icon={Clock3} label="Step-up checks" value={o.step_up.toLocaleString()} detail="Moderate-risk payments" tone="amber" />
        <Kpi icon={CheckCircle2} label="Confirmed cases" value={o.confirmed_fraud.toLocaleString()} detail={`${o.open_alerts.toLocaleString()} still open`} tone="green" />
      </div>

      <div className="grid two dashboard-charts">
        <Card title="Risk signal" hint="Latest 60 scored transactions" className="chart-card">
          {o.recent.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={o.recent.map((row, index) => ({ index: index + 1, score: row.risk_score }))}>
                <defs><linearGradient id="risk-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity={0.45} /><stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} /></linearGradient></defs>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="index" hide />
                <YAxis domain={[0, 100]} stroke="var(--muted)" width={34} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 10, color: "var(--chart-text)" }} labelStyle={{ color: "var(--chart-text)" }} itemStyle={{ color: "var(--chart-text)" }} />
                <Area type="monotone" dataKey="score" name="Risk score" stroke="var(--accent)" fill="url(#risk-fill)" strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div className="chart-empty"><Activity size={25} /><b>No activity yet</b><span>Upload data or start the live monitor to populate this chart.</span></div>}
        </Card>

        <Card title="Decision mix" hint={`${totalFlagged.toLocaleString()} payments need friction`} className="chart-card">
          {o.total ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={riskMix} margin={{ left: 4, right: 4 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--muted)" tickLine={false} axisLine={false} />
                <YAxis stroke="var(--muted)" width={40} allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 10, color: "var(--chart-text)" }} labelStyle={{ color: "var(--chart-text)" }} itemStyle={{ color: "var(--chart-text)" }} />
                <Bar dataKey="value" name="Transactions" radius={[7, 7, 0, 0]}>{riskMix.map((item) => <Cell key={item.name} fill={item.color} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="chart-empty"><Database size={25} /><b>No scored data</b><span>Your low, moderate and high-risk distribution will appear here.</span></div>}
        </Card>
      </div>

      <div className="grid two wide-left operations-row">
        <Card title="Analyst launchpad" hint="Continue an investigation">
          <div className="quick-grid">
            <QuickAction to="/upload" icon={Upload} title="Upload dataset" text="Score a new transaction file" />
            <QuickAction to="/check" icon={ScanSearch} title="Check transaction" text="Assess one payment instantly" />
            <QuickAction to="/alerts" icon={AlertTriangle} title="Review alerts" text="Confirm or dismiss cases" />
          </div>
        </Card>

        <Card title="System posture" hint="Current operational indicators">
          <div className="health-list">
            <div><span><CheckCircle2 size={17} /> Model status</span><b className={model ? "good-text" : "warn-text"}>{model ? "Ready" : "Unavailable"}</b></div>
            <div><span><Network size={17} /> Federation</span><b>5 institutions</b></div>
            <div><span>Labelled fraud capture</span><b>{labelledFraud ? pct(captureRate) : "No labelled data"}</b></div>
            <div><span>False alarms observed</span><b>{o.label_accuracy.false_alarms.toLocaleString()}</b></div>
            <div><span>Model version</span><b className="mono">{model?.version || "—"}</b></div>
          </div>
        </Card>
      </div>

      {metrics && (
        <Card title="Production model quality" hint={`${model.algorithm.toUpperCase()} · ${model.rounds} federated rounds · ${model.banks.length} participating banks`}>
          <div className="grid stats embedded-stats">
            <Stat label="Precision" value={pct(metrics.precision)} />
            <Stat label="Recall" value={pct(metrics.recall)} />
            <Stat label="F1 score" value={pct(metrics.f1)} />
            <Stat label="ROC-AUC" value={metrics.roc_auc.toFixed(3)} sub={`PR-AUC ${metrics.pr_auc.toFixed(3)}`} />
          </div>
        </Card>
      )}

      <Card title="Latest decisions" hint="Most recently scored transactions" action={<Link className="text-link" to="/monitor">View all <ArrowRight size={14} /></Link>}>
        <TxnTable rows={recent} compact />
      </Card>
    </Page>
  );
}
