import { useEffect, useRef, useState } from "react";
import { ChevronDown, Download, FileSpreadsheet, FileText, FileType2, Braces, FileDown } from "lucide-react";
import { api } from "../services/api";

const FORMATS = [
  ["xlsx", "Excel (.xlsx)", FileSpreadsheet],
  ["csv", "CSV (.csv)", FileText],
  ["docx", "Word (.docx)", FileType2],
  ["pdf", "PDF (.pdf)", FileDown],
  ["json", "JSON (.json)", Braces],
];

/** Dropdown that downloads detected (flagged) fraud in the chosen format. */
export default function ExportMenu({ datasetId, decision, status, label = "Download fraud report", disabled, onError }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const ref = useRef();
  useEffect(() => {
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const run = async (fmt) => {
    setBusy(fmt);
    try { await api.exportFlagged(fmt, { datasetId, decision, status }); setOpen(false); }
    catch (e) { onError?.(e.message); }
    setBusy("");
  };
  return (
    <div className="menu-wrap" ref={ref}>
      <button className="btn" disabled={disabled} onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <Download size={15} /> {label} <ChevronDown size={14} />
      </button>
      {open && (
        <div className="menu" role="menu">
          {FORMATS.map(([k, name, Icon]) => (
            <button key={k} role="menuitem" onClick={() => run(k)} disabled={!!busy}>
              <Icon size={16} /> {busy === k ? "Preparing…" : name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
