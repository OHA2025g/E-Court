/** Stable React Query scope so role/HC-scoped API data is never reused across users. */
export function authQueryScope(user) {
  if (!user || user === false) return "anon";
  const id = user.id || user.email || "unknown";
  const role = user.role || "Viewer";
  const hc = user.high_court || "";
  return `${id}|${role}|${hc}`;
}
