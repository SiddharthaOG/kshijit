# Kshitij — Flood Risk Decision-Support Prototype

**Milestone M0: Repository and Geospatial Foundation** — ✅ Complete

**Milestone M1.1: Synthetic-Terrain Flood-Connectivity Core** — ✅ Complete

**Status:** M0 and M1.1 implemented and tested

---

## Project Overview

Kshitij is a prototype that helps a human operator see which areas may flood and which roads may be cut, with graduated, human-confirmed alert levels. It combines terrain, rainfall and road data, shows how fresh each input is and how uncertain the result is, and keeps working (in a reduced mode) when a data feed fails.

> **⚠️ This application is for simulation and research purposes only—not for operational safety use.**
> It never sends real alerts and does not replace official forecasts from agencies such as IMD and CWC.

For this milestone, the goal is to establish the development environment and prove that the geospatial database stack works.

---

## Prerequisites

- [Docker](https://docs.docker.com/engine/install/) (with Docker Compose v2+)
- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-git)
- [QGIS](https://qgis.org/en/site/forusers/download.html) (for later visual inspection of PostGIS data)

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd kshitij
```

### 2. Copy environment variables

```bash
cp .env.example .env
```

Edit `.env` as needed. The default values are suitable for local development.

### 3. Start the services

```bash
docker compose up -d
```

This starts the PostgreSQL+PostGIS service (`db`) in detached mode.

### 4. Wait for the database to be ready

```bash
docker compose logs -f db
```

Wait until you see `ready` in the output (the healthcheck retries for up to 25 seconds).

### 5. Run the smoke test

```bash
docker compose up --abort-on-container-exit smoke-test
```

Or, run directly against the running container:

```bash
docker compose exec db sh -c "python /app/smoke_test.py"
```

### 6. Inspect with QGIS (optional, for later milestones)

Connect QGIS to the local PostGIS database:
- Host: `localhost` (or `127.0.0.1`)
- Port: `5432`
- Database: `kshitij_db`
- User: `kshitij_dev`
- Password: (whatever you set in `.env`)
- Check "Enable PostGIS connections"

---

## Environment Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
| -------- | -------- | ----------- |
| `POSTGRES_USER` | `kshitij_dev` | Database superuser |
| `POSTGRES_PASSWORD` | `dev_password_must_change` | Database password |
| `POSTGRES_DB` | `kshitij_db` | Database name |
| `POSTGRES_HOST` | `db` | Docker Compose service name |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `DEBUG` | `True` | Django / app debug mode |
| `SECRET_KEY` | `dev_secret_key_replace_me` | Secret key for development |

---

## Commands Reference

| Action | Command |
| -------- | -------- |
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f` |
| Rebuild images | `docker compose build` |
| Run smoke test | `docker compose up --abort-on-container-exit smoke-test` |
| Connect QGIS | See README "Connect QGIS" section |

---

## Troubleshooting

| Issue | Resolution |
| -------- | ----------- |
| `db` service won't start | Check Docker resources; ensure no other service occupies port 5432 |
| Smoke test times out | Verify `.env` values; check `docker compose logs db` for startup errors |
| QGIS can't connect | Confirm the `db` service is running; verify `.env` credentials match QGIS settings |
| `psycopg2` import error | Run `docker compose up --build` to rebuild the smoke-test image |

---

## Implemented / Planned / Not Started

| Category | Status |
| -------- | -------- |
| **Implemented** | Repository structure, Docker Compose, PostgreSQL/PostGIS, smoke test, documentation, M1.1 synthetic-terrain flood-connectivity core with BFS and 4-neighbor rules |
| **Planned** | Flood model with real DEM integration, rainfall ingestion, road network, alert engine, MapLibre interface |
| **Not Started** | — |

---

## Repository Structure

```
kshitij/
├── .gitignore
├── .env.example
├── compose.yaml
├── pyproject.toml
│
├── Dockerfile
│
├── requirements.txt
│
├── scripts/
│   └── smoke_test.py
│
├── src/
│   └── kshitij_model/
│       ├── __init__.py
│       └── connectivity.py
│
├── docs/
│   ├── DEVELOPMENT.md
│   └── DATA_SOURCES.md
│
├── tests/
│   └── test_connectivity.py
│
└── README.md
```