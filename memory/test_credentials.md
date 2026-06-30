# eCourts PMIS — Test Credentials

These are the seeded demo accounts. All credentials are also defined in `/app/backend/.env`.

| Email | Password | Role | Jurisdiction |
| --- | --- | --- | --- |
| `admin@pmis.gov.in` | `Admin@PMIS2026` | Admin | All High Courts |
| `cpc.allahabad@pmis.gov.in` | `Cpc@PMIS2026` | CPC | Allahabad High Court |
| `viewer@pmis.gov.in` | `View@PMIS2026` | Viewer | Read-only, all jurisdictions |

## Auth Endpoints

- `POST /api/auth/login` — body `{ "email": "...", "password": "..." }`
- `POST /api/auth/logout`
- `GET  /api/auth/me`
- `POST /api/auth/refresh`

Tokens are returned in the body as `access_token` and also set as httpOnly cookies. Frontend uses `withCredentials: true`.
