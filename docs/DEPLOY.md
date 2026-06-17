# Deploying CareNav to Render

CareNav deploys as three Render resources defined in [`render.yaml`](../render.yaml):

| Resource | Type | Serves |
|---|---|---|
| `carenav-db` | Managed Postgres 16 (pgvector) | Members, claims, KB corpus + embeddings |
| `carenav-api` | Docker web service | FastAPI turn endpoint (`carenav.api.app:app`) |
| `carenav-frontend` | Static site | React chat UI (Vite build) |

The app's `init_schema()` creates the pgvector extension and all tables, so the
managed DB needs no manual migration — but it **does** need data, and the
`data_artifacts/` corpus (1.7 GB) is gitignored. Seed the managed DB once from your
local DB rather than regenerating Synthea/NPPES in the cloud.

## 1. Provision

1. Push `main` to GitHub (this repo's `origin`).
2. Render dashboard → **New + → Blueprint** → select this repo.
3. Render reads `render.yaml` and provisions all three resources.
4. When prompted, fill the `sync: false` secrets:
   - `MISTRAL_API_KEY`, `FIREWORKS_API_KEY`, `FIREWORKS_ACCOUNT_ID`, `PII_MODEL` —
     copy from your local `.env`.
   - `carenav-api → CORS_ORIGINS` — set to the frontend URL once known
     (e.g. `https://carenav-frontend.onrender.com`).
   - `carenav-frontend → VITE_API_BASE_URL` — set to the API URL
     (e.g. `https://carenav-api.onrender.com`). This is baked at build time, so a
     change requires a redeploy of the frontend.

## 2. Seed the managed database (one time)

From the machine running the populated local DB (docker-compose Postgres on 5433):

```bash
# Dump the local DB (schema + data). pgvector types dump/restore cleanly.
pg_dump "postgresql://carenav:carenav@localhost:5433/carenav" \
  --no-owner --no-privileges -Fc -f carenav.dump

# Restore into the Render DB. Use the External Database URL from the Render
# dashboard (carenav-db → Connect → External). It enables pgvector automatically,
# but if a "type vector does not exist" error appears, run once:
#   psql "<external-url>" -c 'CREATE EXTENSION IF NOT EXISTS vector;'
pg_restore --no-owner --no-privileges -d "<external-database-url>" carenav.dump
```

Verify row counts match local:

```bash
psql "<external-database-url>" -c \
  "select (select count(*) from members) members,
          (select count(*) from kb_chunks) kb_chunks;"
```

## 3. Smoke-test

```bash
curl https://carenav-api.onrender.com/health          # -> {"status":"ok"}
curl https://carenav-api.onrender.com/members | head  # -> member summaries
```

Then open the frontend URL and send a question. If the browser console shows a CORS
error, confirm `carenav-api → CORS_ORIGINS` exactly matches the frontend origin
(scheme + host, no trailing slash) and redeploy the API.

## Notes

- The Docker `CMD` binds `--port ${PORT:-8000}`; Render injects `$PORT`.
- `DATABASE_URL` from Render arrives as `postgresql://…`; `get_engine()` rewrites it
  to the `postgresql+psycopg://` driver, so no manual editing is needed.
- To redeploy after code changes: push to `main` (autoDeploy is on for both services).
