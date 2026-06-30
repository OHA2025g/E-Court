export const PASSWORD_POLICY_HINT =
  "Minimum 12 characters with uppercase, lowercase, digit and special character. Cannot reuse your last 5 passwords.";

export function validatePasswordClient(password) {
  if (password.length < 12) return "Password must be at least 12 characters";
  if (!/[A-Z]/.test(password)) return "Password must include an uppercase letter";
  if (!/[a-z]/.test(password)) return "Password must include a lowercase letter";
  if (!/\d/.test(password)) return "Password must include a digit";
  if (!/[!@#$%^&*(),.?":{}|<>_\-+=[\]\\;/`~]/.test(password)) {
    return "Password must include a special character";
  }
  return null;
}
