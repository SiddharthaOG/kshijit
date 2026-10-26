# Kshitij — Implementation Status

## Milestone Overview

| Milestone | Status | Description |
| --------- | ------ | ----------- |
| **M0** | ✅ Configuration complete | Repository, Docker Compose, PostgreSQL/PostGIS config, documentation |
| **M1.1** | ✅ Implemented & tested | Synthetic-terrain flood-connectivity core: NumPy-based threshold-connectivity model with 4-neighbor BFS, 42 tests pass |
| **M1.2 Phase 1** | ✅ **Completed** | DEM acquisition: 3 Copernicus DEM GLO-30 tiles acquired, verified, and cached |
| **M1.2 Phase 2** | ✅ **Completed** | Raster preprocessing: crop, mosaic, validity masks, GeoTIFF output |
| **M1.2 Phase 3** | ✅ **Completed** | Model adapter: raster-to-array adapter with validity mask preservation |
| **M1.2 Phase 4** | ✅ **Completed** | Offline tests: synthetic raster fixtures, edge cases, adapter regression |
| **M1.2 Phase 5-6** | 📋 Planned | Documentation, storage portability, CI integration |

## Deliverables and Verification Status

| Deliverable | Status | Verified |
| ----------- | ------ | -------- |
| `README.md` | ✅ Created | Yes |
| `IMPLEMENTATION_STATUS.md` | ✅ Created | Yes |
| `.gitignore` | ✅ Created | Yes |
| `.env.example` | ✅ Created | Yes |
| `compose.yaml` | ✅ Created | Yes |
| `requirements.txt` | ✅ Created | Yes |
| `Dockerfile` | ✅ Created | Yes |
| `scripts/smoke_test.py` | ✅ Created | Yes |
| `docs/DEVELOPMENT.md` | ✅ Created | Yes |
| `docs/DATA_SOURCES.md` | ✅ Created | Yes |
| `tests/` directory | ✅ Created | Yes |
| `src/kshitij_model/__init__.py` | ✅ Created | Yes |
| `src/kshitij_model/connectivity.py` | ✅ Created | Yes |
| `src/kshitij_model/config.py` | ✅ Created | Yes |
| `src/kshitij_model/dem_acquisition.py` | ✅ Created | Yes |
| `src/kshitij_model/raster_preprocessing.py` | ✅ Created | Yes |
| `tests/test_connectivity.py` | ✅ Created | Yes |
| `tests/test_dem_acquisition.py` | ✅ Created | Yes |
| `tests/test_raster_preprocessing.py` | ✅ Created | Yes |
| **Test suite (96 tests: 94 passed, 2 skipped)** | ✅ All passed | Yes |
| Docker Compose + PostgreSQL/PostGIS running | ⏳ Not yet run | — |
| Smoke test against running DB | ⏳ Not yet run | — |
| QGIS connection setup | ✅ Documented | — |
| **DEM tiles acquired** | ✅ **3 tiles downloaded** | ✅ Verified |
| **Acquisition manifest** | ✅ Created | ✅ Verified |
| **DEM cache and raw storage** | ✅ Configured | ✅ Verified |

## M1.1 Implementation Details

The synthetic-terrain flood-connectivity core (`src/kshitij_model/connectivity.py`) provides:

- `compute_flood_extent(elevation, source_mask, water_level)` — threshold-connectivity flood model
- 4-neighbor (cardinal) connectivity; diagonal contact alone does not connect
- Invalid elevations (NaN, ±inf) excluded from flooding and act as barriers
- Source cells must have finite elevation ≤ water_level to be eligible
- Boolean dtype enforcement for `source_mask`
- Strict elevation dtype validation (rejects bool, complex, object, string)
- Strict water_level validation (rejects bool, complex, string, None, overflow)
- Input arrays are not mutated
- Test suite (42 tests) covers documented core behavior, edge cases, and invariants (monotonicity, flooded-cell validity, input immutability, water-level precision)

## M1.2 Phase 1 — DEM Acquisition (COMPLETED)

### Tiles Acquired

| Tile ID | File Size | SHA-256 | Source |
| ------- | --------- | ------- | ------ |
| N16E079 | 42.9 MB | `4f1297596b709369...` | `s3://copernicus-dem-30m/.../N16E079.tif` |
| N16E080 | 47.5 MB | `4cbdb47bebed8262...` | `s3://copernicus-dem-30m/.../N16E080.tif` |
| N16E081 | 35.8 MB | `9eaabe87202bd85a...` | `s3://copernicus-dem-30m/.../N16E081.tif` |

**Total:** 126.3 MB (3 tiles)

### Verification

- ✅ SHA-256 checksums computed and recorded in `data/cache/manifest.json`
- ✅ Manifest verification: `DEMAcquisition().verify_manifest()` → PASSED
- ✅ All tiles readable via rasterio (EPSG:4326, 3600×3600, float32)
- ✅ Tile bounds correct for WGS84 1°×1° grid

### Acquisition Details

- **Source:** AWS Open Data Registry `s3://copernicus-dem-30m/` (anonymous access)
- **Dataset:** Copernicus DEM GLO-30 Public (DSM, EGM2008 vertical datum, EPSG:4326)
- **Tiles acquired:** N16E079 (42.9 MB), N16E080 (47.5 MB), N16E081 (35.8 MB)
- **Total size:** 126.3 MB
- **Licence:** CC BY 4.0 (Copernicus Free & Open Data Policy)
- **Manifest:** `data/cache/manifest.json` with SHA-256 checksums
- **Retrieval date:** 2026-10-23

### Known Constraints

- **DSM, not DTM:** Includes buildings/vegetation; not bare-earth terrain
- **NoData handling:** COG metadata lacks explicit NoData; auxiliary HEM files suggest -32768
- **Vertical datum:** EGM2008 geoid (orthometric heights)
- **Horizontal CRS:** EPSG:4326 (WGS84)

### Files Created

| File | Purpose |
| ---- | ------- |
| `src/kshitij_model/dem_acquisition.py` | Core acquisition module with caching, verification, manifest |
| `src/kshitij_model/config.py` | Configuration dataclass for DEM parameters |
| `src/kshitij_model/raster_preprocessing.py` | Raster preprocessing (inspect, crop, mosaic, validity masks, GeoTIFF, model adapter) |
| `tests/test_dem_acquisition.py` | 19 tests (config, tile info, manifest, acquisition, validation) |
| `tests/test_raster_preprocessing.py` | 11 tests (inspect, crop, mosaic, validity masks, GeoTIFF, model adapter) |
| `data/raw/dem/N16E079.tif` | Downloaded DEM tile |
| `data/raw/dem/N16E080.tif` | Downloaded DEM tile |
| `data/raw/dem/N16E081.tif` | Downloaded DEM tile |
| `data/cache/manifest.json` | Acquisition manifest with checksums |
| `data/cache/N16E079.json` | Tile metadata cache |
| `data/cache/N16E080.json` | Tile metadata cache |
| `data/cache/N16E081.json` | Tile metadata cache |
| `data/cache/manifest.json` | Full acquisition manifest |

## M1.1 Implementation Details

The synthetic-terrain flood-connectivity core (`src/kshitij_model/connectivity.py`) provides:

- `compute_flood_extent(elevation, source_mask, water_level)` — threshold-connectivity flood model
- 4-neighbor (cardinal) connectivity; diagonal contact alone does not connect
- Invalid elevations (NaN, ±inf) excluded from flooding and act as barriers
- Source cells must have finite elevation ≤ water_level to be eligible
- Boolean dtype enforcement for `source_mask`
- Strict elevation dtype validation (rejects bool, complex, object, string)
- Strict water_level validation (rejects bool, complex, string, None, overflow)
- Input arrays are not mutated
- Test suite (42 tests) covers documented core behavior, edge cases, and invariants (monotonicity, flooded-cell validity, input immutability, water-level precision)

## Known Constraints & Limitations

- PostGIS image updated to `postgis/postgis:17-3.5-alpine` (was `3.5-3.5-alpine`)
- Database credentials via environment variables only — never hard-coded
- `.env` is gitignored
- Smoke test retries 12 times at 5-second intervals for DB readiness
- **This is a research prototype — not a hydraulic simulation or validated flood forecast**
- **This application is for simulation and research purposes only — not for operational safety use**
- M1.1 model is standalone NumPy-based; does not use real DEM, rainfall, or road data
- Real DEM integration and historical flood validation remain planned for future milestones

## Future Milestones (Not Started)

- **M1.2 Phase 5-6**: Documentation updates, storage portability, CI integration
- **M1.3+**: Road network integration, alert engine, MapLibre interface
- Historical flood validation against 2024 Vijayawada event (IoU metrics)
- Live telemetry and satellite-based flood-extent validation
