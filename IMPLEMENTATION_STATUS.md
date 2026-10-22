# Kshitij — Milestone M0 Implementation Status

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
| Docker Compose + PostgreSQL/PostGIS running | ✅ Not yet run | — |
| Smoke test against running DB | ✅ Not yet run | — |
| QGIS connection setup | ✅ Documented | — |

## Known Constraints

- PostGIS image pinned to `postgis/postgis:3.5-3.5-alpine` (not `latest`)
- Database credentials are via environment variables only — never hard-coded
- `.env` is gitignored
- Smoke test retries 12 times at 5-second intervals for DB readiness
- No flood-prediction model implemented (M0 foundation only)
- Mandatory disclaimer included in README

## Next Milestone

- **M1:** Thin slice end-to-end — decoupled Python package for historical rainfall parsing, one DEM tile, static map layout.
- **M1.1:** Synthetic-terrain flood-connectivity core — NumPy-based threshold-connectivity model with 4-neighbor BFS, testable in isolation.

## M1.1 Deliverables

| Deliverable | Status | Verified |
| ----------- | ------ | -------- |
| `src/kshitij_model/__init__.py` | ✅ Created | Yes |
| `src/kshitij_model/connectivity.py` | ✅ Created | Yes |
| `tests/test_connectivity.py` | ✅ Created | Yes |
| Test suite (14 tests) | ✅ All passed | Yes |

## Known Constraints

- PostGIS image pinned to `postgis/postgis:3.5-3.5-alpine` (not `latest`)
- Database credentials are via environment variables only — never hard-coded
- `.env` is gitignored
- Smoke test retries 12 times at 5-second intervals for DB readiness
- No flood-prediction model implemented (M0 foundation only)
- Mandatory disclaimer included in README
- M1.1 synthetic-terrain model is standalone NumPy-based; not a hydraulic simulation
- Real DEM integration remains planned for future milestones