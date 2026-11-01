<div align="center">

# 🌊 Kshitij — Flood Risk Decision-Support Prototype

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Rasterio](https://img.shields.io/badge/Rasterio-Geospatial-8B0000?style=for-the-badge)
![pytest](https://img.shields.io/badge/pytest-Passing-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-Linted-269D69?style=for-the-badge&logo=ruff&logoColor=white)

*A research prototype for exploring flood extent estimation and its potential implications for infrastructure and human decision-making.*

<img src="https://images.unsplash.com/photo-1561484652-5c5b3e1c0f7e?w=800&h=300&fit=crop" alt="Kshitij Flood Risk Banner" width="800" />

---

![M0](https://img.shields.io/badge/M0-Geospatial_Foundation-brightgreen?style=flat-square)
![M1.1](https://img.shields.io/badge/M1.1-Flood_Connectivity_Core-brightgreen?style=flat-square)
![M1.2](https://img.shields.io/badge/M1.2-Geospatial_Processing-brightgreen?style=flat-square)
![M1.4](https://img.shields.io/badge/M1.4-Real_DEM_Pipeline-brightgreen?style=flat-square)
![M1.5](https://img.shields.io/badge/M1.5-Historical_Validation-yellow?style=flat-square)

</div>

---

## 📋 Project Overview

Kshitij is a research prototype for exploring flood extent estimation and its potential implications for infrastructure and human decision-making.

The project combines terrain data, river geometry, and a threshold-connectivity flood model to estimate areas that may become inundated under specified water-level assumptions.

The long-term objective is to develop a reproducible geospatial decision-support workflow that can incorporate historical reference data and infrastructure information while keeping model limitations and uncertainty visible.

> ⚠️ **Important:** Kshitij is a research and simulation prototype. It is **not** an operational flood forecasting or early-warning system. Its outputs must not be used as a substitute for official forecasts, evacuation instructions, or warnings issued by agencies such as the IMD and CWC.

---

## 📊 Current Status

| Component | Status |
|---|---|
| Repository structure and Python package configuration | ✅ Implemented |
| Docker Compose and PostgreSQL/PostGIS configuration | ✅ Implemented |
| M1.1 synthetic-terrain flood-connectivity algorithm | ✅ Implemented and tested |
| Input validation and connectivity edge cases | ✅ Implemented and tested |
| Geospatial raster preprocessing | ✅ Implemented |
| DEM acquisition, caching, mosaicking, and cropping | ✅ Implemented |
| River-vector processing and rasterization | ✅ Implemented |
| Real-DEM flood-extent pipeline | ✅ Implemented |
| Three-state flood-extent GeoTIFF output | ✅ Implemented |
| Validation metrics and raster comparison utilities | ✅ Implemented |
| OSM river-extraction groundwork | ✅ Implemented |
| Georeferencing and digitization of the historical reference map | 🔄 In progress |
| Historical event comparison and model calibration | 🔄 In progress |
| Independent validation | ⏳ Not yet established |
| Road-impact analysis and alerting | 📋 Planned |
| Map-based visualization interface | 📋 Planned |

---

## 🧪 Implemented Capabilities

### 1. Flood-Connectivity Model

The core model estimates flood connectivity using a four-neighbour Breadth-First Search (BFS) approach.

Starting from eligible source cells, the algorithm propagates through neighbouring cells that satisfy the specified elevation threshold.

Implemented functionality includes:

- Four-neighbour connectivity (up, down, left, right).
- Elevation-threshold-based flood propagation.
- Source-mask validation.
- Input shape and dtype validation.
- Handling of invalid and non-finite elevation values.
- Protection against invalid water-level inputs.
- Deterministic flood-connectivity results.

The original synthetic-terrain implementation provides the algorithmic foundation for the real-DEM pipeline.

### 2. Real-DEM Flood-Extent Pipeline — M1.4

M1.4 extends the existing connectivity model to real geospatial elevation data.

The pipeline integrates:

1. **DEM acquisition:** Retrieves and caches the required Copernicus DEM GLO-30 tiles.
2. **Mosaicking and cropping:** Combines the required elevation tiles and crops the resulting raster to the selected area of interest.
3. **Raster preparation:** Prepares elevation data and validity information for processing.
4. **River-mask generation:** Reads supplied river-vector data, transforms geometry into the raster coordinate system, applies the configured buffer, and rasterizes the result onto the DEM grid.
5. **Flood computation:** Runs the existing connectivity algorithm using the generated river mask as the source mask.
6. **Output generation:** Writes the resulting flood extent as a georeferenced raster.

The flood-extent output uses three values:

| Value | Meaning |
|---|---|
| `1` | 🌊 Flooded cell |
| `0` | ✅ Valid, non-flooded cell |
| `255` | ⬜ NoData / invalid cell |

The pipeline is designed to reuse the existing connectivity implementation rather than introduce a separate flood-propagation algorithm.

> ⚠️ **Model limitation:** This is a static, elevation-threshold connectivity model. It does not simulate rainfall-runoff processes, fluid momentum, flow velocity, discharge, temporal flood propagation, or full hydrodynamic behaviour.
>
> A generated flood extent should therefore be interpreted as a terrain-based scenario estimate under specified assumptions, not as a physically complete flood simulation.

### 3. Validation and Comparison Groundwork — M1.5

The project includes utilities intended to support comparison between model outputs and historical reference data.

Implemented groundwork includes:

- Confusion-matrix metrics: TP, FP, FN, and TN.
- Intersection over Union (IoU).
- Precision, recall, and F1 score.
- Area-ratio calculations.
- Raster-alignment utilities.
- RGB comparison and visualization utilities.
- OpenStreetMap river-extraction utilities.

These utilities provide the foundation for evaluating model outputs against a georeferenced reference map.

The September 13, 2024 Vijayawada flood reference map is part of the planned historical comparison workflow.

> ℹ️ **Historical validation is not yet complete.** The reference map must first be georeferenced and converted into a suitable reference inundation mask. Model outputs must then be generated on a compatible grid before meaningful comparison can take place.
>
> Calibration against a reference event must also be distinguished from independent validation. Selecting parameters using a reference map and evaluating against that same map does not constitute independent validation.

---

## 🛠️ Technology and Data

| Component | Technology / Data |
|---|---|
| Programming language | Python 3.12+ |
| Numerical processing | NumPy |
| Geospatial raster processing | Rasterio |
| Elevation data | Copernicus DEM GLO-30 |
| Vector processing | Fiona, Shapely |
| Coordinate transformations | PyProj |
| River data groundwork | OpenStreetMap |
| Database | PostgreSQL |
| Spatial database extension | PostGIS |
| Containerization | Docker Compose |
| Testing | pytest |
| Linting and formatting | Ruff |

---

## 📦 Prerequisites

### Python development and testing

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![Git](https://img.shields.io/badge/Git-Required-F05032?style=flat-square&logo=git&logoColor=white)
![pip](https://img.shields.io/badge/pip-Latest-3775A9?style=flat-square&logo=pypi&logoColor=white)

- Python 3.12 or later
- Git
- pip

### Optional database runtime verification

![Docker](https://img.shields.io/badge/Docker-Optional-2496ED?style=flat-square&logo=docker&logoColor=white)
![QGIS](https://img.shields.io/badge/QGIS-Optional-589632?style=flat-square&logo=qgis&logoColor=white)

- Docker
- Docker Compose v2+
- QGIS (optional, for inspecting geospatial outputs and PostGIS data)

---

## 🚀 Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/SiddharthaOG/kshijit.git
cd kshijit
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install the project and development dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test,river]"
```

The `test` and `river` extras install the dependencies required for the development test suite and river-vector processing.

### 4. Configure environment variables for Docker

Copy the example environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Edit `.env` if you need to change the local database configuration.

### 5. Start PostgreSQL/PostGIS

```bash
docker compose up -d db
```

Check the database status:

```bash
docker compose ps
```

Wait until the database health check reports that the service is healthy.

### 6. Run the database smoke test

```bash
docker compose run --rm smoke-test
```

The smoke test checks database connectivity and PostGIS availability. A successful run exits with status code `0`.

### 7. Stop the database

```bash
docker compose down
```

---

## 💻 Development Commands

| Action | Command |
|---|---|
| Install development dependencies | `python -m pip install -e ".[test,river]"` |
| Run the test suite | `python -m pytest -v` |
| Run Ruff lint checks | `python -m ruff check src/ tests/` |
| Check formatting | `python -m ruff format --check src/ tests/` |
| Start PostgreSQL/PostGIS | `docker compose up -d db` |
| Stop Docker services | `docker compose down` |
| View Docker logs | `docker compose logs -f` |
| Run database smoke test | `docker compose run --rm smoke-test` |

The Python test suite does not require Docker. Database smoke testing requires Docker and a running database service.

---

## ⚙️ Environment Configuration

The Docker database configuration is controlled through `.env`.

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `kshitij_dev` | Database user |
| `POSTGRES_PASSWORD` | `dev_password_must_change` | Local development password |
| `POSTGRES_DB` | `kshitij_db` | Database name |
| `POSTGRES_HOST` | `db` | Docker Compose database service |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `DEBUG` | `True` | Development debug setting |
| `SECRET_KEY` | `dev_secret_key_replace_me` | Development secret key |

> 🔒 Use appropriate secrets for any deployment beyond local development. Do not commit `.env` files or credentials.

---

## 🧪 Testing and Code Quality

The project uses pytest for automated testing and Ruff for linting and formatting.

The test suite covers the flood-connectivity algorithm, geospatial processing, input validation, pipeline behaviour, river-mask generation, and validation utilities.

Run the complete test suite:

```bash
python -m pytest -v
```

Run lint checks:

```bash
python -m ruff check src/ tests/
```

Check formatting:

```bash
python -m ruff format --check src/ tests/
```

The repository also uses GitHub Actions to run automated checks on changes submitted through the GitHub workflow.

---

## 🗺️ Project Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Repository structure, configuration, Docker/PostGIS foundation | ✅ Implemented |
| M1.1 | Synthetic-terrain flood-connectivity algorithm | ✅ Implemented |
| M1.2 | Geospatial processing foundation | ✅ Implemented |
| M1.4 | Real-DEM flood-extent pipeline | ✅ Implemented |
| M1.5 | Historical reference comparison, validation, and calibration | 🔄 In progress |
| Future | Road-network impact analysis | 📋 Planned |
| Future | Graduated alert framework with human confirmation | 📋 Planned |
| Future | Interactive map-based visualization | 📋 Planned |

Milestone numbering reflects the project's development plan; it does not imply that every intermediate milestone has been independently released.

---

## ⚠️ Scientific Limitations and Intended Use

Kshitij is intended for research, experimentation, and development of geospatial flood-risk analysis workflows.

Its current flood model:

- Uses terrain elevation and a specified water-level threshold.
- Relies on connectivity from designated source cells.
- Does not solve the shallow-water equations.
- Does not model time-dependent water movement or flow velocity.
- Does not independently establish the accuracy of a real-world flood prediction.

Historical comparisons can help assess how closely a selected model configuration corresponds to a reference inundation map. They do not, by themselves, establish operational forecasting capability.

> 📌 All results should be interpreted with these limitations in mind.

---

## 📁 Repository Structure

The repository is organized around the Python package, its geospatial processing modules, tests, documentation, and Docker configuration.

```text
kshitij/
├── .github/
│   └── workflows/
├── docker-compose/
├── docs/
├── scripts/
├── src/
│   └── kshitij_model/
│       ├── connectivity.py
│       ├── pipeline.py
│       ├── raster_preprocessing.py
│       ├── river_mask.py
│       └── validation.py
├── tests/
├── .env.example
├── .gitignore
├── compose.yaml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── README.md
```

This is a high-level structural overview; individual modules and supporting files may evolve as development continues.

---

## 📄 License

This project is intended for research and simulation purposes. Refer to the repository's license information for applicable terms.

---

<div align="center">

*Advancing flood-risk understanding through reproducible geospatial research.* 🌍

</div>
