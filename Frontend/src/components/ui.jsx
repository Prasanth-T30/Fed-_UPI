import { Fragment, useState } from "react";
import { inr } from "../services/api";

export const Page = ({ title, sub, actions, children }) => (
  <div className="page">
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      <div className="actions">{actions}</div>
    </header>
    {children}
  </div>
);

export const Card = ({ title, hint, action, children, className = "" }) => (
  <section className={`card ${className}`}>
    {title && (
      <div className="card-head">
        <h3>{title}</h3>
        {hint && <small>{hint}</small>}
        {action && <div className="card-action">{action}</div>}
      </div>
    )}
    {children}
  </section>
);

export const Stat = ({ label, value, sub, tone }) => (
  <div className={`stat ${tone || ""}`}>
    <small>{label}</small>
    <b>{value}</b>
    {sub && <span>{sub}</span>}
  </div>
);

export const Badge = ({ tone = "gray", children }) => <span className={`badge ${tone}`}>{children}</span>;

export const DecisionBadge = ({ d }) => {
  const m = { BLOCK: ["red", "High risk"], STEP_UP_AUTH: ["amber", "Moderate risk"], ALLOW: ["green", "Low risk"] }[d] || ["gray", d];
  return <Badge tone={m[0]}>{m[1]}</Badge>;
};

export const ScoreBar = ({ value }) => {
  const tone = value >= 80 ? "red" : value >= 40 ? "amber" : "green";
  return (
    <div className="scorebar" title={`${value}`}>
      <i className={tone} style={{ width: `${Math.min(100, Math.max(2, value))}%` }} />
      <span>{value.toFixed(1)}%</span>
    </div>
  );
};

export const Empty = ({ children }) => <div className="empty">{children}</div>;
export const ErrorNote = ({ error }) => (error ? <div className="note bad">{error}</div> : null);

export function TxnTable({ rows, onStatus, compact, showTransactionId = false }) {
  const [open, setOpen] = useState(null);
  if (!rows?.length) return <Empty>No transactions yet.</Empty>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {showTransactionId && <th>Transaction ID</th>}
            <th>Ref</th><th>Bank</th><th>Category</th><th className="num">Amount</th><th>Risk %</th><th>Risk tier</th>
            {!compact && <th>Why</th>}{onStatus && <th>Analyst</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Fragment key={r.id}>
              <tr className={open === r.id ? "sel" : ""} onClick={() => setOpen(open === r.id ? null : r.id)}>
                {showTransactionId && <td className="mono">{r.transaction_id || r.txn_ref || r.id}</td>}
                <td className="mono">{r.reference_id || r.txn_ref}</td><td>{r.bank}</td><td>{r.category}</td>
                <td className="num">{inr(r.amount)}</td><td><ScoreBar value={r.risk_score} /></td>
                <td><DecisionBadge d={r.decision} /></td>
                {!compact && <td className="why">{r.reasons?.[0]?.reason || <span className="muted">—</span>}</td>}
                {onStatus && (
                  <td onClick={(e) => e.stopPropagation()}>
                    {r.status === "open" ? (
                      <div className="btn-row">
                        <button className="mini red" onClick={() => onStatus(r.id, "confirmed_fraud")}>Fraud</button>
                        <button className="mini" onClick={() => onStatus(r.id, "dismissed")}>Dismiss</button>
                      </div>
                    ) : (
                      <Badge tone={r.status === "confirmed_fraud" ? "red" : "gray"}>{r.status.replace("_", " ")}</Badge>
                    )}
                  </td>
                )}
              </tr>
              {open === r.id && (
                <tr key={`${r.id}-d`} className="detail">
                  <td colSpan={showTransactionId ? 10 : 9}>
                    <ReasonList reasons={r.reasons} />
                    {r.ground_truth !== null && r.ground_truth !== undefined && (
                      <small className="muted">Simulation ground truth: {r.ground_truth ? "fraud" : "legitimate"}</small>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const ReasonList = ({ reasons }) =>
  reasons?.length ? (
    <ul className="reasons">
      {reasons.map((x, i) => (
        <li key={i}>
          <span>{x.reason}</span>
          {x.weight != null && <i style={{ width: `${Math.round(x.weight * 100)}%` }} />}
          {x.weight == null ? <b className="rule-tag">Rule</b> : <b>{Math.round(x.weight * 100)}%</b>}
        </li>
      ))}
    </ul>
  ) : (
    <small className="muted">No risk drivers — transaction looks normal.</small>
  );
