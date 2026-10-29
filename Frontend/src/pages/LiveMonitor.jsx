import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Database, LoaderCircle, Pause, Play, RefreshCw, Trash2 } from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, inr } from "../services/api";
import { Card, ErrorNote, Page, Stat, TxnTable } from "../components/ui";

const LIVE_BANKS = ["Bank A", "Bank B", "Bank C", "Bank D", "Bank E"];
const LIVE_CATEGORIES = ["p2p", "merchant", "investment"];

function makeLiveSnapshot() {
  const count = 24 + Math.floor(Math.random() * 13);
  const stamp = Date.now();
  return Array.from({ length: count }, (_, index) => {
    const riskScore = Math.round(Math.pow(Math.random(), 1.75) * 999) / 10;
    const decision = riskScore >= 80 ? "BLOCK" : riskScore >= 40 ? "STEP_UP_AUTH" : "ALLOW";
    const reason = decision === "BLOCK"
      ? "High-risk behavior detected in the live stream"
      : decision === "STEP_UP_AUTH" ? "Unusual transaction pattern requires verification" : null;
    return {
      id: `live-${stamp}-${index}`,
      txn_ref: `LIVE${String(stamp).slice(-6)}${String(index + 1).padStart(3, "0")}`,
      bank: LIVE_BANKS[Math.floor(Math.random() * LIVE_BANKS.length)],
      category: LIVE_CATEGORIES[Math.floor(Math.random() * LIVE_CATEGORIES.length)],
      amount: Math.round(100 + Math.random() * 149900),
      risk_score: riskScore,
      risk_level: decision === "BLOCK" ? "high" : decision === "STEP_UP_AUTH" ? "moderate" : "low",
      decision,
      reasons: reason ? [{ reason, weight: Math.min(0.99, riskScore / 100) }] : [],
      status: decision === "ALLOW" ? "auto" : "open",
      ground_truth: null,
      source: "live_simulation",
      created_at: new Date(stamp - index * 9000).toISOString(),
    };
  });
}

export default function LiveMonitor() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const datasetId = searchParams.get("dataset_id");
  const uploadSummary = location.state?.uploadSummary;
  const [datasets, setDatasets] = useState([]);
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [err, setErr] = useState("");
  const timer = useRef(null);

  const selectedDataset = datasets.find((dataset) => String(dataset.id) === datasetId);
  const uploadedMode = Boolean(datasetId);
  const filename = selectedDataset?.filename || uploadSummary?.filename;

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      if (datasetId) {
        setRows(await api.transactions({ limit: 150, dataset_id: datasetId }));
      } else {
        if (!quiet) await new Promise((resolve) => window.setTimeout(resolve, 300));
        setRows(makeLiveSnapshot());
      }
      setLastUpdated(new Date());
      setErr("");
    } catch (error) {
      setErr(error.message);
      setRunning(false);
    } finally {
      setLoading(false);
      if (!quiet) setRefreshing(false);
    }
  }, [datasetId]);

  useEffect(() => {
    api.datasets().then(setDatasets).catch((error) => setErr(error.message));
  }, []);

  useEffect(() => {
    setLoading(true);
    refresh();
  }, [refresh]);

  useEffect(() => {
    clearInterval(timer.current);
    if (running && !uploadedMode) timer.current = setInterval(() => refresh(true), 15000);
    return () => clearInterval(timer.current);
  }, [refresh, running, uploadedMode]);

  const showLive = () => navigate("/monitor", { replace: true, state: null });

  const showUploaded = () => {
    const nextId = datasetId || datasets[0]?.id;
    if (!nextId) {
      setErr("No uploaded datasets are available. Upload and analyze a file first.");
      return;
    }
    navigate(`/monitor?dataset_id=${nextId}`, { replace: true, state: null });
  };

  const chooseDataset = (nextId) => {
    navigate(`/monitor?dataset_id=${nextId}`, { replace: true, state: null });
  };

  const clearLiveTransactions = () => {
    setRows([]);
    setErr("");
    setLastUpdated(new Date());
  };

  const flagged = rows.filter((row) => row.decision !== "ALLOW");
  const blocked = rows.filter((row) => row.decision === "BLOCK");
  const confirmed = rows.filter((row) => row.status === "confirmed_fraud");

  return (
    <Page
      title={uploadedMode ? "Uploaded dataset monitor" : "Live monitor"}
      sub={uploadedMode
        ? `Previously analyzed transactions from ${filename || "the selected uploaded file"}.`
        : "Simulated live transaction activity generates a fresh snapshot every 15 seconds."}
      actions={(
        <div className="monitor-header-actions">
          <button className="btn ghost" onClick={() => refresh()} disabled={refreshing} aria-busy={refreshing}>
            {refreshing ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          {!uploadedMode && (
            <button className="btn" onClick={() => setRunning((value) => !value)}>
              {running ? <><Pause size={16} /> Pause updates</> : <><Play size={16} /> Resume updates</>}
            </button>
          )}
          {!uploadedMode && (
            <button className="btn ghost" onClick={clearLiveTransactions}><Trash2 size={16} /> Clear</button>
          )}
        </div>
      )}
    >
      <section className="monitor-modebar" aria-label="Monitoring source">
        <div className="seg monitor-tabs">
          <button className={!uploadedMode ? "on" : ""} onClick={showLive} aria-pressed={!uploadedMode}>
            <Activity size={16} /> Live transactions
          </button>
          <button className={uploadedMode ? "on" : ""} onClick={showUploaded} aria-pressed={uploadedMode}>
            <Database size={16} /> Uploaded datasets
          </button>
        </div>
        {uploadedMode && (
          <label className="dataset-picker">
            <span>Choose analyzed file</span>
            <select value={datasetId} onChange={(event) => chooseDataset(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>{dataset.filename} · {dataset.rows.toLocaleString()} rows</option>
              ))}
            </select>
          </label>
        )}
      </section>

      <ErrorNote error={err} />
      {uploadSummary && String(uploadSummary.filename) === String(filename) && (
        <div className="note good monitor-upload-note" role="status">
          <b>{uploadSummary.filename} analyzed successfully.</b>
          <span>{uploadSummary.rows.toLocaleString()} transactions scored · {uploadSummary.flagged.toLocaleString()} flagged for review</span>
        </div>
      )}
      <div className="grid stats">
        <Stat
          label={uploadedMode ? "Dataset transactions" : "Recent transactions"}
          value={rows.length}
          sub={uploadedMode ? "stored analysis remains unchanged" : running ? "new snapshot every 15 seconds" : "automatic updates paused"}
        />
        <Stat label="Flagged" value={flagged.length} tone="amber" sub="moderate and high risk" />
        <Stat label="Confirmed fraud" value={confirmed.length} tone="red" sub="analyst-confirmed cases" />
        <Stat label="High-risk value" value={inr(blocked.reduce((sum, row) => sum + row.amount, 0))} tone="red" />
      </div>
      <Card
        title={uploadedMode ? "Uploaded file results" : "Live transaction feed"}
        hint={loading
          ? "Loading…"
          : uploadedMode
            ? `${filename || "Selected file"} · refresh reloads the same stored analysis`
            : `Randomized demo stream${lastUpdated ? ` · updated ${lastUpdated.toLocaleTimeString()}` : ""}`}
      >
        <TxnTable rows={rows} />
      </Card>
    </Page>
  );
}
