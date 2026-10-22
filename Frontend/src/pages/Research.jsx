import { useEffect, useState } from "react";
import { ArrowRight, Building2, Server } from "lucide-react";
import { api } from "../services/api";
import { Card, Page } from "../components/ui";

const MODULES = [
  ["Data layer", "UPI-style generator, 5 banks, 6 fraud typologies, fixed-scale feature engineering."],
  ["Federated engine", "FedAvg, FedProx, DP clipping + noise; parameters-only communication."],
  ["AI models", "Supervised MLP classifier + unsupervised autoencoder (novelty signal); fused only if it improves validation F1."],
  ["Explainability", "Per-transaction gradient×input attribution turned into plain-language reasons."],
  ["Risk policy", "High risk only above ₹99,999; moderate for ₹70,000–99,999, repeated payments to one receiver, or model-flagged; risk % per payment."],
  ["Analyst loop", "Alert queue, confirm/dismiss labels stored for retraining."],
];

export default function Research() {
  const [papers, setPapers] = useState([]);
  useEffect(() => { api.papers().then(setPapers).catch(() => {}); }, []);
  return (
    <Page title="Research & architecture" sub="How the system works and the papers it builds on.">
      <Card title="Architecture">
        <div className="arch">
          <div className="banks-col">
            {["Bank A", "Bank B", "Bank C", "Bank D", "Bank E"].map((b) => <div key={b} className="node"><Building2 size={16} /> {b}<small>private data + local training</small></div>)}
          </div>
          <div className="arrow"><ArrowRight /><small>model weights ↑</small><small>global model ↓</small></div>
          <div className="node big"><Server size={22} />Aggregator<small>FedAvg / FedProx<br />clip + noise (optional)</small></div>
          <div className="arrow"><ArrowRight /></div>
          <div className="node big green">Fraud scoring API<small>classifier + autoencoder<br />explanations · decisions</small></div>
        </div>
      </Card>
      <div className="grid three">
        {MODULES.map(([t, d], i) => <Card key={t} title={`${i + 1}. ${t}`}><p className="small">{d}</p></Card>)}
      </div>
      <Card title="Base papers & references">
        <ul className="papers">
          {papers.map((p) => (
            <li key={p.url}>
              <a href={p.url} target="_blank" rel="noreferrer">{p.title}</a>
              <small>{p.authors} · {p.venue}</small>
              <span>{p.used_for}</span>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Honest limitations">
        <ul className="small plain">
          <li>Model quality depends on the coverage and accuracy of the labelled dataset supplied for training.</li>
          <li>Model updates can leak information. Secure aggregation and a formal DP budget (ε) are future work.</li>
          <li>The scoring API receives transaction signals in clear; this is a bank-side deployment, not private inference.</li>
        </ul>
      </Card>
    </Page>
  );
}
