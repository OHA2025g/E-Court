import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api, formatApiError } from "@/lib/api";
import { PASSWORD_POLICY_HINT, validatePasswordClient } from "@/lib/passwordPolicy";
import { useAdminLabels } from "@/lib/useAdminLabels";
import { toast } from "sonner";
import { FloppyDisk, Key } from "@phosphor-icons/react";

export default function ChangePassword() {
  const { account: a } = useAdminLabels();
  const { user, loading, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [cur, setCur] = useState("");
  const [nxt, setNxt] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user && !user.must_change_password && !user.password_expired) {
    return <Navigate to="/app-selector" replace />;
  }

  async function save(e) {
    e.preventDefault();
    if (nxt !== confirm) {
      toast.error(a.passwordMismatch);
      return;
    }
    const policyErr = validatePasswordClient(nxt);
    if (policyErr) {
      toast.error(policyErr);
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: nxt });
      toast.success(a.passwordUpdated);
      const updated = await refreshUser();
      if (updated && !updated.must_change_password && !updated.password_expired) {
        navigate("/app-selector", { replace: true });
      }
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <form onSubmit={save} className="w-full max-w-md bg-white rounded-sm border border-slate-200 shadow-sm p-8">
        <div className="flex items-center gap-2 mb-1">
          <Key size={22} className="text-[#003B73]" />
          <h1 className="font-display text-2xl font-bold text-slate-900">{a.changePasswordHeading}</h1>
        </div>
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-sm p-3 mb-6">
          {user.password_expired ? a.mandatoryChangeExpired : a.mandatoryChangeTemp}
        </p>
        <p className="text-xs text-slate-500 mb-4">{PASSWORD_POLICY_HINT}</p>
        <label className="block mb-4">
          <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.currentPassword}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={cur}
            onChange={(e) => setCur(e.target.value)}
            className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73]"
          />
        </label>
        <label className="block mb-4">
          <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.newPassword}</span>
          <input
            type="password"
            autoComplete="new-password"
            required
            value={nxt}
            onChange={(e) => setNxt(e.target.value)}
            className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73]"
          />
        </label>
        <label className="block mb-6">
          <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.confirmPassword}</span>
          <input
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73] focus:ring-1 focus:ring-[#003B73]"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !cur || !nxt || !confirm}
          className="w-full bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white py-2.5 rounded-sm font-medium uppercase tracking-wider text-sm inline-flex items-center justify-center gap-2"
        >
          <FloppyDisk size={16} />
          {busy ? a.updating : a.updatePassword}
        </button>
      </form>
    </div>
  );
}
