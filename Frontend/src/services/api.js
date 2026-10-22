const TOKEN_KEY = "fedupi.token";
export const token = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch {} },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch {} },
};

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn);

async function raw(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const t = token.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : j.detail?.map?.((d) => d.msg).join("; ") || JSON.stringify(j.detail);
    } catch {}
    if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/register")) onUnauthorized();
    throw new Error(msg);
  }
  return res;
}
const req = async (path, opts) => (await raw(path, opts)).json();
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/** Download a file endpoint through fetch so the auth header is sent. */
export async function download(path, fallbackName = "download") {
  const res = await raw(path);
  const cd = res.headers.get("Content-Disposition") || "";
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] || fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const api = {
  health: () => fetch("/api/health").then((r) => r.json()),
  login: (b) => req("/auth/login", json("POST", b)),
  register: (b) => req("/auth/register", json("POST", b)),
  me: () => req("/auth/me"),
  updateMe: (b) => req("/auth/me", json("PATCH", b)),
  changePassword: (b) => req("/auth/password", json("POST", b)),
  overview: () => req("/overview"),
  score: (t) => req("/transactions/score", json("POST", t)),
  upload: (file) => {
    const f = new FormData();
    f.append("file", file);
    return req("/datasets", { method: "POST", body: f });
  },
  datasets: () => req("/datasets"),
  rescore: (id) => req(`/datasets/${id}/rescore`, { method: "POST" }),
  deleteDataset: (id) => req(`/datasets/${id}`, { method: "DELETE" }),
  downloadOriginal: (id) => download(`/datasets/${id}/file`),
  exportFlagged: (format, { datasetId, decision, status } = {}) => {
    const q = new URLSearchParams({ format });
    if (datasetId) q.set("dataset_id", datasetId);
    if (decision) q.set("decision", decision);
    if (status) q.set("status", status);
    return download(`/export/flagged?${q}`, `fedupi-flagged.${format}`);
  },
  transactions: (q = {}) => req(`/transactions?${new URLSearchParams(q)}`),
  setStatus: (id, status) => req(`/transactions/${id}`, json("PATCH", { status })),
  clear: () => req("/transactions", { method: "DELETE" }),
  report: () => req("/model/report"),
  fedStatus: () => req("/federated/status"),
  fedTrain: (cfg) => req("/federated/train", json("POST", cfg)),
  epsilon: (noise, rounds, delta) => req(`/privacy/epsilon?noise=${noise}&rounds=${rounds}&delta=${delta}`),
  papers: () => req("/papers"),
};

export const inr = (v) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v || 0);
export const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`;
export const bytes = (n) => (n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} KB`);
