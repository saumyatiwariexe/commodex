# Deployment and Operations

> **Skills:** `anthropic-skills:devops-engineer` (Dockerfiles, compose, CI), `engineering:deploy-checklist` (release check), `anthropic-skills:security-reviewer` (dependency and secrets audit).

## 1. Goal
One command brings everything up, and the demo works offline.

## 2. Local run
```
cp .env.example .env
docker compose up --build
```
Services:
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, reads `data/` volume |
| web | 5173 (dev) / 8080 (built) | React app, calls api |

## 3. Containers
- `api`: python:3.11-slim, non-root user, pinned requirements, read-only root filesystem where possible, writable volume only for `data/` and the SQLite file.
- `web`: multi-stage build (node build, then static serve with nginx).
- Pin base image versions. Run `pip-audit` and `npm audit` in CI.

## 4. Data and demo safety
- `data/samples/` holds a small, committed, real or realistic sample plus a precomputed backtest run. `?demo=1` uses it.
- **Do not depend on live MCX during the demo.** Ingest beforehand, snapshot, and demo from the snapshot.
- Back up `data/` and the DuckDB file to a second location before presenting.

## 5. Configuration and secrets
- `.env.example` committed with placeholders only. Real `.env` in `.gitignore`.
- JWT secret supplied through environment or mounted files.

## 6. Hosting (optional)
A single small VM or a free-tier container host is enough: `api` and `web` behind one reverse proxy with HTTPS. Static frontend can also go to any static host if the API is public read-only. Restrict write endpoints by role and keep admin routes off the public internet if possible.

## 7. Release checklist (night before the demo)
- [ ] Fresh clone builds and runs with one command
- [ ] Demo mode works with the network disabled
- [ ] Snapshot hash shown in the UI matches the manifest
- [ ] Backtest run is reproducible: re-running gives identical metrics
- [ ] Look-ahead tests green
- [ ] Hold-out evaluated exactly once, result recorded
- [ ] README has run steps, architecture picture, known limits
- [ ] Slides and a 2-minute backup screen recording

## 8. Runbook for demo day problems
| Problem | Action |
|---------|--------|
| Wi-Fi fails | Run local with demo mode, nothing needs the internet |
| Backend crash | Frontend demo mode with bundled data |
| Question about a number | Open the trade table, show raw rows, then normalization, then costs |
