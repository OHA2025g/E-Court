import { api } from "@/lib/api";

export const taskApi = {
  meta: () => api.get("/tasks/meta").then((r) => r.data),
  list: (params) => api.get("/tasks", { params }).then((r) => r.data),
  get: (id) => api.get(`/tasks/${id}`).then((r) => r.data),
  updateInfo: (id, body) => api.patch(`/tasks/${id}/info`, body).then((r) => r.data),
  create: (body) => api.post("/tasks", body).then((r) => r.data),
  assignLead: (id, userId, remarks) => api.post(`/tasks/${id}/assign-team-lead`, { user_id: userId, remarks }).then((r) => r.data),
  assignMember: (id, userId, remarks) => api.post(`/tasks/${id}/assign-member`, { user_id: userId, remarks }).then((r) => r.data),
  accept: (id) => api.post(`/tasks/${id}/accept`).then((r) => r.data),
  start: (id) => api.post(`/tasks/${id}/start`).then((r) => r.data),
  progress: (id, body) => api.post(`/tasks/${id}/update-progress`, body).then((r) => r.data),
  blocked: (id, reason) => api.post(`/tasks/${id}/mark-blocked`, { reason }).then((r) => r.data),
  evidence: (id, body) => api.post(`/tasks/${id}/upload-evidence`, body).then((r) => r.data),
  submit: (id) => api.post(`/tasks/${id}/submit-approval`).then((r) => r.data),
  verify: (id, body) => api.post(`/tasks/${id}/verify`, body).then((r) => r.data),
  approveClosure: (id, remarks) => api.post(`/tasks/${id}/approve-closure`, { remarks: remarks || "" }).then((r) => r.data),
  rejectClosure: (id, remarks) => api.post(`/tasks/${id}/reject-closure`, { remarks }).then((r) => r.data),
  escalate: (id, reason) => api.post(`/tasks/${id}/escalate`, { reason }).then((r) => r.data),
  comment: (id, text) => api.post(`/tasks/${id}/comments`, { comment_text: text }).then((r) => r.data),
  acceptProposed: (id) => api.post(`/tasks/${id}/accept-proposed`).then((r) => r.data),
  rejectProposed: (id, remarks) => api.post(`/tasks/${id}/reject-proposed`, { remarks }).then((r) => r.data),
  assignableUsers: (role) => api.get("/tasks/assignable-users", { params: { role } }).then((r) => r.data),
  managerDashboard: () => api.get("/tasks/manager/dashboard").then((r) => r.data),
  teamLeadDashboard: () => api.get("/tasks/team-lead/dashboard").then((r) => r.data),
  memberDashboard: () => api.get("/tasks/my/dashboard").then((r) => r.data),
  reportSummary: () => api.get("/tasks/reports/summary").then((r) => r.data),
  exportBlob: (format, filters = {}) =>
    api.get("/tasks/export", { params: { format, ...filters }, responseType: "blob" }),
  bulkAssignLead: (taskIds, userId, remarks) =>
    api.post("/tasks/bulk/assign-team-lead", { task_ids: taskIds, user_id: userId, remarks }).then((r) => r.data),
  bulkAssignMember: (taskIds, userId, remarks) =>
    api.post("/tasks/bulk/assign-member", { task_ids: taskIds, user_id: userId, remarks }).then((r) => r.data),
  bulkCancel: (taskIds, remarks) =>
    api.post("/tasks/bulk/cancel", { task_ids: taskIds, remarks }).then((r) => r.data),
};
