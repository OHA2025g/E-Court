import React, { createContext, useContext, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
      return r.data;
    } catch {
      setUser(false);
      return false;
    }
  }

  useEffect(() => {
    let mounted = true;
    refreshUser()
      .then((u) => mounted && setUser(u || false))
      .catch(() => mounted && setUser(false))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  async function login(email, password, totp_code, captcha_id, captcha_answer) {
    try {
      const r = await api.post("/auth/login", {
        email,
        password,
        totp_code,
        captcha_id,
        captcha_answer,
      });
      if (r.data?.requires_2fa) {
        return { requires_2fa: true, email: r.data.email };
      }
      setUser(r.data.user);
      toast.success(`Welcome, ${r.data.user.name}`);
      return r.data.user;
    } catch (e) {
      const status = e.response?.status;
      const detail = e.response?.data?.detail;
      const msg = formatApiError(detail) || e.message;
      if (status !== 423) toast.error(msg);
      throw e;
    }
  }

  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(false);
    }
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refreshUser, setUser }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
