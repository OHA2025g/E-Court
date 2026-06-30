import React, { useState } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAdminLabels } from "@/lib/useAdminLabels";
import { PASSWORD_POLICY_HINT, validatePasswordClient } from "@/lib/passwordPolicy";
import { useAccessibleRag } from "@/lib/ragColors";
import Card from "@/components/Card";
import { toast } from "sonner";
import { Key, ShieldCheck, ShieldWarning, FloppyDisk, SignOut } from "@phosphor-icons/react";

function ChangePasswordCard() {
  const { account: a } = useAdminLabels();
  const { refreshUser } = useAuth();
  const [cur, setCur] = useState("");
  const [nxt, setNxt] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function savePassword() {
    const err = validatePasswordClient(nxt);
    if (err) { toast.error(err); return; }
    if (nxt !== confirm) { toast.error(a.passwordMismatch); return; }
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: nxt });
      toast.success(a.passwordUpdated);
      setCur(""); setNxt(""); setConfirm("");
      await refreshUser();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={a.changePasswordTitle} subtitle={a.changePasswordSubtitle}>
      <div className="p-4 space-y-3">
        <p className="text-xs text-slate-500">{PASSWORD_POLICY_HINT}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.currentPassword}</span>
            <input type="password" value={cur} onChange={(e) => setCur(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.newPassword}</span>
            <input type="password" value={nxt} onChange={(e) => setNxt(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]" />
          </label>
          <label className="block sm:col-span-2">
            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{a.confirmPassword}</span>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]" />
          </label>
        </div>
        <button data-testid="change-password-btn" disabled={busy || !cur || !nxt || !confirm} onClick={savePassword}
          className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
          <FloppyDisk size={14} /> {busy ? a.updating : a.updatePassword}
        </button>
      </div>
    </Card>
  );
}

function TwoFactor() {
  const { account: a, cancel } = useAdminLabels();
  const { user, refreshUser } = useAuth();
  const location = useLocation();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["auth-me"], queryFn: () => api.get("/auth/me").then(r => r.data) });
  const enabled = !!me.data?.totp_enabled;
  const [setup, setSetup] = useState(null);
  const [setupPassword, setSetupPassword] = useState("");
  const [code, setCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [busy, setBusy] = useState(false);
  const mandatory = !!user?.two_fa_mandatory;

  async function startSetup() {
    if (!setupPassword.trim()) {
      toast.error("Enter your current password to begin 2FA setup");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post("/auth/2fa/setup", { password: setupPassword });
      setSetup(r.data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }

  async function verify() {
    setBusy(true);
    try {
      await api.post("/auth/2fa/verify", { code });
      toast.success(a.twoFactorEnabledToast);
      setSetup(null); setCode("");
      qc.invalidateQueries({ queryKey: ["auth-me"] });
      await refreshUser();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }

  async function disable2fa() {
    setBusy(true);
    try {
      await api.post("/auth/2fa/disable", { code: disableCode });
      toast.success(a.twoFactorDisabledToast);
      setDisableCode("");
      qc.invalidateQueries({ queryKey: ["auth-me"] });
      await refreshUser();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }

  const qrUrl = setup ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(setup.otpauth_uri)}` : null;

  if (!["Admin", "CPC", "Viewer"].includes(user?.role || "")) {
    return null;
  }

  return (
    <Card
      title={mandatory ? a.twoFactorTitle : a.twoFactorTitleOptional}
      subtitle={
        enabled
          ? (mandatory ? a.twoFactorEnabled : a.twoFactorOptionalEnabled)
          : mandatory
            ? a.twoFactorRequired
            : a.twoFactorOptionalSubtitle
      }
      action={enabled
        ? <span className="inline-flex items-center gap-1.5 text-emerald-700 text-xs"><ShieldCheck size={16} weight="fill" /> {a.twoFactorActive}</span>
        : <span className="inline-flex items-center gap-1.5 text-amber-700 text-xs"><ShieldWarning size={16} weight="fill" /> {a.twoFactorNotConfigured}</span>
      }
    >
      <div className="p-4 space-y-3">
        {location.state?.setup2fa && !enabled && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-sm p-3">
            {a.twoFactorSetupPrompt}
          </p>
        )}
        {!enabled && !setup && (
          <div className="space-y-2">
            <input
              type="password"
              value={setupPassword}
              onChange={(e) => setSetupPassword(e.target.value)}
              placeholder="Confirm your password"
              className="w-full max-w-sm px-3 py-2 border border-slate-300 rounded-sm text-sm focus:outline-none focus:border-[#003B73]"
            />
            <button data-testid="2fa-setup-btn" disabled={busy || !setupPassword.trim()} onClick={startSetup}
              className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
              <Key size={14} /> {a.begin2fa}
            </button>
          </div>
        )}
        {setup && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="text-sm space-y-2">
              <p>{a.twoFactorStep1}</p>
              <p>{a.twoFactorStep2}</p>
              <div className="bg-slate-100 rounded-sm p-2 font-mono text-xs break-all border border-slate-200">{setup.secret}</div>
              <p>{a.twoFactorStep3}</p>
              <input
                data-testid="2fa-code-input"
                type="text" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)}
                className="w-32 text-center tracking-[0.4em] font-mono text-lg px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]"
              />
              <div className="flex gap-2">
                <button data-testid="2fa-verify-btn" disabled={busy || code.length !== 6} onClick={verify}
                  className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider">
                  {busy ? a.verifying : a.verifyEnable}
                </button>
                <button onClick={() => setSetup(null)}
                  className="text-slate-600 hover:text-slate-900 text-xs uppercase tracking-wider px-2 py-2">{cancel}</button>
              </div>
            </div>
            <div className="flex items-start justify-center">
              {qrUrl && <img src={qrUrl} alt={a.qrAlt} className="w-44 h-44 border border-slate-200 bg-white p-2 rounded-sm" />}
            </div>
          </div>
        )}
        {enabled && mandatory && (
          <p className="text-sm text-slate-600">
            {a.twoFactorLocked}
          </p>
        )}
        {enabled && !mandatory && (
          <div className="border-t border-slate-200 pt-4 space-y-2">
            <p className="text-sm font-medium text-slate-800">{a.disable2faTitle}</p>
            <p className="text-sm text-slate-600">{a.disable2faPrompt}</p>
            <div className="flex flex-wrap items-center gap-2">
              <input
                data-testid="2fa-disable-code-input"
                type="text"
                maxLength={6}
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                className="w-32 text-center tracking-[0.4em] font-mono text-lg px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]"
              />
              <button
                data-testid="2fa-disable-btn"
                disabled={busy || disableCode.length !== 6}
                onClick={disable2fa}
                className="text-red-700 border border-red-200 hover:bg-red-50 disabled:opacity-50 px-4 py-2 rounded-sm text-sm uppercase tracking-wider"
              >
                {a.disable2fa}
              </button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function parseUa(ua, unknownLabel) {
  if (!ua) return unknownLabel;
  if (ua.includes("Chrome")) return "Chrome browser";
  if (ua.includes("Firefox")) return "Firefox browser";
  if (ua.includes("Safari") && !ua.includes("Chrome")) return "Safari browser";
  return ua.slice(0, 48) + (ua.length > 48 ? "…" : "");
}

function ActiveSessions() {
  const { account: a } = useAdminLabels();
  const qc = useQueryClient();
  const { logout } = useAuth();
  const sessions = useQuery({
    queryKey: ["auth-sessions"],
    queryFn: () => api.get("/auth/sessions").then(r => r.data),
  });
  const [busy, setBusy] = useState(null);

  async function revoke(id, isCurrent) {
    setBusy(id);
    try {
      await api.delete(`/auth/sessions/${id}`);
      toast.success(isCurrent ? a.signedOut : a.sessionRevoked);
      if (isCurrent) {
        await logout();
        return;
      }
      qc.invalidateQueries({ queryKey: ["auth-sessions"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(null);
    }
  }

  async function revokeOthers() {
    setBusy("all");
    try {
      await api.delete("/auth/sessions");
      toast.success(a.othersSignedOut);
      qc.invalidateQueries({ queryKey: ["auth-sessions"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title={a.sessionsTitle} subtitle={a.sessionsSubtitle}>
      <div className="p-4">
        <div className="flex justify-end mb-3">
          <button type="button" disabled={busy === "all"} onClick={revokeOthers}
            className="text-xs uppercase tracking-wider text-[#003B73] hover:underline inline-flex items-center gap-1">
            <SignOut size={14} /> {a.signOutOthers}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="dense-table w-full">
            <thead>
              <tr>
                <th>{a.colDevice}</th>
                <th>{a.colIp}</th>
                <th>{a.colSignedIn}</th>
                <th>{a.colLastActive}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(sessions.data || []).map((s) => (
                <tr key={s.id}>
                  <td>
                    {parseUa(s.user_agent, a.unknownDevice)}
                    {s.is_current && (
                      <span className="ml-2 text-[10px] uppercase bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">{a.thisDevice}</span>
                    )}
                  </td>
                  <td className="font-mono text-xs">{s.ip || "—"}</td>
                  <td className="text-xs">{s.created_at?.slice(0, 16) || "—"}</td>
                  <td className="text-xs">{s.last_seen_at?.slice(0, 16) || "—"}</td>
                  <td>
                    <button type="button" disabled={busy === s.id} onClick={() => revoke(s.id, s.is_current)}
                      className="text-xs uppercase tracking-wider text-red-700 hover:underline">
                      {s.is_current ? a.signOut : a.revoke}
                    </button>
                  </td>
                </tr>
              ))}
              {(sessions.data?.length || 0) === 0 && !sessions.isLoading && (
                <tr><td colSpan={5} className="text-center text-slate-400 py-6">{a.noSessions}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

function AccessibleRagCard() {
  const { account: a } = useAdminLabels();
  const [enabled, setEnabled] = useAccessibleRag();

  return (
    <Card title={a.accessibleRagTitle} subtitle={a.accessibleRagSubtitle}>
      <div className="p-4 flex items-center justify-between gap-4">
        <p className="text-sm text-slate-600">
          {a.accessibleRagDesc}
        </p>
        <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            data-testid="accessible-rag-toggle"
          />
          {a.enableAccessibleRag}
        </label>
      </div>
    </Card>
  );
}

function ApiTokensCard() {
  const { account: a } = useAdminLabels();
  const qc = useQueryClient();
  const tokens = useQuery({
    queryKey: ["api-tokens"],
    queryFn: () => api.get("/admin/api-tokens").then((r) => r.data),
  });
  const [name, setName] = useState("");
  const [created, setCreated] = useState(null);
  const [busy, setBusy] = useState(false);

  async function createToken() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const r = await api.post("/admin/api-tokens", { name: name.trim() });
      setCreated(r.data);
      setName("");
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
      toast.success(a.tokenCreated);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id) {
    if (!window.confirm(a.revokeTokenConfirm)) return;
    try {
      await api.delete(`/admin/api-tokens/${id}`);
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
      toast.success(a.tokenRevoked);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  }

  return (
    <Card title={a.apiTokensTitle} subtitle={a.apiTokensSubtitle}>
      <div className="p-4 space-y-4">
        <div className="flex flex-wrap gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={a.tokenNamePlaceholder}
            className="flex-1 min-w-[200px] px-3 py-2 border border-slate-300 rounded-sm text-sm"
          />
          <button
            disabled={busy || !name.trim()}
            onClick={createToken}
            className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-xs uppercase tracking-wider"
          >
            {a.generateToken}
          </button>
        </div>
        {created?.token && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs p-3 rounded-sm font-mono break-all">
            {a.newTokenOnce(created.token)}
          </div>
        )}
        <table className="dense-table w-full">
          <thead><tr><th>{a.colTokenName}</th><th>{a.colScopes}</th><th>{a.colTokenCreated}</th><th></th></tr></thead>
          <tbody>
            {(tokens.data || []).filter((tok) => tok.active !== false).map((tok) => (
              <tr key={tok.id}>
                <td>{tok.name}</td>
                <td className="text-xs">{(tok.scopes || []).join(", ")}</td>
                <td className="text-xs font-mono">{tok.created_at?.slice(0, 10)}</td>
                <td>
                  <button onClick={() => revoke(tok.id)} className="text-red-600 text-xs uppercase tracking-wider">{a.revoke}</button>
                </td>
              </tr>
            ))}
            {(tokens.data?.length || 0) === 0 && (
              <tr><td colSpan={4} className="text-center text-slate-400 py-4">{a.noTokens}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function AccountSettings() {
  const { account: a } = useAdminLabels();
  const { user } = useAuth();
  return (
    <div className="space-y-6 max-w-3xl">
      {(user?.must_change_password || user?.password_expired) && (
        <div
          data-testid="banner-password-policy"
          className="rounded-sm border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        >
          {user.password_expired ? a.passwordExpiredBanner : a.mustChangeBanner}
        </div>
      )}
      <Card title={a.profile}>
        <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{a.fieldName}</div><div className="font-medium text-slate-800">{user?.name}</div></div>
          <div><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{a.fieldEmail}</div><div className="font-mono text-xs">{user?.email}</div></div>
          <div><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{a.fieldRoleJurisdiction}</div><div className="font-medium text-slate-800">{user?.role}{user?.high_court ? ` · ${user.high_court}` : ""}</div></div>
        </div>
      </Card>
      {!user?.must_change_password && !user?.password_expired && <ChangePasswordCard />}
      <AccessibleRagCard />
      {user?.role === "Admin" && <ApiTokensCard />}
      <TwoFactor />
      <ActiveSessions />
    </div>
  );
}
