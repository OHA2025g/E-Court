import React from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { setStoredLang, SUPPORTED_LANGS } from "@/lib/i18n";
import { TID } from "@/lib/testIds";
import {
  House, GridFour, CurrencyInr, Target, ChartBar,
  Database, ClipboardText, Notebook, PlugCharging, UsersThree,
  SignOut, Scales, UserCircle, FloppyDisk, PaperPlaneTilt, Clock, Scroll,
  Moon, Sun, Globe,
} from "@phosphor-icons/react";
import NotificationBell from "@/components/NotificationBell";
import SecurityPolicyBanner from "@/components/SecurityPolicyBanner";
import PwaInstallPrompt, { OfflineBanner } from "@/components/PwaInstallPrompt";

const NAV = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: House, test: TID.navDashboard, roles: ["Admin","CPC","Viewer"] },
  { to: "/physical", labelKey: "nav.physical", icon: GridFour, test: TID.navPhysical, roles: ["Admin","CPC","Viewer"] },
  { to: "/financial", labelKey: "nav.financial", icon: CurrencyInr, test: TID.navFinancial, roles: ["Admin","CPC","Viewer"] },
  { to: "/outcome", labelKey: "nav.outcome", icon: Target, test: TID.navOutcome, roles: ["Admin","CPC","Viewer"] },
  { to: "/submissions", labelKey: "nav.submissions", icon: PaperPlaneTilt, test: "nav-submissions", roles: ["Admin","CPC","Viewer"] },
  { to: "/reports", labelKey: "nav.reports", icon: ChartBar, test: TID.navReports, roles: ["Admin","CPC","Viewer"] },
  { to: "/master", labelKey: "nav.master", icon: Database, test: TID.navMaster, roles: ["Admin","Viewer"] },
  { to: "/pmu-tasks", labelKey: "nav.pmu", icon: ClipboardText, test: TID.navPmu, roles: ["Admin","Viewer"] },
  { to: "/dpr", labelKey: "nav.dpr", icon: Notebook, test: TID.navDpr, roles: ["Admin","Viewer"] },
  { to: "/ijuris", labelKey: "nav.ijuris", icon: PlugCharging, test: TID.navIjuris, roles: ["Admin"] },
  { to: "/users", labelKey: "nav.users", icon: UsersThree, test: TID.navUsers, roles: ["Admin"] },
  { to: "/backup", labelKey: "nav.backup", icon: FloppyDisk, test: "nav-backup", roles: ["Admin"] },
  { to: "/schedules", labelKey: "nav.schedules", icon: Clock, test: "nav-schedules", roles: ["Admin"] },
  { to: "/audit", labelKey: "nav.audit", icon: ClipboardText, test: TID.navAudit, roles: ["Admin","CPC","Viewer"] },
  { to: "/scope-charter", labelKey: "nav.scopeCharter", icon: Scroll, test: "nav-scope-charter", roles: ["Admin","CPC","Viewer"] },
  { to: "/account", labelKey: "nav.account", icon: UserCircle, test: "nav-account", roles: ["Admin","CPC","Viewer"] },
];

function Sidebar() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const items = NAV.filter(n => n.roles.includes(user?.role));
  return (
    <aside data-testid={TID.sidebar} aria-label={t("nav.mainNav")} className="app-sidebar">
      <div className="app-sidebar-brand">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 shadow-lg shadow-amber-900/30">
            <Scales size={22} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-white font-display font-bold text-base leading-tight">{t("app.title")}</div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400">{t("app.subtitle")}</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {items.map((n) => {
          const Icon = n.icon;
          const label = n.labelKey ? t(n.labelKey) : n.label;
          return (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.test}
              className={({ isActive }) => `app-nav-link ${isActive ? "app-nav-link-active" : ""}`}
            >
              <Icon size={18} weight="duotone" />
              <span>{label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-white/10 p-4 m-3 mt-0 rounded-xl bg-white/5" data-testid={TID.userBadge}>
        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400 mb-1">{t("nav.signedIn")}</div>
        <div className="text-sm text-white font-semibold leading-tight truncate">{user?.name}</div>
        <div className="text-xs text-slate-400 truncate mt-0.5">{user?.email}</div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 bg-amber-400/20 text-amber-300 rounded-full border border-amber-400/30">
            {user?.role}
          </span>
          {user?.high_court && (
            <span className="text-[10px] text-slate-400 truncate">{user.high_court}</span>
          )}
        </div>
        <button
          data-testid={TID.logoutBtn}
          onClick={logout}
          className="mt-3 w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/15 text-slate-200 text-xs uppercase tracking-wider py-2 rounded-lg transition-colors border border-white/10"
        >
          <SignOut size={14} /> {t("nav.signOut")}
        </button>
      </div>
    </aside>
  );
}

function HeaderControls() {
  const { t, i18n } = useTranslation();
  const { dark, toggleTheme } = useTheme();

  function changeLang(lng) {
    setStoredLang(lng);
    i18n.changeLanguage(lng);
  }

  const langValue = SUPPORTED_LANGS.find((l) => i18n.language?.startsWith(l.code))?.code || "en";

  return (
    <div className="flex items-center gap-2 shrink-0">
      <label className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
        <Globe size={16} className="text-slate-500" aria-hidden="true" />
        <select
          value={langValue}
          onChange={(e) => changeLang(e.target.value)}
          className="app-control-select max-w-[4.5rem] dark:bg-slate-800 dark:border-slate-600 dark:text-slate-200"
          aria-label={t("common.language")}
        >
          {SUPPORTED_LANGS.map((l) => (
            <option key={l.code} value={l.code}>{l.label}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={toggleTheme}
        className="app-control-btn dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
        title={dark ? t("common.lightMode") : t("common.darkMode")}
        aria-label={dark ? t("common.lightMode") : t("common.darkMode")}
        data-testid="theme-toggle"
      >
        {dark ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <NotificationBell />
    </div>
  );
}

export default function Layout() {
  const loc = useLocation();
  const { t } = useTranslation();
  const navItem = NAV.find((n) => loc.pathname.startsWith(n.to));
  const displayPage = navItem?.labelKey ? t(navItem.labelKey) : (navItem?.label || "PMIS");

  return (
    <div className="flex app-shell rtl:flex-row-reverse">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:start-2 focus:bg-[#003B73] focus:text-white focus:px-4 focus:py-2 focus:rounded-sm"
      >
        {t("common.skipToContent")}
      </a>
      <Sidebar />
      <main id="main-content" tabIndex={-1} className="app-main dark:bg-slate-900 outline-none">
        <div className="app-topbar-accent" aria-hidden="true" />
        <header className="app-topbar dark:bg-slate-950 dark:border-slate-800">
          <div>
            <div className="app-page-eyebrow">eCourts Phase III · Project Monitoring</div>
            <h1 className="app-page-title">{displayPage}</h1>
          </div>
          <HeaderControls />
        </header>
        <div className="app-content dark:bg-slate-900">
          <OfflineBanner />
          <PwaInstallPrompt />
          <SecurityPolicyBanner />
          <Outlet />
        </div>
      </main>
    </div>
  );
}
