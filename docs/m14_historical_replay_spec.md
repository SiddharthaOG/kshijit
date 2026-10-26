# Kshitij M1.4 — Historical Replay Specification

**Status:** Specification only — no validation executed  
**Branch:** `docs/m14-audit-and-roadmap` (based on `master` at `0f84aa0`)  
**Prerequisites:** M1.2 DEM acquisition, M1.2 raster preprocessing, M1.1 connectivity core

---

## 1. Objective

Execute a reproducible historical replay comparing Kshitij's simulated flood extent against the ISRO/NRSC September 13, 2024 Vijayawada inundation map (AP_2024_13_09_Map.pdf), using Copernicus DEM GLO-30 tiles and the existing M1.1 flood-connectivity model.

**This is a plan only.** No validation has been executed. Results will be reported as plausibility comparison, not predictive accuracy.

---

## 2. Input Data & Directory Layout

```
data/
├── raw/
│   ├── dem/                    # Copernicus DEM GLO-30 (immutable, cached)
│   │   ├── N16E080.tif         # Core tile (80°E–81°E, 16°N–17°N)
│   │   └── N16E081.tif         # Eastern tile (81°E–82°E, 16°N–17°N)
│   ├── reference/
│   │   ├── AP_2024_13_09_Map.pdf          # ISRO/NRSC reference map
│   │   └── AP_2024_13_09_Map_digitized.tif # GeoTIFF (digitized, 30m, EPSG:4326)
│   └── rivers/
│       └── krishna_river.gpkg    # River polyline (OSM/HydroSHEDS, clipped to AOI)
├── processed/
│   ├── dem_mosaic.tif            # Mosaicked DEM (EPSG:4326, 30m, 1 arc-sec)
│   ├── dem_cropped.tif           # Cropped to AOI + buffer (EPSG:4326, 30m)
│   ├── river_source_mask.tif     # River source mask (bool, same grid as DEM)
│   ├── model_output/
│   │   ├── flood_wl_XX.tif       # Flood extent per water level (bool, same grid)
│   │   └── ...
│   └── reference/
│       └── reference_mask.tif    # Rasterized reference (1=inundated, 0=dry, NaN=outside)
├── runs/
│   ├── manifest_<timestamp>.json  # Run manifest (see §5)
│   └── metrics_<timestamp>.json   # Metrics JSON (see §6)
└── reports/
    └── report_<timestamp>.md      # Human-readable report
```

**Git policy:** `data/raw/`, `data/processed/`, `data/rivers/`, `runs/`, `reports/` are gitignored. Only `data/raw/dem/` metadata (manifest.json, SHA256) and code are tracked.

---

## 3. Versioned Run Configuration

A YAML/JSON configuration file fully specifies a replay run:

```yaml
# config/replay_v1.yaml
version: "1.0"
run_id: "replay_20261026_001"           # auto-generated if omitted
code_commit: "auto"                      # git commit SHA
timestamp: "2026-10-26T12:00:00Z"        # ISO 8601 UTC

# AOI — provisional, pending NRSC validation
aoi:
  min_lon: 80.5
  min_lat: 16.3
  max_lon: 81.2
  max_lat: 16.7
  buffer_km: 2.0                         # buffer for crop

# DEM configuration
dem:
  tiles: ["N16E080", "N16E081"]
  source: "s3://copernicus-dem-30m/"
  nodata_sentinel: -32768                # from HEM auxiliary files
  output_nodata: -32767                  # written by preprocessing

# Common grid specification
grid:
  crs: "EPSG:4326"
  resolution_arcsec: 1                   # 1 arc-second ≈ 30m
  alignment: "arcsec_grid"               # snap to 1/3600° boundaries
  resampling:
    dem: "bilinear"
    mask: "nearest"
    reference: "nearest"

# River source mask
river_source:
  source: "OSM"                          # or "HydroSHEDS"
  buffer_m: 90                           # buffer river polyline by 3 cells
  min_stream_order: 3                    # filter minor tributaries

# Water level scenarios
water_levels:
  - mode: "sweep"
    min: 5.0
    max: 30.0
    step: 0.5
    unit: "meters"                       # EGM2008 orthometric
  # - mode: "gauge"
  #   station: "Vijayawada_CWC"
  #   date: "2024-09-13"
  #   datum: "EGM2008"

# Evaluation
evaluation:
  metrics: ["iou", "precision", "recall", "f1", "area_ratio"]
  area_weighting: "latitude_aware"       # cos(lat) correction
  undefined_denominator: "report_as_null" # not zero
  valid_intersection_only: true          # TP/FP/FN/TN over valid ∩ valid

# Output artifacts
output:
  raster_comparison: true
  visualization: true                    # TP=green, FP=red, FN=blue
  metrics_json: true
  run_manifest: true
  report_markdown: true
```

---

## 4. Preflight Checks (Before Model Run)

Before `compute_flood_extent()` is called, verify:

| Check | Implementation | Failure Action |
|-------|----------------|----------------|
| DEM & reference same CRS | `dem.crs == ref.crs` | Abort |
| DEM & reference same transform | `dem.transform == ref.transform` | Abort |
| DEM & reference same shape | `dem.shape == ref.shape` | Abort |
| DEM & source mask same shape | `dem.shape == mask.shape` | Abort |
| DEM & reference same valid-data interpretation | `dem.nodata == ref.nodata` (or both None) | Warn + proceed |
| DEM valid pixel count > 0 | `dem_valid.sum() > 0` | Abort |
| Reference has both classes | `ref_flooded.sum() > 0 and ref_dry.sum() > 0` | Warn |
| River source mask has True pixels | `mask.sum() > 0` | Abort |
| Water level finite & reasonable | `np.isfinite(wl) and 0 < wl < 100` | Abort |

**Implementation:** `src/kshitij_model/validation.py` — `validate_preflight(dem, ref, mask, water_level, config)`

---

## 5. Run Manifest

```json
{
  "run_id": "replay_20261026_001",
  "code_commit": "a1b2c3d4",
  "timestamp": "2026-10-26T12:00:00Z",
  "config_hash": "sha256:abc123...",
  "inputs": {
    "dem_tiles": [
      {"tile_id": "N16E080", "sha256": "abc...", "path": "data/raw/dem/N16E080.tif"},
      {"tile_id": "N16E081", "sha256": "def...", "path": "data/raw/dem/N16E081.tif"}
    ],
    "reference_raster": {"path": "data/processed/reference/reference_mask.tif", "sha256": "..."},
    "river_source": {"path": "data/rivers/krishna_river.gpkg", "sha256": "..."}
  },
  "processing": {
    "dem_mosaic": {"sha256": "...", "shape": [3600, 7200], "transform": [...], "crs": "EPSG:4326"},
    "dem_cropped": {"sha256": "...", "shape": [1440, 2880], "transform": [...], "bounds": [80.3, 16.1, 81.4, 16.9]},
    "river_source_mask": {"sha256": "...", "true_pixels": 15420}
  },
  "model": {
    "water_levels": [5.0, 5.5, ..., 30.0],
    "river_source_method": "OSM_buffer_90m",
    "nodata_policy": {"dem_sentinel": -32768, "output_nodata": -32767}
  },
  "grid": {
    "crs": "EPSG:4326",
    "resolution_arcsec": 1,
    "transform": [0.00027778, 0.0, 80.3, 0.0, -0.00027778, 16.9]
  },
  "timestamp": "2026-10-26T12:34:56Z"
}
```

---

## 6. Evaluation Metrics

### 6.1 Valid Intersection

Only pixels where **both** model and reference have valid data contribute:

```python
valid = model_valid_mask & ref_valid_mask
tp = (model_flooded & ref_flooded & valid).sum()
fp = (model_flooded & ~ref_flooded & valid).sum()
fn = (~model_flooded & ref_flooded & valid).sum()
tn = (~model_flooded & ~ref_flooded & valid).sum()
```

### 6.2 Metric Formulas

| Metric | Formula | Undefined Denominator |
|--------|---------|----------------------|
| IoU (Jaccard) | `tp / (tp + fp + fn)` | Return `null` if `tp+fp+fn == 0` |
| Precision | `tp / (tp + fp)` | Return `null` if `tp+fp == 0` |
| Recall (Sensitivity) | `tp / (tp + fn)` | Return `null` if `tp+fn == 0` |
| F1-Score | `2 * P * R / (P + R)` | Return `null` if `P+R == 0` |
| Area Ratio | `(tp + fp) * cell_area / (tp + fn) * cell_area` | Return `null` if `tp+fn == 0` |

**Area weighting:** `cell_area = (111320)^2 * cos(lat_rad) * (1/3600)^2` m² per pixel. Compute per-row latitude.

**Undefined denominators:** Return `null` (not 0, not 1). Report in JSON as `null`.

### 6.3 Output Artifacts

| Artifact | Format | Description |
|----------|--------|-------------|
| Comparison raster | GeoTIFF | 4-band: TP=green(1), FP=red(2), FN=blue(3), TN=gray(4) |
| Visualization | PNG | RGB composite with legend |
| Metrics | JSON | Per water level + aggregate |
| Run manifest | JSON | Full reproducibility record |
| Report | Markdown | Human-readable summary |

---

## 7. Tests Required Before Trusting Pipeline

| Test | Description | Implementation |
|------|-------------|----------------|
| Synthetic all-dry | Reference all dry → model should produce no flood | `test_replay_alldry()` |
| Synthetic all-flooded | Reference all flooded → model should flood all valid | `test_replay_allflooded()` |
| NoData boundary | Reference has NoData fringe → excluded from counts | `test_nodata_boundary()` |
| All-dry reference + all-flooded model | Precision = 0, Recall = 1 | `test_mismatch_alldry_allflooded()` |
| Empty positive class | TP+FP=0 or TP+FN=0 → metrics null | `test_empty_positive_class()` |
| Mismatched grid detection | Different transform → preflight abort | `test_mismatched_grid_abort()` |
| NoData boundary exclusion | NoData pixels excluded from TP/FP/FN/TN | `test_nodata_excluded()` |
| Deterministic repeat | Same config → identical flood extent | `test_deterministic_repeat()` |
| Area weighting | Area ratio matches latitude-weighted sum | `test_area_weighting()` |
| Undefined denominator handling | Metrics null, not zero | `test_undefined_denominator()` |

---

## 8. Acceptance Criteria

| Criterion | Threshold |
|-----------|-----------|
| All preflight checks pass | 100% |
| Deterministic repeat | Bitwise identical flood extent for same config |
| Metrics computed without error | No exceptions |
| Undefined denominators → `null` | No `ZeroDivisionError` |
| Area ratio physically plausible | 0.1 < ratio < 10 for reasonable WL |
| Run manifest complete | All fields populated, hashes match |
| Visualization generated | PNG + GeoTIFF saved |

---

## 9. Implementation Checklist (Incremental)

| Step | Task | Depends On | Est. Effort |
|------|------|------------|-------------|
| 1 | `validation.py` — preflight checks | — | S |
| 2 | `prepare_model_input` alignment check | validation.py | S |
| 3 | River source mask generator (OSM/HydroSHEDS) | — | M |
| 4 | Replay CLI (`replay.py` — config-driven) | validation, mask gen | M |
| 5 | Metrics module (IoU, P, R, F1, area) | — | S |
| 6 | Run manifest writer | replay.py | S |
| 7 | Comparison raster writer (4-band) | replay.py | S |
| 8 | Visualization (PNG + GeoTIFF) | metrics, replay.py | M |
| 9 | Report generator (Markdown) | metrics, manifest | S |
| 10 | Sweep mode (water level range) | replay.py | S |
| 11 | Gauge mode (CWC stage data) | — | M (external) |
| 12 | Test suite (synthetic + edge cases) | all above | M |
| 13 | Full replay with Sep 2024 data | 1-12 | L |

---

## 10. Water Level: Sweep vs. Stage-Supported

| Mode | Description | Validity |
|------|-------------|----------|
| **Sweep** | Test WL range, pick max IoU | Post-hoc fitting only — **not predictive** |
| **Gauge** | Use observed CWC stage on 13 Sep 2024 | Predictive — requires CWC data |

**Policy:** Any reported IoU from sweep mode must be labeled "post-hoc best-fit, not predictive." Stage-supported scenario is the only predictive claim.

---

## 11. Limitations & Caveats

| Limitation | Impact |
|------------|--------|
| DSM not DTM | Buildings/vegetation elevate DEM → underpredicts urban flooding |
| Single water level | Steady-state only; no temporal dynamics |
| No infiltration/breach physics | Threshold connectivity only |
| Reference map timing | Single snapshot (13 Sep) vs. event duration |
| SAR interpretation | Rain ponds, wet vegetation, urban specular = false positives |
| Vertical datum mismatch | DEM=EGM2008, gauge datum unknown |
| Reference map CRS | Unverified (assumed EPSG:4326) |

---

## 12. Acceptance Criteria for M1.4 Completion

| Criterion | Status |
|-----------|--------|
| All preflight checks implemented | ☐ |
| River source mask generator working | ☐ |
| Replay CLI runs sweep mode end-to-end | ☐ |
| Metrics match manual calculation on synthetic cases | ☐ |
| Run manifest complete and reproducible | ☐ |
| Comparison artifacts generated | ☐ |
| Test suite passes (synthetic + edge) | ☐ |
| Documentation updated (README, usage) | ☐ |

---

*End of Specification — No validation executed*