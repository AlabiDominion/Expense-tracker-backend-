# CloudBerth Pilot deployment

## Configuration saved on 21 October 2026

Frontend (`AlabiDominion/Expense-Tracker`, master):
- Install: `npm ci`
- Build: `npm run build`
- Start override: empty (Railpack supplies the static server)
- Static output: `dist`
- Port: `8080`
- Variable: `VITE_API_URL=https://expense-tracker-backend.pilot.cloudberth.com`

Backend (`AlabiDominion/Expense-tracker-backend-`, master):
- Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`
- Port: `8080`
- Saved variables: `COOKIE_SECURE`, `FRONTEND_URL`, `CORS_ORIGINS` as in `production.env.example`.
- DATABASE_URL is still missing. Do not point it at the existing `cloudberth` schema.

## Remaining steps

1. Connect to MySQL as an administrator on the hosting server. The Pilot SQL console runs as `admin@cloudberth`, which cannot create other schemas. Both external database endpoints timed out from the development computer.
2. Run `mysql.sql`, choosing your own strong application password first. This creates a separate schema and schema-limited user on the existing MySQL instance. Do not change the service's MYSQL_DATABASE/MYSQL_USER variables; existing applications use those.
3. Add DATABASE_URL to the backend's variables using the internal database hostname, port 3306, and the new application user's credentials. Never use the root password for the application.
4. Commit and push the current frontend and backend changes to their master branches. Latest private-account and KPI changes were still uncommitted during inspection; the October 20 build contains older code.
5. Redeploy the backend, confirm `/health` returns status ok, then redeploy the frontend. The backend start command runs Alembic migrations in the new schema.
6. Check signup, login, logout, transactions, report balances, statement preview, and refreshing `/overview` directly. Verify two accounts cannot see each other's records.

Production starts with an empty database. Local financial records and credentials have not been uploaded. The in-browser guest demo remains available. Configure Zoho SMTP before relying on password-reset email.

The two original failures were `/bin/bash: dist: command not found` (frontend) and no detected start command followed by exit code 0 (backend).
