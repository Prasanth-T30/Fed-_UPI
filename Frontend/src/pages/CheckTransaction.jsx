import { useState } from "react";
import { api } from "../services/api";
import { Card, DecisionBadge, ErrorNote, Page, ReasonList } from "../components/ui";

const EMPTY_TRANSACTION = {
  amount_inr: "", amount_to_average_ratio: "", transaction_hour: "", account_age_days: "",
  transactions_last_hour: "", minutes_since_last_transaction: "", failed_login_attempts_24h: "",
  upi_pin_failures_24h: "", sender_txn_24h: "", same_receiver_24h: "", sender_id: "", receiver_id: "",
  is_new_device: 0, is_new_beneficiary: 0, is_collect_request: 0, is_weekend: 0, merchant_category: "p2p",
};

const FIELDS = [
  ["amount_inr", "Amount (₹)"], ["amount_to_average_ratio", "Amount ÷ user's average"],
  ["transaction_hour", "Hour (0–23)"], ["account_age_days", "Account age (days)"],
  ["transactions_last_hour", "Transactions in last hour"], ["minutes_since_last_transaction", "Minutes since last transaction"],
  ["failed_login_attempts_24h", "Failed logins (24h)"], ["upi_pin_failures_24h", "UPI PIN failures (24h)"],
  ["same_receiver_24h", "Earlier payments to same receiver (24h)"], ["sender_txn_24h", "Earlier payments by user (24h)"],
];

const FLAGS = [
  ["is_new_device", "New device"], ["is_new_beneficiary", "New beneficiary"],
  ["is_collect_request", "Collect request"], ["is_weekend", "Weekend"],
];

export default function CheckTransaction() {
  const [form, setForm] = useState(EMPTY_TRANSACTION);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api.score(form));
    } catch (requestError) {
      setError(requestError.message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const tone = result && (result.risk_level === "HIGH" ? "red" : result.risk_level === "MODERATE" ? "amber" : "green");

  return (
    <Page title="Check a transaction" sub="Enter the actual transaction signals to receive a risk decision and explanation.">
      <div className="grid two wide-left">
        <Card title="Transaction details" hint="No sample values are pre-filled">
          <form onSubmit={submit} className="form">
            {FIELDS.map(([key, label]) => (
              <label key={key}>{label}
                <input type="number" step="any" value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} required />
              </label>
            ))}
            <label>Sender ID <small>(optional)</small><input value={form.sender_id} onChange={(event) => setForm({ ...form, sender_id: event.target.value })} /></label>
            <label>Receiver ID <small>(optional)</small><input value={form.receiver_id} onChange={(event) => setForm({ ...form, receiver_id: event.target.value })} /></label>
            <label>Merchant category
              <select value={form.merchant_category} onChange={(event) => setForm({ ...form, merchant_category: event.target.value })}>
                <option value="p2p">P2P</option>
                <option value="merchant">Merchant</option>
                <option value="investment">Investment</option>
              </select>
            </label>
            <div className="flags">
              {FLAGS.map(([key, label]) => (
                <label key={key} className="check"><input type="checkbox" checked={!!form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.checked ? 1 : 0 })} /> {label}</label>
              ))}
            </div>
            <button className="btn" disabled={busy}>{busy ? "Scoring…" : "Score transaction"}</button>
          </form>
          <ErrorNote error={error} />
        </Card>

        <Card title="Decision">
          {!result ? <div className="empty">Fill in the transaction details, then score.</div> : (
            <div className="result">
              <div className={`gauge ${tone}`}><b>{result.risk_score.toFixed(1)}%</b><small>{result.risk_level.toLowerCase()} risk</small></div>
              <DecisionBadge d={result.decision} />
              <div className="sub-scores">
                <span>Federated model fraud score <b>{result.model_score.toFixed(1)}%</b></span>
                <span>Autoencoder anomaly score <b>{result.anomaly_score.toFixed(0)}%</b></span>
              </div>
              <h4>Why this risk level</h4>
              <ReasonList reasons={result.reasons} />
              <small className="muted">Risk percentage is tier-consistent and is not a calibrated probability. Model: {result.model_version}</small>
            </div>
          )}
        </Card>
      </div>
    </Page>
  );
}
