import { useState } from "react";
import { ShieldCheck, Moon, Sun } from "lucide-react";
import { useAuth, useTheme } from "../context";

export default function Login() {
  const { login, register } = useAuth();
  const { theme, toggle } = useTheme();
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ name: "", email: "", password: "", organization: "" });
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr(""); setNotice("");
    try {
      if (mode === "login") await login({ email: f.email, password: f.password });
      else {
        await register(f);
        setF((current) => ({ ...current, name: "", organization: "", password: "" }));
        setMode("login");
        setNotice("Account created successfully. Sign in to continue.");
      }
    } catch (x) { setErr(x.message); }
    setBusy(false);
  };

  return (
    <div className="auth">
      <button className="icon-btn auth-theme" onClick={toggle} aria-label="Toggle theme">{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
      <section className="auth-hero">
        <div className="brand big"><ShieldCheck size={30} /><b>FedUPI</b></div>
        <h1>Fraud detection that never moves your data.</h1>
        <p>Banks train one shared model on UPI patterns while every transaction stays inside its own walls. Sign in to monitor, investigate and export.</p>
        <ul>
          <li>Federated learning with secure aggregation</li>
          <li>Plain-language reasons for every decision</li>
          <li>Upload data, download fraud reports in Excel, Word, PDF or CSV</li>
        </ul>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        <p className="muted">{mode === "login" ? "Sign in to continue to your dashboard." : "Takes less than a minute."}</p>
        {mode === "register" && (
          <>
            <label>Full name<input value={f.name} onChange={set("name")} required minLength={2} autoComplete="name" /></label>
            <label>Organization <small>(optional)</small><input value={f.organization} onChange={set("organization")} autoComplete="organization" /></label>
          </>
        )}
        <label>Email<input type="email" value={f.email} onChange={set("email")} required autoComplete="email" /></label>
        <label>Password<input type="password" value={f.password} onChange={set("password")} required minLength={mode === "register" ? 8 : 1}
          autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {mode === "register" && <small>At least 8 characters.</small>}</label>
        {notice && <div className="note good" role="status">{notice}</div>}
        {err && <div className="note bad" role="alert">{err}</div>}
        <button className="btn wide" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <p className="switch">
          {mode === "login" ? "New here?" : "Already registered?"}{" "}
          <a href="#" onClick={(e) => { e.preventDefault(); setErr(""); setNotice(""); setMode(mode === "login" ? "register" : "login"); }}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </a>
        </p>
      </form>
    </div>
  );
}
