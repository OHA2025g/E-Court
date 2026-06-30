import React from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { taskDashboardPath } from "@/lib/taskPermissions";
import { useTaskLabels } from "@/lib/useTaskLabels";
import { ListChecks, SquaresFour, Scales, ArrowRight } from "@phosphor-icons/react";

export default function AppSelector() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const l = useTaskLabels();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">{l.appSelector.initialising}</div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password || user.password_expired) {
    return <Navigate to="/change-password" replace />;
  }
  if (user.requires_2fa_setup) {
    return <Navigate to="/account" replace state={{ setup2fa: true }} />;
  }

  const taskPath = taskDashboardPath(user);

  return (
    <div className="workspace-page dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 flex flex-col">
      <header className="border-b border-slate-200/80 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur px-6 py-4 flex items-center gap-3 shadow-sm">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#003B73] to-[#0284c7] shadow-md">
          <Scales size={24} className="text-white" weight="duotone" />
        </div>
        <div>
          <div className="font-display text-sm uppercase tracking-[0.18em] text-[#003B73] dark:text-sky-400 font-semibold">eCourts PMIS</div>
          <div className="text-xs text-slate-500">{l.appSelector.signedInAs(user.name, user.role)}</div>
        </div>
      </header>
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-4xl w-full">
          <h1 className="font-display text-2xl md:text-4xl font-bold text-slate-900 dark:text-white text-center mb-3">
            {l.appSelector.chooseWorkspace}
          </h1>
          <p className="text-center text-slate-500 mb-12 text-sm max-w-xl mx-auto leading-relaxed">
            {l.appSelector.subtitle}
          </p>
          <div className="grid md:grid-cols-2 gap-6">
            <button
              type="button"
              data-testid="tile-task-management"
              onClick={() => navigate(taskPath)}
              className="workspace-tile group dark:bg-slate-900 dark:border-slate-700"
            >
              <div className="workspace-tile-icon bg-gradient-to-br from-[#003B73]/15 to-[#003B73]/5 group-hover:from-[#003B73]/25 group-hover:to-[#003B73]/10">
                <ListChecks size={30} className="text-[#003B73]" weight="duotone" />
              </div>
              <h2 className="font-display text-xl font-semibold text-slate-900 dark:text-white">{l.appSelector.taskTitle}</h2>
              <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                {l.appSelector.taskDesc}
              </p>
              <span className="inline-flex items-center gap-1.5 mt-6 text-sm uppercase tracking-wider text-[#003B73] font-semibold">
                {l.appSelector.openTask} <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </span>
            </button>
            <button
              type="button"
              data-testid="tile-application"
              onClick={() => navigate("/dashboard")}
              className="workspace-tile group dark:bg-slate-900 dark:border-slate-700"
            >
              <div className="workspace-tile-icon bg-gradient-to-br from-emerald-500/15 to-teal-500/5 group-hover:from-emerald-500/25 group-hover:to-teal-500/10">
                <SquaresFour size={30} className="text-emerald-700" weight="duotone" />
              </div>
              <h2 className="font-display text-xl font-semibold text-slate-900 dark:text-white">{l.appSelector.appTitle}</h2>
              <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                {l.appSelector.appDesc}
              </p>
              <span className="inline-flex items-center gap-1.5 mt-6 text-sm uppercase tracking-wider text-emerald-700 font-semibold">
                {l.appSelector.openApp} <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </span>
            </button>
          </div>
          <p className="text-center text-xs text-slate-400 mt-10">
            {l.appSelector.directLinks}{" "}
            <Link to="/dashboard" className="text-[#003B73] underline font-medium">/dashboard</Link>
            {" · "}
            <Link to={taskPath} className="text-[#003B73] underline font-medium">{l.appSelector.taskModule}</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
