import React from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { ShieldWarning } from "@phosphor-icons/react";

/** Global notices for mandatory security policies (2FA setup, password expiry). */
export default function SecurityPolicyBanner() {
  const { t } = useTranslation();
  const { user } = useAuth();
  if (!user) return null;

  if (user.requires_2fa_setup) {
    return (
      <div
        data-testid="banner-requires-2fa"
        className="mb-6 flex items-start gap-3 rounded-sm border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <ShieldWarning size={20} weight="fill" className="mt-0.5 shrink-0 text-amber-600" />
        <div>
          <div className="font-semibold uppercase tracking-wider text-[10px] text-amber-800 mb-1">
            {t("account.twoFactorRequired")}
          </div>
          <p>
            {t("account.twoFactorSetupPrompt")}{" "}
            <Link to="/account" className="font-medium text-[#003B73] underline underline-offset-2">
              {t("nav.account")}
            </Link>
            .
          </p>
        </div>
      </div>
    );
  }

  return null;
}
