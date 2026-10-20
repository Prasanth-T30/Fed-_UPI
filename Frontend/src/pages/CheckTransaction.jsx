import { useState } from "react";
import { api } from "../services/api";
import { Card, DecisionBadge, ErrorNote, Page, ReasonList } from "../components/ui";

const DEFAULTS = {
  amount_inr: 25000, amount_to_average_ratio: 1, transaction_hour: 14, account_age_days: 800,
  transactions_last_hour: 0, minutes_since_last_transaction: 300, failed_login_attempts_24h: 0,
  upi_pin_failures_24h: 0, is_new_device: 0, is_new_beneficiary: 0, is_collect_request: 0,
  is_weekend: 0, merchant_category: "p2p", bank: "Bank A", sender_id: "", receiver_id: "", sender_txn_24h: 0, same_receiver_24h: 0,
};
const PRESETS = {
  "Normal payment": DEFAULTS,
  "Repeat payments (3rd to same receiver)": { ...DEFAULTS, amount_inr: 24500, amount_to_average_ratio: 3, same_receiver_24h: 2, transactions_last_hour: 2, is_new_beneficiary: 0 },
  "Amount ₹85,000 (moderate)": { ...DEFAULTS, amount_inr: 85000, amount_to_average_ratio: 2 },
  "Amount ₹1,20,000 (high)": { ...DEFAULTS, amount_inr: 120000, amount_to_average_ratio: 2, merchant_category: "investment" },
  "Collect-request scam": { ...DEFAULTS, amount_inr: 9500, amount_to_average_ratio: 4.2, is_collect_request: 1, is_new_beneficiary: 1, upi_pin_failures_24h: 1 },
  "SIM-swap takeover": { ...DEFAULTS, amount_inr: 48000, amount_to_average_ratio: 6, transaction_hour: 3, is_new_device: 1, is_new_beneficiary: 1, failed_login_attempts_24h: 4 },
  "Mule burst": { ...DEFAULTS, amount_inr: 30000, amount_to_average_ratio: 5, transactions_last_hour: 7, minutes_since_last_transaction: 1.5, is_new_beneficiary: 1 },
};
const FIELDS = [
  ["amount_inr", "Amount (₹)", "number"], ["amount_to_average_ratio", "Amount ÷ user's average", "number"],
  ["transaction_hour", "Hour (0–23)", "number"], ["account_age_days", "Account age (days)", "number"],
  ["transactions_last_hour", "Txns in last hour", "number"], ["minutes_since_last_transaction", "Minutes since last txn", "number"],
  ["failed_login_attempts_24h", "Failed logins (24h)", "number"], ["upi_pin_failures_24h", "UPI PIN failures (24h)", "number"],
  ["same_receiver_24h", "Earlier payments to same receiver (24h)", "number"], ["sender_txn_24h", "Earlier payments by user (24h)", "number"],
];
const FLAGS = [["is_new_device", "New device"], ["is_new_beneficiary", "New beneficiary"], ["is_collect_request", "Collect request"], ["is_weekend", "Weekend"]];

export default function CheckTransaction() {
  const [f, setF] = useState(DEFAULTS);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { setRes(await api.score(f)); } catch (x) { setErr(x.message); setRes(null); }
    setBusy(false);
  };
  const tone = res && (res.risk_level === "HIGH" ? "red" : res.risk_level === "MODERATE" ? "amber" : "green");
  return (
    <Page title="Check a transaction" sub="Enter UPI transaction signals and get an instant risk decision with explanation.">
      <div className="chips">
        {Object.entries(PRESETS).map(([k, v]) => <button key={k} className="chip" onClick={() => { setF(v); setRes(null); }}>{k}</button>)}
      </div>
      <div className="grid two wide-left">
        <Card title="Transaction details">
          <form onSubmit={submit} className="form">
            {FIELDS.map(([k, label, type]) => (
              <label key={k}>{label}
                <input type={type} step="any" value={f[k]} onChange={(e) => setF({ ...f, [k]: Number(e.target.value) })} required />
              </label>
            ))}
            <label>Sender ID <small>(optional)</small><input value={f.sender_id} onChange={(e) => setF({ ...f, sender_id: e.target.value })} placeholder="e.g. A-U00123" /></label>
            <label>Receiver ID <small>(optional)</small><input value={f.receiver_id} onChange={(e) => setF({ ...f, receiver_id: e.target.value })} placeholder="e.g. R04512" /></label>
            <label>Merchant category
              <select value={f.merchant_category} onChange={(e) => setF({ ...f, merchant_category: e.target.value })}>
                {["p2p", "merchant", "investment"].map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <div className="flags">
              {FLAGS.map(([k, label]) => (
                <label key={k} className="check"><input type="checkbox" checked={!!f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked ? 1 : 0 })} /> {label}</label>
              ))}
            </div>
            <button className="btn" disabled={busy}>{busy ? "Scoring…" : "Score transaction"}</button>
          </form>
          <ErrorNote error={err} />
        </Card>
        <Card title="Decision">
          {!res ? <div className="empty">Pick a preset or fill the form, then score.</div> : (
            <div className="result">
              <div className={`gauge ${tone}`}><b>{res.risk_score.toFixed(1)}%</b><small>{res.risk_level.toLowerCase()} risk</small></div>
              <DecisionBadge d={res.decision} />
              <div className="sub-scores">
                <span>Federated model fraud score <b>{res.model_score.toFixed(1)}%</b></span>
                <span>Autoencoder anomaly score <b>{res.anomaly_score.toFixed(0)}%</b></span>
              </div>
              <h4>Why this risk level</h4>
              <ReasonList reasons={res.reasons} />
              <small className="muted">Risk % is tier-consistent (low 0–39, moderate 40–79, high 80–99) and is not a calibrated probability. Model: {res.model_version}</small>
            </div>
          )}
        </Card>
      </div>
    </Page>
  );
}
