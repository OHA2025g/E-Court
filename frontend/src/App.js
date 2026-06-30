import React from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import ChangePassword from "@/pages/ChangePassword";
import PublicProgress from "@/pages/PublicProgress";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import PhysicalTracker from "@/pages/PhysicalTracker";
import FinancialTracker from "@/pages/FinancialTracker";
import OutcomeTracker from "@/pages/OutcomeTracker";
import Reports from "@/pages/Reports";
import MasterData from "@/pages/MasterData";
import AuditLogs from "@/pages/AuditLogs";
import PmuTasks from "@/pages/PmuTasks";
import DprDeliverables from "@/pages/DprDeliverables";
import IjurisIntegration from "@/pages/IjurisIntegration";
import UserManagement from "@/pages/UserManagement";
import AccountSettings from "@/pages/AccountSettings";
import AdminBackup from "@/pages/AdminBackup";
import Submissions from "@/pages/Submissions";
import Schedules from "@/pages/Schedules";
import AppSelector from "@/pages/AppSelector";
import ScopeCharter from "@/pages/ScopeCharter";
import TaskManagementLayout from "@/components/task-management/TaskManagementLayout";
import TaskManagementHub from "@/pages/task-management/TaskManagementHub";
import ManagerDashboard from "@/pages/task-management/ManagerDashboard";
import TeamLeadDashboard from "@/pages/task-management/TeamLeadDashboard";
import MemberDashboard from "@/pages/task-management/MemberDashboard";
import TaskListPage from "@/pages/task-management/TaskListPage";
import TaskDetailPage from "@/pages/task-management/TaskDetailPage";
import TaskReportsPage from "@/pages/task-management/TaskReportsPage";
import TaskAdminConfig from "@/pages/task-management/TaskAdminConfig";
import AuditorDashboard from "@/pages/task-management/AuditorDashboard";

const ALL_ROLES = ["Admin", "CPC", "Viewer"];
const ADMIN_VIEWER = ["Admin", "Viewer"];
const ADMIN_ONLY = ["Admin"];

function AuthGate({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        Initialising PMIS…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        Initialising PMIS…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password || user.password_expired) {
    return <Navigate to="/change-password" replace />;
  }
  if (user.requires_2fa_setup && !location.pathname.startsWith("/account")) {
    return <Navigate to="/account" replace state={{ setup2fa: true }} />;
  }
  return children;
}

function HomeRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/app-selector" replace />;
  return <PublicProgress />;
}

function FallbackRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user ? "/app-selector" : "/public"} replace />;
}

function RoleGuard({ allow, children }) {
  const { user } = useAuth();
  if (!user || !allow.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute />} />
      <Route path="/public" element={<PublicProgress />} />
      <Route path="/login" element={<Login />} />
      <Route
        path="/change-password"
        element={
          <AuthGate>
            <ChangePassword />
          </AuthGate>
        }
      />
      <Route
        path="/app-selector"
        element={
          <Protected>
            <AppSelector />
          </Protected>
        }
      />
      <Route
        path="/task-management"
        element={
          <Protected>
            <TaskManagementLayout />
          </Protected>
        }
      >
        <Route index element={<TaskManagementHub />} />
        <Route path="manager" element={<ManagerDashboard />} />
        <Route path="team-lead" element={<TeamLeadDashboard />} />
        <Route path="my-tasks" element={<MemberDashboard />} />
        <Route path="auditor" element={<AuditorDashboard />} />
        <Route path="tasks" element={<TaskListPage />} />
        <Route path="tasks/:id" element={<TaskDetailPage />} />
        <Route path="reports" element={<TaskReportsPage />} />
        <Route path="admin" element={<RoleGuard allow={ADMIN_ONLY}><TaskAdminConfig /></RoleGuard>} />
      </Route>
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="dashboard" element={<RoleGuard allow={ALL_ROLES}><Dashboard /></RoleGuard>} />
        <Route path="physical" element={<RoleGuard allow={ALL_ROLES}><PhysicalTracker /></RoleGuard>} />
        <Route path="financial" element={<RoleGuard allow={ALL_ROLES}><FinancialTracker /></RoleGuard>} />
        <Route path="outcome" element={<RoleGuard allow={ALL_ROLES}><OutcomeTracker /></RoleGuard>} />
        <Route path="submissions" element={<RoleGuard allow={ALL_ROLES}><Submissions /></RoleGuard>} />
        <Route path="reports" element={<RoleGuard allow={ALL_ROLES}><Reports /></RoleGuard>} />
        <Route path="master" element={<RoleGuard allow={ADMIN_VIEWER}><MasterData /></RoleGuard>} />
        <Route path="pmu-tasks" element={<RoleGuard allow={ADMIN_VIEWER}><PmuTasks /></RoleGuard>} />
        <Route path="dpr" element={<RoleGuard allow={ADMIN_VIEWER}><DprDeliverables /></RoleGuard>} />
        <Route path="ijuris" element={<RoleGuard allow={ADMIN_ONLY}><IjurisIntegration /></RoleGuard>} />
        <Route path="users" element={<RoleGuard allow={ADMIN_ONLY}><UserManagement /></RoleGuard>} />
        <Route path="backup" element={<RoleGuard allow={ADMIN_ONLY}><AdminBackup /></RoleGuard>} />
        <Route path="schedules" element={<RoleGuard allow={ADMIN_ONLY}><Schedules /></RoleGuard>} />
        <Route path="audit" element={<RoleGuard allow={ALL_ROLES}><AuditLogs /></RoleGuard>} />
        <Route path="scope-charter" element={<RoleGuard allow={ALL_ROLES}><ScopeCharter /></RoleGuard>} />
        <Route path="account" element={<RoleGuard allow={ALL_ROLES}><AccountSettings /></RoleGuard>} />
      </Route>
      <Route path="*" element={<FallbackRoute />} />
    </Routes>
  );
}
