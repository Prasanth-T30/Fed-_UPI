import { useState } from "react";
import { Activity, Building2, LockKeyhole, Moon, ShieldCheck, Sparkles, Sun } from "lucide-react";
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
        <div className="auth-copy">
          <div className="brand big"><span className="brand-mark"><ShieldCheck size={24} /></span><div><b>FedUPI</b><small>Privacy-first fraud intelligence</small></div></div>
          <span className="auth-kicker"><Sparkles size={14} /> Collaborative intelligence. Private by design.</span>
          <h1>One fraud shield.<br /><em>Five private banks.</em></h1>
          <p>Detect suspicious UPI activity with a shared model while each institution keeps its transaction records local.</p>
          <div className="auth-proof">
            <span><LockKeyhole size={15} /> Raw data stays local</span>
            <span><Activity size={15} /> Live risk decisions</span>
          </div>
        </div>
        <div className="federation-visual" aria-label="Animated federated learning network">
          <div className="visual-glow" />
          <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" />
          <div className="visual-core"><ShieldCheck size={29} /><b>Global</b><small>FedAvg model</small><i /></div>
          {["A", "B", "C", "D", "E"].map((bank, index) => (
            <div className={`bank-node bank-${index + 1}`} key={bank}>
              <Building2 size={15} /><b>Bank {bank}</b><span>local weights</span>
            </div>
          ))}
          <div className="signal signal-one" /><div className="signal signal-two" /><div className="signal signal-three" />
          <div className="privacy-chip"><LockKeyhole size={13} /> 0 raw records shared</div>
        </div>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-card-top"><span>Secure workspace</span><i><LockKeyhole size={13} /> Encrypted session</i></div>
        <h2>{mode === "login" ? "Welcome back" : "Join FedUPI"}</h2>
        <p className="muted">{mode === "login" ? "Sign in to open your fraud operations workspace." : "Create your analyst account. You will sign in after registration."}</p>
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
        <button className="btn wide auth-submit" disabled={busy}>{busy ? <><span className="button-spinner" /> Verifying…</> : mode === "login" ? <>Open secure workspace <span>→</span></> : <>Create analyst account <span>→</span></>}</button>
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
