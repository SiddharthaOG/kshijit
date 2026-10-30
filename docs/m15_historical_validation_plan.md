# Kshitij M1.5 — Historical Flood Validation

## A. Objective and Scope

**Historical event:** September 13, 2024, Vijayawada (Krishna River) flooding  
**Reference source:** ISRO/NRSC flood inundation map (`AP_2024_13_09_Map.pdf`) from APSAC  
**Model source:** M1.4 real-DEM threshold-connectivity flood extent pipeline (`kshitij_model.pipeline.run_pipeline`)

**Scope:** This milestone executes the validation specified in M1.3 (`docs/m13_historical_validation_plan.md`) using the operational M1.4 pipeline. The objective is to produce a documented, reproducible spatial comparison between the model's potential flood extent and the observed SAR inundation extent.

**Deliverables:**
- Georeferenced, digitised reference inundation mask (GeoTIFF)
- M1.4 model output for the historical AOI (GeoTIFF)
- Common-grid alignment and valid-intersection mask
- Confusion matrix (TP, FP, FN, TN), IoU, Precision, Recall, F1, Area Ratio
- Visual comparison composite (TP=green, FP=red, FN=blue)
- Reproducible metrics report (JSON) with all configuration parameters

**Out of scope for M1.5:**
- Hydrodynamic model integration
- Water-level calibration from gauge data (separate investigation)
- Predictive accuracy claims — this is a plausibility comparison for a single hypothetical water level
- Time-evolving validation (reference is a single snapshot)

---

## B. Data Inventory

### Confirmed Available Assets

| Asset | Location | Format | Status |
|-------|----------|--------|--------|
| Copernicus DEM GLO-30 tiles (N16E079, N16E080, N16E081) | `data/raw/dem/` | GeoTIFF | ✅ Downloaded |
| M1.4 pipeline implementation | `src/kshitij_model/pipeline.py` | Python | ✅ Complete |
| M1.3 validation plan | `docs/m13_historical_validation_plan.md` | Markdown | ✅ Complete |

### Assets Requiring Acquisition / Preparation

| Asset | Source | Format | Status |
|-------|--------|--------|--------|
| NRSC reference map (`AP_2024_13_09_Map.pdf`) | APSAC (https://apsac.ap.gov.in/?page_id=7156) | PDF | ⬜ Not yet acquired |
| Georeferenced reference inundation mask | Derived from PDF | GeoTIFF | ⬜ Pending digitisation |
| Krishna River vector (OSM/HydroSHEDS) | OSM / HydroSHEDS | GeoJSON / GPKG | ⬜ Not yet extracted |
| Krishna River gauge stage (13 Sep 2024) | CWC / Andhra Pradesh WRD | Time series (m) | ⬓ Unknown availability |

### Required Metadata & Provenance

For reproducibility, the following must be recorded:
- DEM tiles used, CRS, resolution, NoData sentinel
- River vector source, extraction method, CRS, buffer applied
- Water level(s) tested, vertical datum (EGM2008 vs. gauge)
- AOI bounds, common grid specification, resampling method
- Reference map georeferencing GCPs, RMSE, digitisation method
- Software versions, random seeds (if any), hardware

---

## C. Reference Map Preparation

### Current State
- Source file: `AP_2024_13_09_Map.pdf` (952 KB, downloaded from APSAC)
- Not yet georeferenced
- Not yet digitised

### Georeferencing Workflow

1. **Open PDF in QGIS** (or GDAL/rasterio + ground control points)
2. **Identify GCPs** from:
   - Known landmarks (bridges, road intersections, city boundaries)
   - Lat/lon grid lines printed on map (if present)
   - Cross-reference with OpenStreetMap / satellite imagery
3. **Minimum 4 GCPs** (prefer 6–8) distributed across map extent
4. **Target CRS:** EPSG:4326 (WGS84) — matches DEM
5. **Record GCP residuals** and overall RMSE; target ≤ 1 pixel (≈30 m)

### Digitisation

1. **Trace inundation boundary** as polygon vector (shapefile/GeoJSON)
2. **Rasterise to binary mask** aligned to common grid (1 arc-second, EPSG:4326)
3. **Encoding:** 1 = inundated, 0 = dry, NaN = outside AOI / no data
4. **Save as GeoTIFF** with valid-data mask

### Output Location

- `data/reference/AP_2024_13_09_Map.georeferenced.tif` (georeferenced PDF)
- `data/reference/inundation_mask.tif` (binary raster mask)
- `data/reference/inundation_polygon.geojson` (vector)
- `data/reference/georeferencing_gcps.csv` (GCP coordinates, residuals)

### Limitations to Document

- Georeferencing error (GCP RMSE) → spatial uncertainty in reference mask
- SAR classification ambiguity (wet vegetation, specular surfaces)
- Timing: reference is 13 Sep snapshot; model is steady-state
- Reference includes all surface water (flood + rain ponds + specular)

---

## D. Spatial Alignment

### Common Grid Specification

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **CRS** | EPSG:4326 (WGS84) | Matches DEM native CRS |
| **Resolution** | 1 arc-second (≈30 m at equator) | Copernicus DEM GLO-30 native |
| **Alignment** | Snapped to 1/3600° grid | Avoids resampling artifacts |
| **Extent** | AOI bounds from digitised reference + 1–2 km buffer | Covers full inundation |
| **Resampling** | Nearest-neighbor (both model & reference masks) | Preserves binary class integrity |

### Alignment Procedure

1. **Model output:** M1.4 pipeline writes `flood_extent.tif` in EPSG:4326 at 1 arc-second
2. **Reference mask:** Rasterised to identical grid using nearest-neighbor
3. **Valid intersection:** `valid = model_valid_mask & reference_valid_mask`
4. **NoData handling:** Cells with NoData in either layer excluded from metrics

### Area Calculations

Since EPSG:4326 is geographic, convert pixel counts to area using latitude-dependent cell area:
```
cell_area_m2 ≈ (111320)² × cos(lat_rad) × (1/3600)²
```
Or reproject both masks to equal-area CRS (e.g., EPSG:6933) for area metrics.

---

## E. Water-Level and Event Assumptions

### Water Level Input

The M1.4 pipeline requires a single `water_level` threshold (meters, EGM2008 datum). Two approaches:

| Approach | Description | Status |
|----------|-------------|--------|
| **A. Post-hoc sweep** | Sweep water levels (e.g., 5–30 m in 0.5 m steps), select max IoU | ✅ Feasible now |
| **B. Gauge-based** | Use observed Krishna River stage at Vijayawada on 13 Sep 2024 | ⬓ Unknown availability |

**Vertical datum compatibility:** Copernicus DEM = EGM2008 orthometric. River gauge datum must be confirmed (typically MSL/EGM2008 in India). If gauge uses different datum, a conversion is required.

### Calibration vs. Evaluation Distinction

- **Calibration:** Choosing water level to maximise IoU (post-hoc fitting)
- **Evaluation:** Using independently observed water level

M1.5 will use **Approach A (post-hoc sweep)** as primary, with clear documentation that this is calibration, not independent prediction. If gauge data becomes available, Approach B will be added as a separate evaluation.

---

## F. Validation Metrics

### Contingency Table (over valid intersection only)

| | Reference Inundated | Reference Dry |
|---|---|---|
| **Model Flooded** | TP | FP |
| **Model Dry** | FN | TN |

**Valid intersection:** `valid = model_valid_mask & reference_valid_mask`

### Metric Definitions

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **IoU (Jaccard)** | TP / (TP + FP + FN) | Spatial overlap of flooded/inundated areas |
| **Precision** | TP / (TP + FP) | Of model-flooded cells, fraction actually inundated |
| **Recall (Sensitivity)** | TP / (TP + FN) | Of reference-inundated cells, fraction captured by model |
| **F1-Score** | 2 × P × R / (P + R) | Harmonic mean of precision and recall |
| **Inundated Area Ratio** | (TP + FP) / (TP + FN) | >1 = overprediction, <1 = underprediction |

### Output Format

```json
{
  "event": "2024-09-13 Vijayawada",
  "model_config": {
    "water_level_m": 15.0,
    "river_buffer_m": 30.0,
    "dem_tiles": ["N16E079", "N16E080", "N16E081"],
    "aoi_bounds_wgs84": [80.5, 16.3, 81.2, 16.7]
  },
  "reference": {
    "source": "ISRO/NRSC AP_2024_13_09_Map.pdf",
    "georeferencing_rmse_m": 15.2,
    "digitisation_method": "manual polygon in QGIS"
  },
  "grid": {
    "crs": "EPSG:4326",
    "resolution_arcsec": 1,
    "valid_pixels": 1234567
  },
  "metrics": {
    "tp": 45231,
    "fp": 12845,
    "fn": 8932,
    "tn": 987654,
    "iou": 0.682,
    "precision": 0.778,
    "recall": 0.835,
    "f1": 0.805,
    "area_ratio": 1.15
  }
}
```

---

## G. Limitations

| Category | Limitation | Impact on Metrics |
|----------|------------|-------------------|
| **Timing** | Reference = 13 Sep snapshot; Model = steady-state | FP/FN inflated by timing mismatch |
| **SAR Interpretation** | SAR detects all surface water (flood + rain ponds) | FP inflated in urban/vegetated areas |
| **DSM vs DTM** | Copernicus DEM = DSM (buildings/vegetation) | Underpredicts urban flooding (FN) |
| **Resolution** | 30 m DEM vs ~10–30 m SAR | Urban drainage (<30 m) not resolved |
| **Vertical Datum** | DEM = EGM2008; gauge datum unknown | Water level may not match DEM datum |
| **Hydraulic Physics** | Threshold connectivity ≠ hydrodynamics | No flow routing, infiltration, breaches |
| **River Source Mask** | Manual vector; no auto OSM/HydroSHEDS yet | Source mask errors propagate |
| **Water Level** | Single threshold vs time-varying stage | Cannot match time-specific snapshot |
| **Georeferencing** | PDF-to-raster introduces spatial error | Reference mask shifted by ~10–30 m |

> **Critical framing:** This comparison is a **plausibility check for a single hypothetical water level**, not proof of predictive accuracy. Without time-series gauge data and multi-event validation, no predictive claims are justified.

---

## H. Acceptance Criteria

### Measurable Deliverables

- [ ] `data/reference/inundation_mask.tif` — georeferenced, digitised binary mask
- [ ] `data/validation/model_output.tif` — M1.4 output for historical AOI
- [ ] `data/validation/valid_intersection_mask.tif` — valid intersection
- [ ] `data/validation/metrics.json` — complete metrics report (see §F)
- [ ] `data/validation/comparison_rgb.tif` — visual composite (TP=green, FP=red, FN=blue)
- [ ] All configuration parameters recorded in `metrics.json`

### Reproducibility Requirements

- [ ] Single script/command reproduces entire validation workflow
- [ ] All random seeds fixed (if any stochastic components)
- [ ] Software versions pinned in `requirements.txt` or `pyproject.toml`
- [ ] Intermediate artifacts saved for inspection

### Numeric Thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| IoU | TBD — requires project approval | ⬜ Pending |
| Precision | TBD | ⬜ Pending |
| Recall | TBD | ⬜ Pending |

> **Note:** No arbitrary minimum IoU is defined without domain justification. Thresholds require stakeholder approval.

---

## I. Implementation Sequence

### Task 1: Reference Map Acquisition & Digitisation (1–2 days)
- [ ] Download `AP_2024_13_09_Map.pdf` from APSAC
- [ ] Georeference in QGIS (4+ GCPs, record RMSE)
- [ ] Digitise inundation polygon
- [ ] Rasterise to 1 arc-second binary mask
- [ ] Save artifacts to `data/reference/`

### Task 2: River Vector Extraction (0.5 days)
- [ ] Extract Krishna River polyline from OSM (Overpass API) or HydroSHEDS
- [ ] Clip to AOI + buffer
- [ ] Save to `data/validation/krishna_river.geojson`

### Task 3: M1.4 Model Run for Historical AOI (0.5 days)
- [ ] Define AOI from digitised reference extent + 2 km buffer
- [ ] Run `run_pipeline` with water-level sweep (5–30 m, 0.5 m steps)
- [ ] Save all outputs to `data/validation/`

### Task 4: Spatial Alignment & Metrics (1 day)
- [ ] Align model outputs and reference to common grid
- [ ] Compute valid intersection mask
- [ ] Calculate TP, FP, FN, TN for each water level
- [ ] Compute IoU, Precision, Recall, F1, Area Ratio
- [ ] Generate visual comparison RGB composite
- [ ] Save `metrics.json` with full provenance

### Task 5: Documentation & Reporting (0.5 days)
- [ ] Record all parameters, limitations, assumptions
- [ ] Produce summary report (Markdown + JSON)
- [ ] Archive all intermediate artifacts

---

## J. Open Questions and Blockers

| # | Question | Impact | Resolution Path |
|---|----------|--------|-----------------|
| 1 | Is Krishna River gauge stage for 13 Sep 2024 available? | Enables Approach B (gauge-based) vs. only Approach A (sweep) | Contact CWC / AP WRD; check public portals |
| 2 | Does NRSC PDF contain lat/lon grid or known landmarks? | Affects georeferencing accuracy | Inspect PDF in QGIS |
| 3 | Is reference map extent fully within 3 acquired DEM tiles? | May need additional tiles (N15E080, N15E081, N17E080, N17E081) | Digitise extent first, then check |
| 4 | Does Copernicus DEM EGM2008 vertical datum match Indian gauge datum? | Required for meaningful water-level comparison | Verify with CWC metadata |
| 5 | Can river vector be reliably auto-extracted from OSM? | Manual extraction needed if not | Test Overpass API query |
| 6 | What IoU threshold constitutes "acceptable" for this use case? | Defines acceptance criteria | Requires stakeholder input |

---

## Data Directory Structure & Purpose

```
data/
├── reference/                 # NRSC reference map & derived products
│   ├── AP_2024_13_09_Map.pdf              # Original source (not in git)
│   ├── AP_2024_13_09_Map.georeferenced.tif # Georeferenced PDF
│   ├── inundation_mask.tif                 # Binary raster mask (1=inundated)
│   ├── inundation_polygon.geojson          # Digitised vector polygon
│   ├── georeferencing_gcps.csv             # GCP coordinates & residuals
│   └── .gitkeep
├── validation/                # Validation inputs & intermediate artifacts
│   ├── krishna_river.geojson               # River vector for model
│   ├── model_output_wl_15.0.tif            # M1.4 output at specific WL
│   ├── model_output_wl_15.5.tif            # ... (sweep outputs)
│   ├── valid_intersection_mask.tif         # model_valid & ref_valid
│   ├── comparison_rgb.tif                  # TP=green, FP=red, FN=blue
│   ├── metrics.json                        # Complete metrics report
│   └── .gitkeep
└── processed/
    └── validation/             # Final validated products (if promoted)
        └── .gitkeep
```

**Note:** Large raster files (DEM tiles, model outputs, reference masks) are excluded from git via `.gitignore`. Only metadata, vectors, and small artifacts are tracked.

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-30 | — | Initial M1.5 plan derived from M1.3 & M1.4 |

---

## References

- M1.3 Historical Validation Plan: `docs/m13_historical_validation_plan.md`
- M1.4 Implementation Plan: `docs/m14_implementation_plan.md`
- ISRO/NRSC APSAC Flood Mapping: https://apsac.ap.gov.in/?page_id=7156
- Copernicus DEM GLO-30: https://registry.opendata.aws/copernicus-dem/