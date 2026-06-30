/** Task Management role mapping — aligns PMIS roles with task workflow roles. */

const TASK_ROLE_ALIASES = {
  manager: "manager",
  team_lead: "team_lead",
  teamlead: "team_lead",
  lead: "team_lead",
  member: "team_member",
  team_member: "team_member",
  admin: "admin",
  auditor: "auditor",
};

const PMIS_DEFAULT = {
  Admin: "manager",
  CPC: "team_lead",
  Viewer: "auditor",
};

export function resolveTaskRole(user) {
  if (!user) return "team_member";
  const explicit = (user.task_role || user.resolved_task_role || "").toLowerCase();
  if (TASK_ROLE_ALIASES[explicit]) return TASK_ROLE_ALIASES[explicit];
  if (user.role === "Admin") return "manager";
  return PMIS_DEFAULT[user.role] || "team_member";
}

export function taskDashboardPath(user) {
  const role = resolveTaskRole(user);
  if (role === "manager" || role === "admin") return "/task-management/manager";
  if (role === "team_lead") return "/task-management/team-lead";
  if (role === "auditor") return "/task-management/auditor";
  return "/task-management/my-tasks";
}

export function taskPermissions(user) {
  const role = resolveTaskRole(user);
  const pmisAdmin = user?.role === "Admin";
  return {
    taskRole: role,
    canViewAll: ["manager", "admin", "auditor"].includes(role) || pmisAdmin,
    canCreate: ["manager", "team_lead", "team_member", "admin"].includes(role) || pmisAdmin,
    canAssignLead: ["manager", "admin"].includes(role) || pmisAdmin,
    canAssignMember: ["manager", "team_lead", "admin"].includes(role) || pmisAdmin,
    canVerify: ["team_lead", "manager", "admin"].includes(role) || pmisAdmin,
    canApproveClosure: ["manager", "admin"].includes(role) || pmisAdmin,
    canAcceptTask: role === "team_member",
    canEscalate: ["team_lead", "team_member", "manager", "admin"].includes(role) || pmisAdmin,
    canMarkBlocked: !["auditor"].includes(role) || pmisAdmin,
    canBulkCancel: ["manager", "admin"].includes(role) || pmisAdmin,
    readOnly: role === "auditor" && !pmisAdmin,
  };
}

export default resolveTaskRole;
