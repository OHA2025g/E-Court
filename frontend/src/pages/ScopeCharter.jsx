import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Card from "@/components/Card";
import { toast } from "sonner";
import { CheckCircle, Clock, Scroll, Signature } from "@phosphor-icons/react";

function StatusBadge({ signed, labelSigned, labelPending }) {
  if (signed) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-sm">
        <CheckCircle size={14} weight="fill" /> {labelSigned}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-sm">
      <Clock size={14} /> {labelPending}
    </span>
  );
}

export default function ScopeCharter() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [activeSlot, setActiveSlot] = useState(null);
  const [signerName, setSignerName] = useState(user?.name || "");
  const [affirm, setAffirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const charter = useQuery({
    queryKey: ["scope-charter"],
    queryFn: () => api.get("/scope-charter").then((r) => r.data),
  });

  async function submitSign(slotId) {
    if (!signerName.trim()) {
      toast.error(t("scopeCharter.nameRequired"));
      return;
    }
    if (!affirm) {
      toast.error(t("scopeCharter.affirmRequired"));
      return;
    }
    setBusy(true);
    try {
      const r = await api.post("/scope-charter/sign", {
        slot_id: slotId,
        signer_name: signerName.trim(),
        affirm: true,
      });
      toast.success(r.data.fully_signed ? t("scopeCharter.fullySignedToast") : t("scopeCharter.signedToast"));
      setActiveSlot(null);
      setAffirm(false);
      qc.invalidateQueries({ queryKey: ["scope-charter"] });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  const data = charter.data;
  const docStatus = data?.document_status || "DRAFT";

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Scroll size={28} className="text-[#003B73]" weight="duotone" />
            {t("scopeCharter.title")}
          </h1>
          <p className="text-sm text-slate-500 mt-1">{t("scopeCharter.subtitle")}</p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{t("scopeCharter.version", { version: data?.version || "—" })}</div>
          <div className="mt-1 font-semibold uppercase tracking-wider text-[#003B73]">{docStatus}</div>
        </div>
      </div>

      {data?.fully_signed && (
        <div
          data-testid="scope-charter-signed-banner"
          className="rounded-sm border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
        >
          {t("scopeCharter.completedBanner", { date: (data.completed_at || "").slice(0, 10) || "—" })}
        </div>
      )}

      <Card title={t("scopeCharter.signoffTitle")} subtitle={t("scopeCharter.signoffSubtitle", {
        signed: data?.signed_count ?? 0,
        total: data?.required_count ?? 4,
      })}>
        <div className="p-4 overflow-x-auto">
          <table className="dense-table w-full" data-testid="scope-charter-signoff-table">
            <thead>
              <tr>
                <th>{t("scopeCharter.colRole")}</th>
                <th>{t("scopeCharter.colName")}</th>
                <th>{t("scopeCharter.colDate")}</th>
                <th>{t("scopeCharter.colStatus")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(data?.signoff_slots || []).map((slot) => (
                <tr key={slot.id}>
                  <td>{slot.title}</td>
                  <td>{slot.signoff?.signer_name || "—"}</td>
                  <td className="text-xs font-mono">{slot.signoff?.signed_at?.slice(0, 10) || "—"}</td>
                  <td>
                    <StatusBadge
                      signed={slot.signed}
                      labelSigned={t("scopeCharter.statusSigned")}
                      labelPending={t("scopeCharter.statusPending")}
                    />
                  </td>
                  <td>
                    {slot.can_sign && (
                      <button
                        type="button"
                        data-testid={`scope-charter-sign-${slot.id}`}
                        onClick={() => {
                          setActiveSlot(slot.id);
                          setSignerName(user?.name || "");
                          setAffirm(false);
                        }}
                        className="text-xs uppercase tracking-wider text-[#003B73] hover:underline inline-flex items-center gap-1"
                      >
                        <Signature size={14} /> {t("scopeCharter.signAction")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {activeSlot && (
        <Card title={t("scopeCharter.signModalTitle")}>
          <div className="p-4 space-y-3 max-w-lg">
            <label className="block text-sm">
              <span className="text-[11px] uppercase tracking-[0.2em] text-slate-600 font-medium">{t("scopeCharter.signerName")}</span>
              <input
                data-testid="scope-charter-signer-name"
                value={signerName}
                onChange={(e) => setSignerName(e.target.value)}
                className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-sm"
              />
            </label>
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                data-testid="scope-charter-affirm"
                checked={affirm}
                onChange={(e) => setAffirm(e.target.checked)}
                className="mt-1"
              />
              {t("scopeCharter.affirmLabel")}
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="scope-charter-submit-sign"
                disabled={busy}
                onClick={() => submitSign(activeSlot)}
                className="bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider"
              >
                {busy ? t("scopeCharter.signing") : t("scopeCharter.confirmSign")}
              </button>
              <button
                type="button"
                onClick={() => setActiveSlot(null)}
                className="text-slate-600 text-sm uppercase tracking-wider px-2 py-2"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </Card>
      )}

      <Card title={t("scopeCharter.documentTitle")}>
        <div className="p-4">
          <pre
            data-testid="scope-charter-markdown"
            className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700 dark:text-slate-200 font-sans max-h-[520px] overflow-y-auto border border-slate-200 dark:border-slate-700 rounded-sm p-4 bg-slate-50 dark:bg-slate-900/40"
          >
            {charter.isLoading ? t("common.loading") : data?.markdown}
          </pre>
        </div>
      </Card>
    </div>
  );
}
