import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { taskDashboardPath } from "@/lib/taskPermissions";

/** Redirect /task-management to role-appropriate dashboard. */
export default function TaskManagementHub() {
  const { user } = useAuth();
  return <Navigate to={taskDashboardPath(user)} replace />;
}
