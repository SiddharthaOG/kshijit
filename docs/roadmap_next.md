# Kshitij — Prioritized Roadmap (Next Engineering Milestones)

**Date:** 2026-10-26  
**Base Commit:** `0f84aa0` (master)  
**Current State:** M1.1 ✅, M1.2 Phases 1-2 ✅, M1.3 validation plan ✅, CI recovered ✅

---

## Priority Framework

| Priority | Definition |
|----------|------------|
| **P0** | Blocks CI, correctness, or reproducibility. Must fix before any feature work. |
| **P1** | Minimal viable historical replay + evaluation metrics. Directly enables M1.4. |
| **P2** | Data provenance, river-source-mask generation, raster-alignment safeguards. Hardens P1. |
| **P3** | PostGIS persistence, spatial queries. Enables scaling beyond files. |
| **P4** | API/service boundary, React + MapLibre visualization. Productization. |

> **Rule:** No P3/P4 work until P0/P1 complete. No PostGIS/Django/React/MapLibre/cloud until explicitly approved.

---

## P0 — CI, Correctness, Reproducibility (BLOCKERS)

| ID | Item | Rationale | Dependencies | Acceptance Criteria | Effort | Status |
|----|------|-----------|--------------|---------------------|--------|--------|
| P0-1 | CI passes on GitHub Actions | Current PR only verified locally | — | All 3 checks pass on GH Actions (test, lint, docker) | S | ⏳ PR #open |
| P0-2 | Raster alignment guard in `prepare_model_input` | Prevents silent wrong results | P0-1 | Warn/error on CRS/transform/shape mismatch; test added | S | 📋 |
| P0-3 | `tests/__init__.py` in all test modules | Fixes INP001 | P0-1 | `tests/test_connectivity.py`, `test_dem_acquisition.py` have `__init__.py` | S | ✅ Done |
| P0-4 | `boto3` in `[test]` extra | Already done | — | `pip install -e ".[test]"` includes boto3 | S | ✅ Done |
| P0-5 | Remove `print()` from `dem_acquisition.py` | Clean output, CI-friendly | — | Replace with `logging` | S | 📋 |
| P0-6 | Remove unused imports (F401) in `dem_acquisition.py`, `raster_preprocessing.py` | Clean code | — | `ruff check --select F401` passes | S | 📋 |

---

## P1 — Minimal Historical Replay & Metrics (M1.4)

| ID | Item | Rationale | Dependencies | Acceptance Criteria | Effort | Status |
|----|------|-----------|--------------|---------------------|--------|--------|
| P1-1 | `validation.py` — preflight checks | Prevent silent errors | P0-2 | CRS/transform/shape/CRS checks; tests | S | 📋 |
| P1-2 | River source mask generator | Required for model input | — | OSM/HydroSHEDS → bool mask, buffer option, tests | M | 📋 |
| P1-3 | Replay CLI (`replay.py`) | End-to-end driver | P1-1, P1-2 | Config-driven sweep mode; manifest output | M | 📋 |
| P1-4 | Metrics module (IoU, P, R, F1, area ratio) | Core evaluation | — | Formulas match spec; undefined→null; tests | S | 📋 |
| P1-5 | Run manifest writer | Reproducibility | P1-3 | JSON with commit, config hash, inputs, timestamps | S | 📋 |
| P1-6 | Comparison raster writer (4-band) | Visual inspection | P1-4 | GeoTIFF: TP/FP/FN/TN bands | S | 📋 |
| P1-7 | Metrics JSON + Markdown report | Human review | P1-4, P1-6 | JSON + MD; undefined→null | S | 📋 |
| P1-8 | Sweep mode (water level range) | Find best-fit IoU | P1-3 | Configurable min/max/step; records best WL | S | 📋 |
| P1-9 | Synthetic test fixtures | Confidence before real data | P1-1..P1-4 | All-dry, all-flooded, NoData edge, mismatched grid | M | 📋 |
| P1-10 | Full Sep 2024 replay execution | End-to-end validation | P1-1..P1-9 | Run with N16E080/081, produce artifacts | L | 📋 |

> **Gate:** P1-10 requires CWC gauge data or explicit "sweep-only" label. No accuracy claims without stage data.

---

## P2 — Data Provenance, River Mask, Alignment Safeguards

| ID | Item | Rationale | Dependencies | Acceptance Criteria | Effort | Status |
|----|------|-----------|--------------|---------------------|--------|--------|
| P2-1 | DEM acquisition provenance manifest | Audit trail | — | `manifest.json` with SHA256, timestamps, source URLs | S | ✅ Done (M1.2) |
| P2-2 | River source mask from OSM/HydroSHEDS | Automate source mask | P1-2 | OSM Overpass query → river polyline → rasterize → buffer | M | 📋 |
| P2-3 | Raster alignment utility | Prevent mismatch | P0-2 | `align_rasters(ref, target) → aligned_target` | M | 📋 |
| P2-4 | DEM NoData verification | Trust but verify | — | Read HEM auxiliary, confirm -32768 sentinel | S | 📋 |
| P2-5 | River source mask from gauge stations | Alternative to OSM | P2-2 | CWC gauge locations → upstream catchment mask | M | 📋 |
| P2-5 | Reproject option in `crop_raster` | Support non-EPSG:4326 | P0-2 | `dst_crs` implemented; tests | M | 📋 |
| P2-6 | Multi-band `mosaic_tiles` support | Future-proof | — | Document limitation or implement | M | 📋 |
| P2-7 | River source mask from gauge stations | Alternative to OSM | P2-2 | CWC gauge locations → upstream catchment mask | M | 📋 |

---

## P3 — PostGIS Persistence & Spatial Queries

| ID | Item | Rationale | Dependencies | Acceptance Criteria | Effort | Status |
|----|------|-----------|--------------|---------------------|--------|--------|
| P3-1 | PostGIS schema for DEM tiles | Persistent storage | P2-1 | Table with raster column, SRID, metadata JSONB | M | 📋 |
| P3-2 | PostGIS schema for flood extents | Query/analysis | P1-4 | Table with raster, water_level, metrics JSONB, timestamp | M | 📋 |
| P3-3 | PostGIS schema for river network | Source mask source | P2-2 | LineString geometry, stream_order, source | M | 📋 |
| P3-4 | Spatial indexes & queries | Performance | P3-1..P3-3 | GiST indexes; bbox/contains queries < 100ms | M | 📋 |
| P3-4 | Docker Compose PostGIS 17 | CI/CD ready | — | `postgis/postgis:17-3.5-alpine`; healthcheck | S | ✅ Done |
| P3-5 | Migration system (Alembic) | Schema evolution | P3-1 | Versioned migrations; downgrade support | M | 📋 |

---

## P4 — API/Service Boundary & Visualization

| ID | Item | Rationale | Dependencies | Acceptance Criteria | Effort | Status |
|----|------|-----------|--------------|---------------------|--------|--------|
| P4-1 | FastAPI service skeleton | Service boundary | P3-1 | `/replay`, `/metrics`, `/tiles/{z}/{x}/{y}` endpoints | M | 📋 |
| P4-2 | COG output for flood extents | Web tiling | P1-4 | `rio cogeo` convert → COG; validate | S | 📋 |
| P4-3 | PMTiles / MBTiles export | Frontend tiles | P4-2 | `tippecanoe` or `rio-mbtiles` | M | 📋 |
| P4-4 | React + MapLibre prototype | Visualization | P4-2 | Map with flood extent overlay, water level slider | L | 📋 |
| P4-5 | API authentication/rate limiting | Production readiness | P4-1 | JWT or API key; rate limits | M | 📋 |

---

## Cross-Cutting Decisions Needing Approval

| Decision | Options | Recommendation | Impact |
|----------|---------|----------------|--------|
| **River mask source** | OSM vs HydroSHEDS vs CWC gauges | OSM for now (free, global); add gauge fallback later | Blocks P1-2 |
| **Vertical datum alignment** | DEM=EGM2008, gauge=?, model=? | Document assumption; require gauge metadata | Blocks P1-10 |
| **Reference map CRS** | EPSG:4326 vs UTM 44N | Assume EPSG:4326; verify during digitization | Blocks P1-10 |
| **Reference map digitization** | Manual (QGIS) vs automated | Manual for v1; document process | Blocks P1-10 |
| **Water level sweep vs gauge** | Sweep (post-hoc) vs gauge (predictive) | Sweep only for M1.4; gauge for M1.5+ | Blocks P1-10 |
| **PostGIS vs file-based** | When to migrate | File-based until P3-1; migrate when query need > 10k rasters | Blocks P3 |
| **Frontend framework** | React + MapLibre vs Leaflet | MapLibre (vector tiles, GL style) | Blocks P4-4 |

---

## Next Milestone Definition (M1.5+)

| Milestone | Scope | Prerequisites |
|-----------|-------|---------------|
| **M1.5** | Gauge-supported validation + PostGIS persistence | M1.4 complete, CWC data access |
| **M1.6** | Rainfall ingestion (Open-Meteo) + dynamic water level | M1.5 |
| **M1.7** | Road network integration (OSM) + impact metrics | M1.5 |
| **M2.0** | API service + MapLibre prototype | M1.6 + P3 complete |

---

## Single Highest-Priority Next Milestone

> **M1.4 (P1-1 through P1-10): Minimal Historical Replay**
>
> **Why:** This is the first end-to-end validation of the model against real data. All prior work (M1.1, M1.2) builds toward this. It produces the first quantitative IoU/precision/recall numbers and establishes the evaluation framework.
>
> **Blocking:** CWC gauge data access (for stage-supported run) and NRSC reference map digitization (QGIS, 4+ GCPs). Can proceed in sweep-only mode without these, but must label results as "post-hoc best-fit, not predictive."
>
> **Target:** Complete P1-1 through P1-9 in this sprint; P1-10 when data available.

---

*End of Roadmap*