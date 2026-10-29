import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, BarChart3, BellRing, BookOpen, ChevronDown, Download, FlaskConical, LayoutDashboard, LogOut, Menu, Moon,
  ScanSearch, ShieldCheck, Sun, Upload, UserRound, X,
} from "lucide-react";
import { api } from "./services/api";
import { useAuth, useTheme } from "./context";
import Login from "./pages/Login.jsx";

const PAGE_LOADERS = {
  "/": () => import("./pages/Dashboard.jsx"),
  "/monitor": () => import("./pages/LiveMonitor.jsx"),
  "/check": () => import("./pages/CheckTransaction.jsx"),
  "/upload": () => import("./pages/Datasets.jsx"),
  "/alerts": () => import("./pages/Alerts.jsx"),
  "/reports": () => import("./pages/Reports.jsx"),
  "/lab": () => import("./pages/FederatedLab.jsx"),
  "/insights": () => import("./pages/ModelInsights.jsx"),
  "/research": () => import("./pages/Research.jsx"),
  "/profile": () => import("./pages/Profile.jsx"),
};

const Dashboard = lazy(PAGE_LOADERS["/"]);
const LiveMonitor = lazy(PAGE_LOADERS["/monitor"]);
const CheckTransaction = lazy(PAGE_LOADERS["/check"]);
const Datasets = lazy(PAGE_LOADERS["/upload"]);
const Alerts = lazy(PAGE_LOADERS["/alerts"]);
const Reports = lazy(PAGE_LOADERS["/reports"]);
const FederatedLab = lazy(PAGE_LOADERS["/lab"]);
const ModelInsights = lazy(PAGE_LOADERS["/insights"]);
const Research = lazy(PAGE_LOADERS["/research"]);
const Profile = lazy(PAGE_LOADERS["/profile"]);

const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("") || "U";

function RouteLoader() {
  return <div className="route-loader" role="status" aria-label="Loading page"><i /><span>Loading page…</span></div>;
}

const NAV = [
  ["/", "Dashboard", LayoutDashboard],
  ["/monitor", "Live Monitor", Activity],
  ["/check", "Check Transaction", ScanSearch],
  ["/upload", "Upload & Analyze", Upload],
  ["/alerts", "Alert Queue", BellRing],
  ["/reports", "Downloads", Download],
  ["/lab", "Federated Lab", FlaskConical],
  ["/insights", "Model Insights", BarChart3],
  ["/research", "Research & Papers", BookOpen],
];

function ProfileMenu() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef();
  useEffect(() => {
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="menu-wrap" ref={ref}>
      <button className="profile-btn" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <span className="avatar">{initials(user.name)}</span>
        <span className="who"><b>{user.name}</b><small>{user.role}</small></span>
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="menu right" role="menu">
          <div className="menu-head"><b>{user.name}</b><small>{user.email}</small></div>
          <button role="menuitem" onClick={() => { setOpen(false); nav("/profile"); }}><UserRound size={16} /> Profile & settings</button>
          <button role="menuitem" onClick={logout}><LogOut size={16} /> Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  const { theme, toggle } = useTheme();
  const [health, setHealth] = useState(null);
  const [drawer, setDrawer] = useState(false);
  const loc = useLocation();
  useEffect(() => { setDrawer(false); window.scrollTo(0, 0); }, [loc.pathname]);
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  useEffect(() => {
    if (user) api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, [user]);
  useEffect(() => {
    if (!user) return undefined;
    const loaders = Object.values(PAGE_LOADERS);
    let index = 0;
    let timer;
    const prefetchNext = () => {
      loaders[index++]?.();
      if (index < loaders.length) timer = window.setTimeout(prefetchNext, 180);
    };
    timer = window.setTimeout(prefetchNext, 700);
    return () => window.clearTimeout(timer);
  }, [user]);

  if (loading) return <div className="splash"><ShieldCheck size={28} /></div>;
  if (!user) return <Login />;

  return (
    <div className="shell">
      <aside className={`side ${drawer ? "open" : ""}`} aria-hidden={!drawer}>
        <div className="brand">
          <ShieldCheck size={26} />
          <div><b>FedUPI</b><small>Federated fraud shield</small></div>
          <button className="icon-btn close-drawer" onClick={() => setDrawer(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav>
          {NAV.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "on" : "")}
              onMouseEnter={() => PAGE_LOADERS[to]()} onFocus={() => PAGE_LOADERS[to]() }>
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <span className={`dot ${health?.model_ready ? "ok" : "bad"}`} />
          {health === null ? "Connecting…" : health.status === "down" ? "API offline" : health.model_ready ? "Model loaded" : "Model not trained"}
          <small>{health?.model_version}</small>
        </div>
      </aside>
      {drawer && <div className="scrim" onClick={() => setDrawer(false)} />}
      <div className="content">
        <header className="topbar">
          <button className="icon-btn burger" onClick={() => setDrawer(true)} aria-label="Open menu" aria-expanded={drawer}><Menu size={20} /></button>
          <div className="topbar-brand"><ShieldCheck size={20} />FedUPI</div>
          <div className="spacer" />
          <button className="icon-btn" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title="Toggle theme">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <ProfileMenu />
        </header>
        <main className="main">
          <Suspense fallback={<RouteLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/monitor" element={<LiveMonitor />} />
              <Route path="/check" element={<CheckTransaction />} />
              <Route path="/upload" element={<Datasets />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/lab" element={<FederatedLab />} />
              <Route path="/insights" element={<ModelInsights />} />
              <Route path="/research" element={<Research />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
