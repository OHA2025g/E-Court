import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { DownloadSimple, X, WifiSlash } from "@phosphor-icons/react";

const DISMISS_KEY = "pmis-pwa-install-dismissed";

export function OfflineBanner() {
  const { t } = useTranslation();
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="mb-4 rounded-sm border border-slate-400 bg-slate-800 text-white px-4 py-2 text-sm flex items-center gap-2"
      data-testid="offline-banner"
    >
      <WifiSlash size={18} aria-hidden="true" />
      {t("pwa.offline")}
    </div>
  );
}

export default function PwaInstallPrompt() {
  const { t } = useTranslation();
  const [deferred, setDeferred] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    function onPrompt(e) {
      e.preventDefault();
      setDeferred(e);
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (!deferred || dismissed) return null;

  async function install() {
    deferred.prompt();
    await deferred.userChoice.catch(() => undefined);
    setDeferred(null);
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  function dismiss() {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  return (
    <div
      className="mb-4 rounded-sm border border-[#003B73]/30 bg-sky-50 dark:bg-sky-950/40 px-4 py-3 text-sm text-slate-800 dark:text-slate-100 flex flex-wrap items-center justify-between gap-3"
      data-testid="pwa-install-prompt"
    >
      <div className="flex items-start gap-2">
        <DownloadSimple size={20} className="text-[#003B73] shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <p className="font-semibold">{t("pwa.installTitle")}</p>
          <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">{t("pwa.installBody")}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={install}
          className="bg-[#003B73] hover:bg-[#002B54] text-white px-3 py-1.5 rounded-sm text-xs uppercase tracking-wider"
        >
          {t("pwa.installAction")}
        </button>
        <button
          type="button"
          onClick={dismiss}
          className="p-1.5 text-slate-500 hover:text-slate-700"
          aria-label={t("common.cancel")}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
