import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, setUnauthorizedHandler, token } from "./services/api";

/* ---------------- theme ---------------- */
const ThemeCtx = createContext(null);
export const useTheme = () => useContext(ThemeCtx);

function initialTheme() {
  try {
    const saved = localStorage.getItem("fedupi.theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {}
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("fedupi.theme", theme); } catch {}
  }, [theme]);
  return <ThemeCtx.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}>{children}</ThemeCtx.Provider>;
}

/* ---------------- auth ---------------- */
const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!token.get());

  const logout = useCallback(() => { token.clear(); setUser(null); }, []);
  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (token.get()) api.me().then(setUser).catch(logout).finally(() => setLoading(false));
  }, [logout]);

  const accept = ({ token: t, user: u }) => { token.set(t); setUser(u); };
  const value = {
    user, loading, logout, setUser,
    login: async (b) => accept(await api.login(b)),
    register: (b) => api.register(b),
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
