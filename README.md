# Kshitij — Flood Risk Decision-Support Prototype

**Milestone M0: Repository and Geospatial Foundation** — Configuration implemented, runtime verification pending  
**Milestone M1.1: Synthetic-Terrain Flood-Connectivity Core** — Implemented and tested  

**Status:** M0 configuration complete, M1.1 implemented and tested. Runtime verification of Docker/PostGIS pending.

---

## Current Status Summary

| Component | Status |
|-----------|--------|
| Repository structure, configuration, documentation | ✅ Implemented |
| M1.1 flood-connectivity core (algorithm + tests) | ✅ Implemented & tested (42 tests pass) |
| Docker Compose + PostgreSQL/PostGIS configuration | ✅ Configured |
| Docker/PostGIS runtime verification | ⏳ Pending (requires Docker) |
| Database smoke test | ⏳ Pending (requires Docker) |
| M1.2+ DEM integration, rainfall, roads, alerting, MapLibre | 📋 Planned |

> **⚠️ This application is for simulation and research purposes only—not for operational safety use.**  
> It never sends real alerts and does not replace official forecasts from agencies such as IMD and CWC.

---

## Project Overview

Kshitij is a **research prototype** designed to help a human operator assess potential flood extents and road impacts using terrain, rainfall, and road data. The system combines these inputs with a threshold-connectivity flood model and presents estimates through a graduated, human-confirmed alert framework.

**Current capabilities (implemented):**
- Synthetic-terrain flood-connectivity model with 4-neighbor BFS (`src/kshitij_model/connectivity.py`)
- Strict input validation (elevation dtype, water_level type, source_mask Boolean)
- 94 automated tests covering connectivity, edge cases, and input validation
- Raster preprocessing: crop, mosaic, validity masks, GeoTIFF output, model adapter (`src/kshitij_model/raster_preprocessing.py`)
- DEM acquisition: Copernicus GLO-30 tiles, caching, manifest verification (`src/kshitij_model/dem_acquisition.py`)
- Docker Compose configuration for PostgreSQL/PostGIS with health checks
- Smoke test script for database connectivity and PostGIS verification

**Planned / Not yet implemented:**
- Real DEM integration and preprocessing (M1.2)
- Historical rainfall ingestion from Open-Meteo
- OpenStreetMap road network integration
- Graduated alert engine with human confirmation workflow
- MapLibre GL JS map interface
- Real-world validation against 2024 Vijayawada flood event

> **⚠️ This application is for simulation and research purposes only—not for operational safety use.**  
> It never sends real alerts and does not replace official forecasts from agencies such as IMD and CWC.

---

## Prerequisites

### For Python development and testing (no Docker required)
- Python 3.12+
- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-git)

### For database runtime verification (requires Docker)
- [Docker](https://docs.docker.com/engine/install/) with Docker Compose v2+
- [QGIS](https://qgis.org/en/site/forusers/download.html) (optional, for visual inspection of PostGIS data)

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/SiddharthaOG/kshijit.git kshijit
cd kshijit
```

### 2. Python development setup (recommended for testing)

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in development mode with test dependencies
pip install -e ".[test]"
```

### 3. Environment configuration (for Docker)

```bash
cp .env.example .env
# Edit .env as needed. Default values are suitable for local development.
```

### 4. Start the database (for runtime verification)

```bash
docker compose up -d db
```

This starts only the PostgreSQL/PostGIS service (`db`) with health checks. Wait for the health check to pass (check with `docker compose ps`).

### 5. Run smoke test (after database is healthy)

```bash
# Run smoke test against running database (exits with status code)
docker compose run --rm smoke-test
```

The smoke test runs as a one-off job. Its exit code indicates success (0) or failure (non-zero). Check the output for "All checks passed" or specific error messages.

### 6. Stop services

```bash
docker compose down
```

### 6. Inspect with QGIS (optional)

Connect QGIS to the local PostGIS database:
- Host: `127.0.0.1` (database port published to localhost only)
- Port: `5432`
- Database: `kshitij_db` (or value from `.env`)
- User: `kshitij_dev` (or value from `.env`)
- Password: (from `.env`)
- Check "Enable PostGIS connections"

---

## Environment Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
| -------- | -------- | ----------- |
| `POSTGRES_USER` | `kshitij_dev` | Database superuser |
| `POSTGRES_PASSWORD` | `dev_password_must_change` | Database password |
| `POSTGRES_DB` | `kshitij_db` | Database name |
| `POSTGRES_HOST` | `db` | Docker Compose service name (for inter-container) |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `DEBUG` | `True` | App debug mode |
| `SECRET_KEY` | `dev_secret_key_replace_me` | Secret key for development |

---

## Commands Reference

| Action | Command |
| -------- | -------- |
| Start database | `docker compose up -d db` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f` |
| Rebuild images | `docker compose build` |
| Run database smoke test | `docker compose run --rm smoke-test` |
| Connect QGIS | See "Inspect with QGIS" section |
| **Run Python tests (no Docker)** | `python -m pytest -v` |
| Install dev dependencies | `pip install -e ".[test]"` |

---

## Troubleshooting

| Issue | Resolution |
| -------- | ----------- |
| `db` service won't start | Check Docker resources; ensure no other service occupies port 5432 on 127.0.0.1 |
| Smoke test fails | Verify `.env` values; check `docker compose logs db` and `docker compose logs smoke-test` for errors |
| Smoke test not running | Run `docker compose run --rm smoke-test` manually after `db` is healthy |
| QGIS can't connect | Confirm `db` service is running; verify `.env` credentials; use host `127.0.0.1` |
| `psycopg2` import error in tests | Run `pip install -e ".[test]"` to install test dependencies |
| Python tests fail | Ensure virtual environment is activated and `pip install -e ".[test]"` was run |

---

## Test Suite

The project includes a comprehensive test suite for the M1.1 flood-connectivity core:

```bash
# Run all tests (no Docker required)
python -m pytest -v
```

**Current test coverage:** 96 tests covering:
- Core connectivity algorithm (corridors, isolated depressions, barriers, diagonal rules)
- Edge cases (NaN, ±inf elevation barriers, multiple sources, max water level)
- Input validation (dtype, shape, water_level type, overflow)
- Property tests (monotonicity, flooded-cell validity, input immutability, water-level precision)
- NoData sentinel handling (12 dedicated tests)
- Raster preprocessing: crop, mosaic, validity masks, GeoTIFF, model adapter
- DEM acquisition: config, tile info, manifest, acquisition, validation

---

## Implemented / Planned / Not Started

| Category | Status |
| -------- | -------- |
| **Implemented** | Repository structure, Docker Compose config, M1.1 flood-connectivity core (algorithm + 94 tests), M1.2 DEM acquisition & raster preprocessing, documentation |
| **Runtime-verified** | Python test suite (96 tests: 94 passed, 2 skipped) |
| **Pending runtime verification** | Docker/PostGIS startup, database smoke test (requires Docker) |
| **Planned (M1.3+)** | Historical validation (M1.3), Historical replay (M1.4), rainfall ingestion, road network, alert engine, MapLibre interface |

---

## Repository Structure

```
kshitij/
├── .gitignore
├── .env.example
├── compose.yaml
├── pyproject.toml
├── Dockerfile
├── requirements.txt
├── scripts/
│   └── smoke_test.py
├── src/
│   └── kshitij_model/
│       ├── __init__.py
│       ├── connectivity.py
│       ├── raster_preprocessing.py
│       ├── dem_acquisition.py
│       └── config.py
├── docs/
│   ├── DEVELOPMENT.md
│   ├── DATA_SOURCES.md
│   ├── engineering_audit.md
│   ├── m13_historical_validation_plan.md
│   ├── m14_historical_replay_spec.md
│   └── roadmap_next.md
├── tests/
│   ├── __init__.py
│   ├── test_connectivity.py
│   ├── test_dem_acquisition.py
│   └── test_raster_preprocessing.py
└── README.md
```

---

## License

This project is for research and simulation purposes only.