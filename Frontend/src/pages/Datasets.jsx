import { useRef, useState } from "react";
import { ArrowRight, FileCheck2, FileText, LoaderCircle, ShieldCheck, Upload, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, bytes } from "../services/api";
import { Card, ErrorNote, Page } from "../components/ui";

const MAX_UPLOAD_BYTES = 300 * 1024 * 1024;
const ACCEPTED_FILES = ".csv,.xlsx,.xlsm,.json,.docx,.txt,.tsv";

export default function Datasets() {
  const navigate = useNavigate();
  const input = useRef();
  const [file, setFile] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);

  const choose = (nextFile) => {
    if (!nextFile) return;
    setErr("");
    if (nextFile.size > MAX_UPLOAD_BYTES) {
      setFile(null);
      setErr("File larger than 300 MB. Choose a smaller file.");
      if (input.current) input.current.value = "";
      return;
    }
    setFile(nextFile);
  };

  const clearFile = () => {
    setFile(null);
    setErr("");
    if (input.current) input.current.value = "";
  };

  const analyze = async () => {
    if (!file || busy) return;
    setBusy(true);
    setErr("");
    try {
      const result = await api.upload(file);
      navigate(`/monitor?dataset_id=${result.dataset.id}`, {
        state: {
          uploadSummary: {
            filename: result.dataset.filename,
            rows: result.rows,
            flagged: result.flagged,
          },
        },
      });
    } catch (error) {
      setErr(error.message);
      setBusy(false);
    }
  };

  return (
    <Page
      title="Upload files for analysis"
      sub="Choose a transaction dataset or supported document, then start the fraud analysis when you are ready."
    >
      <Card className="upload-intake">
        <div
          className={`drop upload-drop ${drag ? "over" : ""} ${busy ? "uploading" : ""}`}
          onClick={busy ? undefined : () => input.current?.click()}
          onDragOver={(event) => { event.preventDefault(); if (!busy) setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDrag(false);
            if (!busy) choose(event.dataTransfer.files[0]);
          }}
          role="button"
          tabIndex={busy ? -1 : 0}
          onKeyDown={(event) => {
            if (!busy && (event.key === "Enter" || event.key === " ")) input.current?.click();
          }}
          aria-label="Choose a file for fraud analysis"
          aria-busy={busy}
        >
          <span className="upload-icon"><Upload size={28} /></span>
          <b>{file ? "Choose a different file" : "Drop a file here, or browse your device"}</b>
          <span>CSV, Excel, JSON, Word tables, TXT or TSV · up to 300 MB</span>
          <input
            ref={input}
            type="file"
            accept={ACCEPTED_FILES}
            hidden
            disabled={busy}
            onChange={(event) => choose(event.target.files[0])}
          />
        </div>

        {file && (
          <div className="selected-file" aria-live="polite">
            <span className="selected-file-icon"><FileText size={21} /></span>
            <div><b>{file.name}</b><small>{bytes(file.size)} · ready to analyze</small></div>
            <FileCheck2 className="file-ready" size={20} aria-label="File ready" />
            <button className="icon-btn" onClick={clearFile} disabled={busy} aria-label="Remove selected file"><X size={17} /></button>
          </div>
        )}

        <ErrorNote error={err} />

        <div className="upload-submit">
          <div className="upload-privacy">
            <ShieldCheck size={18} />
            <span><b>Results stay off this page.</b> After analysis, this file opens in Live Monitor.</span>
          </div>
          <button className="btn analyze-btn" onClick={analyze} disabled={!file || busy}>
            {busy ? <><LoaderCircle className="spin" size={17} /> Analyzing file…</> : <>Upload & analyze <ArrowRight size={17} /></>}
          </button>
        </div>
      </Card>
    </Page>
  );
}
