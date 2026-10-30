import { useState } from "react";
import { api, inr } from "../services/api";
import { findLiveTransaction } from "../services/liveTransactions";
import { useAuth } from "../context";
import { Card, DecisionBadge, ErrorNote, Page, ReasonList } from "../components/ui";

export default function CheckTransaction() {
  const { user } = useAuth();
  const [transactionId, setTransactionId] = useState("");
  const [referenceId, setReferenceId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);
    if (!transactionId.trim() && !referenceId.trim()) {
      setError("Enter a transaction ID or a reference ID.");
      return;
    }
    if (transactionId.trim() && referenceId.trim()) {
      setError("Enter only one identifier at a time.");
      return;
    }
    setBusy(true);
    try {
      const identifiers = {
        transactionId: transactionId.trim(),
        referenceId: referenceId.trim(),
      };
      const liveResult = findLiveTransaction(user.id, identifiers);
      setResult(liveResult || await api.lookupTransaction(identifiers));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const tone = result && (result.risk_level === "HIGH" ? "red" : result.risk_level === "MODERATE" ? "amber" : "green");

  return (
    <Page title="Check a transaction" sub="Search your uploaded datasets and transaction history by transaction ID or reference ID.">
      <div className="grid two wide-left">
        <Card title="Find transaction" hint="Enter either one of the identifiers">
          <form onSubmit={submit} className="form lookup-form">
            <label>Transaction ID
              <input value={transactionId} disabled={!!referenceId || busy}
                onChange={(event) => setTransactionId(event.target.value)} placeholder="e.g. UPI0002636 or 125" />
            </label>
            <div className="lookup-or">or</div>
            <label>Reference ID
              <input value={referenceId} disabled={!!transactionId || busy}
                onChange={(event) => setReferenceId(event.target.value)} placeholder="e.g. UPI0000125" />
            </label>
            <button className="btn" disabled={busy || (!transactionId && !referenceId)}>
              {busy ? "Searching…" : "Search transaction"}
            </button>
          </form>
          <ErrorNote error={error} />
        </Card>

        <Card title="Decision">
          {!result ? <div className="empty">Enter an ID to view the stored transaction decision.</div> : (
            <div className="result">
              <div className={`gauge ${tone}`}><b>{Number(result.risk_score).toFixed(1)}%</b><small>{result.risk_level.toLowerCase()} risk</small></div>
              <DecisionBadge d={result.decision} />
              <div className="transaction-summary">
                <span>Transaction ID <b>{result.id}</b></span>
                <span>Reference ID <b>{result.reference_id || (result.source === "live_simulation" ? result.txn_ref : "—")}</b></span>
                <span>Amount <b>{inr(result.amount)}</b></span>
                <span>Category <b>{result.category || "—"}</b></span>
                <span>Source <b>{result.source === "upload" ? "Uploaded dataset" : result.source}</b></span>
              </div>
              <h4>Why this risk level</h4>
              <ReasonList reasons={result.reasons} />
              <small className="muted">Model: {result.model_version || "—"}</small>
            </div>
          )}
        </Card>
      </div>
    </Page>
  );
}
