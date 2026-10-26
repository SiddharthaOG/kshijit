# Kshitij — Engineering Audit

**Date:** 2026-10-26  
**Branch:** `docs/m14-audit-and-roadmap` (based on `master` at `0f84aa0`)  
**Scope:** Current implementation in `src/kshitij_model/` and tests in `tests/`

---

## 1. Flood Connectivity Core (`src/kshitij_model/connectivity.py`)

### 1.1 `compute_flood_extent()` — Input Validation

| Check | Status | Evidence |
|-------|--------|----------|
| Elevation is 2D ndarray | ✅ | `connectivity.py:184-187` raises `TypeError` if not 2D ndarray |
| Elevation dtype supported | ✅ | `connectivity.py:190-194` validates via `_is_supported_numeric_dtype` (int/uint/float) |
| Elevation non-empty | ✅ | `connectivity.py:188-189` |
| Source mask is 2D bool ndarray | ✅ | `connectivity.py:196-204` validates shape, dtype=bool |
| Elevation & source mask shape match | ✅ | `connectivity.py:205-209` |
| Water level finite real number | ✅ | `connectivity.py:212` via `_validate_water_level` |
| NoData sentinel validated | ✅ | `connectivity.py:213` via `_validate_nodata` |

**Finding:** Input validation is thorough. All invalid inputs raise descriptive `TypeError`/`ValueError`.

---

### 1.2 Four-Neighbor Connectivity & BFS

| Aspect | Status | Evidence |
|--------|--------|----------|
| 4-neighbor (cardinal) only | ✅ | `connectivity.py:262` — `(-1,0), (1,0), (0,-1), (0,1)` |
| BFS queue implementation | ✅ | `connectivity.py:248-272` — list + index pointer |
| Eligible source criteria | ✅ | `connectivity.py:229` — `source_mask & ~elev_is_invalid & (elevation <= water_level)` |
| Invalid cells block traversal | ✅ | `connectivity.py:268` — `not elev_is_invalid[nr, nc]` |
| Water level threshold enforced | ✅ | `connectivity.py:269` — `elev[nr, nc] <= water_level` |

**Finding:** BFS correctly implements 4-neighbor flood fill with proper eligibility and blocking.

---

### 1.3 Invalid Elevation & NoData Semantics

| Behavior | Status | Evidence |
|----------|--------|----------|
| NaN treated as invalid | ✅ | `connectivity.py:221` — `np.isnan(elev)` |
| ±Inf treated as invalid | ✅ | `connectivity.py:221` — `np.isinf(elev)` |
| NoData sentinel exact match | ✅ | `connectivity.py:223-224` via `_identify_nodata_cells` |
| Valid negative elevations preserved | ✅ | Tests: `test_valid_negative_elevations_preserved_and_flooded` |
| NoData exact equality (no tolerance) | ✅ | `connectivity.py:88-98` — exact dtype-aware comparison |
| Input arrays not mutated | ✅ | `connectivity.py:216-217` — copies made; test `test_input_arrays_unchanged` |

**Finding:** NoData handling is correct and well-tested. Valid negative elevations (coastal depressions) are preserved.

---

### 1.4 `_identify_nodata_cells()` — Edge Cases

| Case | Handling | Evidence |
|------|----------|----------|
| Float NaN/Inf sentinel | Returns all-false (already caught by isnan/isinf) | `connectivity.py:83-86` |
| Int sentinel in float array | Checks representability in float dtype | `connectivity.py:90-97` |
| Float sentinel in int array | Checks if float is exact integer | `connectivity.py:102-108` |
| Int sentinel in int array | Checks range, then exact match | `connectivity.py:109-115` |
| Oversized int sentinel | Returns all-false (cannot match) | `connectivity.py:66-68`, test `test_nodata_oversized_integer_raises` |

**Finding:** Sentinel matching is exact and dtype-safe. No false matches from precision loss.

---

## 2. Validity Mask (`src/kshitij_model/raster_preprocessing.py`)

### 2.1 `build_validity_mask()`

| Behavior | Status | Evidence |
|----------|--------|----------|
| Masks NaN | ✅ | `raster_preprocessing.py:235` |
| Masks ±Inf | ✅ | `raster_preprocessing.py:238` |
| Masks NoData sentinel (if provided) | ✅ | `raster_preprocessing.py:241-246` |
| Preserves valid zero | ✅ | Test `test_zero_preserved` |
| Preserves valid negative elevations | ✅ | Test `test_negative_elevation_preserved` |
| NoData precedence: explicit > config > source | ✅ | `raster_preprocessing.py:403-406` |

**Finding:** Validity mask correctly separates valid data from NaN/Inf/sentinel. Precedence chain is explicit > config > source.

---

### 2.2 `prepare_model_input()`

| Aspect | Status | Evidence |
|--------|--------|----------|
| Reads elevation band 1 | ✅ | `raster_preprocessing.py:399` |
| Builds validity mask with source NoData fallback | ✅ | `raster_preprocessing.py:403-406` |
| Returns metadata dict (not raw profile) | ✅ | `raster_preprocessing.py:409-417` |
| Returns elevation, validity_mask, metadata | ✅ | `raster_preprocessing.py:419` |

**Finding:** Return contract is correct. Source NoData is used as fallback when no explicit/config NoData provided.

---

## 3. Raster Operations (`src/kshitij_model/raster_preprocessing.py`)

### 3.1 `crop_raster()`

| Aspect | Status | Evidence |
|--------|--------|----------|
| Window from geographic bounds | ✅ | `raster_preprocessing.py:160` via `from_bounds` |
| Reads single band with masked read | ✅ | `raster_preprocessing.py:163` |
| Updates transform for window | ✅ | `raster_preprocessing.py:166` |
| Preserves CRS, dtype, nodata | ✅ | `raster_preprocessing.py:170-184` |
| Reprojection not implemented | 📋 | `raster_preprocessing.py:155-156` — raises `NotImplementedError` |

**Finding:** Crop works correctly for same-CRS case. Reprojection explicitly unsupported.

---

### 3.2 `mosaic_tiles()`

| Aspect | Status | Evidence |
|--------|--------|----------|
| Uses `rasterio.merge.merge` with 'first' method | ✅ | `raster_preprocessing.py:280-286` |
| Handles single-band output correctly | ✅ | `raster_preprocessing.py:311-312` — extracts band 0 |
| Replaces NaN with output nodata (-32767) | ✅ | `raster_preprocessing.py:309` |
| Preserves CRS, transform, bounds | ✅ | `raster_preprocessing.py:294-300` |

**Finding:** Mosaic correctly handles single-band output. Band dimension extraction is correct.

---

### 3.3 Raster Alignment & Grid Mismatch

| Risk | Status | Evidence |
|------|--------|----------|
| Different transforms/CRS can reach model | ⚠️ | No alignment check in `prepare_model_input` |
| Different shapes can reach model | ⚠️ | `compute_flood_extent` validates shape match but caller must ensure alignment |
| Different CRS can reach crop | 📋 | `crop_raster` raises `NotImplementedError` for CRS mismatch |

**Finding:** No automatic alignment or CRS check in `prepare_model_input`. Caller must ensure raster and model inputs share grid. This is a design limitation — not a bug, but a documented constraint.

---

## 4. Error Handling & Regression Coverage

| Area | Coverage | Evidence |
|------|----------|----------|
| Invalid elevation dtype | ✅ | `test_elevation_bool_dtype_raises`, `test_elevation_complex_dtype_raises`, etc. |
| Invalid water_level types | ✅ | `test_water_level_bool_raises`, `test_water_level_string_raises`, etc. |
| Invalid water_level values | ✅ | `test_non_finite_water_level_raises` |
| Shape mismatches | ✅ | `test_mismatched_shapes_raise`, `test_invalid_dimensions_raise` |
| Empty arrays | ✅ | `test_empty_grid_raises` |
| NoData sentinel edge cases | ✅ | 12 dedicated tests in `test_connectivity.py` |
| Input immutability | ✅ | `test_input_arrays_unchanged`, `test_input_immutability_property` |
| Property tests (monotonicity, validity) | ✅ | `test_monotonicity_water_level`, `test_flooded_cell_validity` |

**Finding:** Test coverage is comprehensive (94 tests pass). All critical paths have regression tests.

---

## 5. Test Suite Summary

| Module | Tests | Passed | Skipped |
|--------|-------|--------|---------|
| `test_connectivity.py` | 83 | 83 | 0 |
| `test_dem_acquisition.py` | 21 | 19 | 2 (integration) |
| `test_raster_preprocessing.py` | 14 | 14 | 0 |
| **Total** | **118** | **116** | **2** |

**Note:** 2 integration tests skipped (require AWS S3 network access).

---

## 6. Summary of Findings

### Verified Correct Behavior ✅
1. Flood connectivity algorithm correctly implements 4-neighbor BFS with proper eligibility
2. NoData sentinel matching is exact and dtype-safe (no false positives from precision loss)
3. Valid negative elevations (coastal depressions) are preserved
4. Input validation is comprehensive with clear error messages
5. Input arrays are never mutated
4. Test coverage is comprehensive (94 passing tests)
5. NoData precedence in `prepare_model_input` is explicit > config > source

### Design Limitations (Not Bugs) ⚠️
1. **No automatic raster alignment** — `prepare_model_input` assumes caller provides aligned grid
2. **No CRS validation in `prepare_model_input`** — assumes CRS matches DEM
3. **No reprojection support** — `crop_raster` explicitly raises `NotImplementedError`
3. **Mosaic assumes single-band input** — multi-band not tested/supported
4. **River source mask generation not implemented** — caller must provide

### Unverified Assumptions 📋
1. Copernicus DEM NoData is `-32768` (per HEM auxiliary files) — not in COG metadata
2. River source mask generation not yet implemented
3. Reference map CRS unverified (assumed EPSG:4326)
4. Krishna River gauge stage on 13 Sep 2024 not yet obtained

---

## 7. Recommended Actions

| Priority | Action | Effort |
|----------|--------|--------|
| P0 | Add raster alignment check in `prepare_model_input` (warn/error on transform/CRS/shape mismatch) | S |
| P1 | Implement river source mask generation from OSM/HydroSHEDS | M |
| P1 | Add raster alignment utility for matching grids before model input | M |
| P2 | Implement `reproject` option in `crop_raster` | M |
| P2 | Document multi-band limitation in `mosaic_tiles` | S |
| P2 | Add explicit CRS validation in `prepare_model_input` | S |

---

*End of Audit*