import React, { useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api, formatApiError, getApiErrorCode, BACKEND_URL } from "@/lib/api";
import { TID } from "@/lib/testIds";
import { Scales } from "@phosphor-icons/react";

export default function Login() {
  const { t } = useTranslation();
  const { user, loading, login } = useAuth();
  const ssoStatus = useQuery({
    queryKey: ["public-sso"],
    queryFn: () => fetch(`${BACKEND_URL}/api/public/sso`).then((r) => r.json()),
    staleTime: 300_000,
  });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needs2fa, setNeeds2fa] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lockNotice, setLockNotice] = useState(null);
  const [captcha, setCaptcha] = useState(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  if (loading) return null;
  if (user) {
    if (user.must_change_password || user.password_expired) {
      return <Navigate to="/change-password" replace />;
    }
    return <Navigate to="/app-selector" replace />;
  }

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setLockNotice(null);
    try {
      const r = await login(
        email,
        password,
        totpCode || undefined,
        captcha?.captcha_id || captcha?.id,
        captchaAnswer || undefined,
      );
      if (r?.requires_2fa) {
        setNeeds2fa(true);
        return;
      }
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 423) {
        setLockNotice(typeof detail === "string" ? detail : "Account locked.");
      } else if (getApiErrorCode(detail) === "requires_captcha" || detail?.captcha_id) {
        setCaptcha({ captcha_id: detail.captcha_id, image_svg: detail.image_svg });
        setCaptchaAnswer("");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function refreshCaptcha() {
    try {
      const r = await api.get("/auth/captcha");
      setCaptcha(r.data);
      setCaptchaAnswer("");
    } catch (e) {
      /* ignore */
    }
  }

  return (
    <div className="login-page grid grid-cols-1 md:grid-cols-2 bg-slate-100">
      <div className="hidden md:flex flex-col justify-between login-bg text-white p-12 h-full">
        <div>
          <div className="flex items-center gap-2">
            <Scales size={28} weight="fill" className="text-amber-300" />
            <span className="font-display font-bold text-xl">eCourts PMIS</span>
          </div>
          <div className="text-[10px] uppercase tracking-[0.3em] text-slate-300 mt-1">
            Phase III · Project Monitoring
          </div>
        </div>
        <div className="max-w-md">
          <div className="text-[10px] uppercase tracking-[0.25em] text-amber-300 mb-3">
            Department of Justice · PMU · e-Committee
          </div>
          <h2 className="font-display text-3xl sm:text-4xl font-bold leading-tight">
            A single source of truth for eCourts Phase III progress across all 28 High Courts.
          </h2>
          <p className="text-sm text-slate-300 mt-4 leading-relaxed">
            Capture, validate, monitor and report Physical, Financial and Outcome progress
            with role-based access, audit-logged data and configurable RAG thresholds.
          </p>
        </div>
        <div className="text-[10px] uppercase tracking-[0.25em] text-slate-600">
          Government of India · 17 Sanctioned Components · 19 Outcome Subjects
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12 bg-gradient-to-br from-slate-50 via-white to-blue-50 h-full">
        <form
          onSubmit={onSubmit}
          data-testid={TID.loginForm}
          className="login-form-card"
        >
          <div className="text-[10px] uppercase tracking-[0.3em] text-slate-500 mb-1">{t("login.secureLogin")}</div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 mb-2">
            {t("login.title")}
          </h1>
          <p className="text-sm text-slate-500 mb-8">
            {t("login.subtitle")}
          </p>

          {ssoStatus.data?.enabled && (
            <>
              <a
                href={`${BACKEND_URL}/api/sso/login`}
                data-testid="login-sso-btn"
                className="mb-4 w-full inline-flex items-center justify-center gap-2 rounded-lg border-2 border-[#003B73] text-[#003B73] hover:bg-sky-50 py-3 font-semibold uppercase tracking-wider text-sm transition-colors"
              >
                {t("login.ssoSignIn")}
              </a>
              <p className="text-center text-[10px] uppercase tracking-wider text-slate-400 mb-6">{t("login.ssoDivider")}</p>
            </>
          )}

          <label className="block mb-4">
            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{t("login.email")}</span>
            <input
              data-testid={TID.loginEmail}
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="app-input mt-1"
            />
          </label>
          <label className="block mb-6">
            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{t("login.password")}</span>
            <input
              data-testid={TID.loginPassword}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="app-input mt-1"
            />
          </label>
          {captcha && (
            <div className="mb-6 p-3 bg-slate-50 border border-slate-200 rounded-sm">
              <div className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium mb-2">
                Security Check
              </div>
              <div
                className="mb-2"
              >
                <img
                  src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(captcha.image_svg)}`}
                  alt="Security check"
                  className="block max-w-full h-auto"
                />
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  inputMode="numeric"
                  value={captchaAnswer}
                  onChange={(e) => setCaptchaAnswer(e.target.value)}
                  placeholder="Answer"
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-sm focus:outline-none focus:border-[#003B73]"
                />
                <button type="button" onClick={refreshCaptcha}
                  className="text-xs uppercase tracking-wider text-[#003B73] px-2">
                  New
                </button>
              </div>
            </div>
          )}
          {needs2fa && (
            <label className="block mb-6">
              <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">2FA Code</span>
              <input
                data-testid="login-totp-input"
                type="text" inputMode="numeric" maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="6-digit code"
                className="app-input mt-1 font-mono tracking-[0.4em] text-center"
                autoFocus
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Enter the 6-digit code from your authenticator app</span>
            </label>
          )}
          <button
            data-testid={TID.loginSubmit}
            type="submit"
            disabled={submitting}
            className="w-full app-btn-primary py-3 mt-2"
          >
            {submitting ? t("login.signingIn") : t("login.signIn")}
          </button>

          {lockNotice && (
            <div data-testid="login-locked-notice" className="mt-4 flex items-start gap-2 bg-red-50 border border-red-200 text-red-800 text-xs p-3 rounded-sm">
              <span className="w-2 h-2 rounded-full bg-red-500 mt-1.5 shrink-0" />
              <div>
                <div className="font-semibold uppercase tracking-wider text-[10px] mb-0.5">Account temporarily locked</div>
                <div>{lockNotice}</div>
                <div className="text-red-600 mt-1 text-[11px]">If this persists, contact your DoJ/PMU admin for an emergency password reset.</div>
              </div>
            </div>
          )}

          {process.env.REACT_APP_SHOW_DEMO === "true" && (
          <div className="mt-8 border-t border-slate-100 pt-4 text-xs text-slate-500">
            <div className="font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">Demo accounts</div>
            <ul className="space-y-1">
              <li><span className="font-mono">admin@pmis.gov.in</span> · Admin · DoJ/PMU</li>
              <li><span className="font-mono">cpc.allahabad@pmis.gov.in</span> · CPC · Allahabad HC</li>
              <li><span className="font-mono">viewer@pmis.gov.in</span> · Viewer · e-Committee</li>
            </ul>
            <div className="mt-2 text-[10px] text-slate-600">Passwords delivered via DoJ secure channel.</div>
          </div>
          )}
        </form>
      </div>
    </div>
  );
}
