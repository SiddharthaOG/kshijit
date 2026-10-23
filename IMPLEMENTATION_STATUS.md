# Kshitij — Implementation Status

## Milestone Overview

| Milestone | Status | Description |
| --------- | ------ | ----------- |
| **M0** | ✅ Configuration complete | Repository, Docker Compose, PostgreSQL/PostGIS config, documentation |
| **M1.1** | ✅ Implemented & tested | Synthetic-terrain flood-connectivity core: NumPy-based threshold-connectivity model with 4-neighbor BFS, 38 tests pass |
| **M1.2** | 📋 Planned | DEM integration, preprocessing, historical rainfall ingestion |

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
| `tests/test_connectivity.py` | ✅ Created | Yes |
| **Test suite (38 tests)** | ✅ All passed | Yes |
| Docker Compose + PostgreSQL/PostGIS running | ⏳ Not yet run | — |
| Smoke test against running DB | ⏳ Not yet run | — |
| QGIS connection setup | ✅ Documented | — |

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
- Test suite covers documented core behavior and selected edge cases

## Known Constraints & Limitations

- PostGIS image pinned to `postgis/postgis:3.5-3.5-alpine` (not `latest`)
- Database credentials via environment variables only — never hard-coded
- `.env` is gitignored
- Smoke test retries 12 times at 5-second intervals for DB readiness
- **This is a research prototype — not a hydraulic simulation or validated flood forecast**
- **This application is for simulation and research purposes only — not for operational safety use**
- M1.1 model is standalone NumPy-based; does not use real DEM, rainfall, or road data
- Real DEM integration and historical flood validation remain planned for future milestones

## Future Milestones (Not Started)

- **M1.2**: Real DEM integration, DEM preprocessing, and historical rainfall ingestion pipeline
- **M1.3+**: Road network integration, alert engine, MapLibre interface
- Historical flood validation against 2024 Vijayawada event (IoU metrics)
- Live telemetry and satellite-based flood-extent validation