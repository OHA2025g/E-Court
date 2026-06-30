# Database backup

This folder contains a **MongoDB dump** of the `pmis_ecourts` database (captured from the running Docker stack).

## Restore (Docker)

With the stack running (`docker compose up -d`):

```bash
docker cp database/mongodump/pmis_ecourts ecourts-pmisv1-mongo-1:/tmp/restore
docker exec ecourts-pmisv1-mongo-1 mongorestore --drop --db pmis_ecourts /tmp/restore
```

Or use the helper script from the project root:

```bash
chmod +x scripts/restore_database.sh
./scripts/restore_database.sh
```

## Contents

- Master data (28 High Courts, components, indicators, KPIs, periods)
- Tracker entries (physical, financial, outcome)
- Users, sessions, audit logs, submissions, tasks, and related collections

**Note:** Demo passwords are defined in `backend/.env.example` and `docker-compose.yml` — change them before production.
