import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { clearLiveTransactions } from "../services/liveTransactions";
import { useAuth, useTheme } from "../context";
import { Card, Page } from "../components/ui";

export const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join("") || "U";

export default function Profile() {
  const navigate = useNavigate();
  const { user, setUser, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [p, setP] = useState({ name: user.name, organization: user.organization || "", role: user.role || "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [msg, setMsg] = useState({});
  const [resetting, setResetting] = useState(false);
  const flash = (k, ok, text) => setMsg((m) => ({ ...m, [k]: { ok, text } }));

  const save = async (e) => {
    e.preventDefault();
    try { setUser(await api.updateMe(p)); flash("p", true, "Profile saved."); } catch (x) { flash("p", false, x.message); }
  };
  const changePw = async (e) => {
    e.preventDefault();
    try { await api.changePassword(pw); setPw({ current_password: "", new_password: "" }); flash("w", true, "Password updated."); }
    catch (x) { flash("w", false, x.message); }
  };
  const Note = ({ k }) => msg[k] ? <div className={`note ${msg[k].ok ? "good" : "bad"}`}>{msg[k].text}</div> : null;

  const refreshProject = async () => {
    if (!window.confirm("Refresh all project data? This permanently removes your uploaded datasets, transaction history, alerts, searches, and dashboard results.")) return;
    setResetting(true);
    try {
      await api.resetProjectData();
      clearLiveTransactions(user.id);
      navigate("/", { replace: true });
    } catch (error) {
      flash("r", false, error.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <Page title="Profile" sub="Manage your account, appearance and security.">
      <div className="profile-head card">
        <div className="avatar xl">{initials(user.name)}</div>
        <div><h2>{user.name}</h2><p className="muted">{user.email}</p>
          <small className="muted">Member since {new Date(user.created_at).toLocaleDateString()}</small></div>
        <button className="btn ghost" onClick={logout}>Sign out</button>
      </div>
      <div className="grid two">
        <Card title="Personal details">
          <form className="stack" onSubmit={save}>
            <label>Full name<input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} required minLength={2} /></label>
            <label>Email<input value={user.email} disabled /></label>
            <label>Organization<input value={p.organization} onChange={(e) => setP({ ...p, organization: e.target.value })} /></label>
            <label>Role<input value={p.role} onChange={(e) => setP({ ...p, role: e.target.value })} /></label>
            <Note k="p" /><button className="btn">Save changes</button>
          </form>
        </Card>
        <div className="stack-cards">
          <Card title="Appearance">
            <div className="row-between"><span>Theme</span>
              <div className="seg">
                <button className={theme === "light" ? "on" : ""} onClick={() => theme !== "light" && toggle()}>Light</button>
                <button className={theme === "dark" ? "on" : ""} onClick={() => theme !== "dark" && toggle()}>Dark</button>
              </div></div>
          </Card>
          <Card title="Refresh project data" hint="Start every operational module with a clean state">
            <p className="muted small">Removes uploaded datasets, dashboard activity, alerts, transaction searches, and the current live snapshot. Your account, profile, theme, model, and research configuration are preserved.</p>
            <Note k="r" />
            <button className="btn red mt" onClick={refreshProject} disabled={resetting}>
              <RefreshCw className={resetting ? "spin" : ""} size={16} /> {resetting ? "Refreshing…" : "Refresh all project data"}
            </button>
          </Card>
          <Card title="Change password">
            <form className="stack" onSubmit={changePw}>
              <label>Current password<input type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required autoComplete="current-password" /></label>
              <label>New password<input type="password" minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required autoComplete="new-password" /></label>
              <Note k="w" /><button className="btn">Update password</button>
            </form>
          </Card>
        </div>
      </div>
    </Page>
  );
}
