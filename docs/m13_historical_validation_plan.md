# Kshitij M1.3 — Historical Validation Plan

## Objective

Compare Kshitij's simulated flood extent against the September 2024 Vijayawada inundation reference (ISRO/NRSC AP_2024_13_09_Map.pdf) to produce a documented, reproducible Intersection-over-Union (IoU) and derived metrics. This plan is a **specification only** — no validation has been executed.

---

## 1. Reference Data

| Attribute | Detail | Source |
|-----------|--------|--------|
| **Product** | ISRO/NRSC September 2024 Flood Inundation Map (Andhra Pradesh) | APSAC |
| **Publication date** | 13 September 2024 | APSAC collection |
| **File** | `AP_2024_13_09_Map.pdf` (952 KB) | Downloaded from https://apsac.ap.gov.in/?page_id=7156 |
| **Sensor / Method** | SAR-based (likely Sentinel-1 or RISAT-1A) rapid flood mapping | ISRO/NRSC standard practice |
| **Mapped phenomenon** | **Observed surface water extent** (inundation + accumulated rainwater pools) — not modelled flood extent | ISRO/NRSC rapid mapping products |
| **Projection / CRS** | Not explicitly stated in PDF; likely WGS84 (EPSG:4326) or UTM zone 44N | To be verified during digitisation |
| **Spatial resolution** | ~10–30 m (typical for Sentinel-1 GRD / RISAT) | Estimate; to be verified |
| **Vertical datum** | N/A (inundation extent only) | — |

### Key Limitations

- **Not ground truth**: Satellite SAR detects surface water (inundation + rainwater pools + specular surfaces). It does not distinguish river flooding from local ponding.
- **Timing mismatch**: Map represents a single snapshot (13 Sep 2024). Kshitij model simulates steady-state flood extent for a given water level, not a time-evolving event.
- **Registration uncertainty**: PDF-to-raster georeferencing introduces spatial error (estimated 10–30 m depending on ground control points).
- **Classification ambiguity**: SAR backscatter thresholds may misclassify wet vegetation, smooth bare soil, or urban surfaces as water.
- **No depth information**: Reference provides binary inundation mask only; no water depth for model calibration.

> **Distinction**: The reference map shows **observed inundation** (what was wet on 13 Sep 2024). Kshitij's model computes **potential flood extent** for a given water level threshold and river-source mask. They are fundamentally different products; comparison is a plausibility check, not proof of predictive accuracy.

---

## 2. Area of Interest (AOI)

### Proposed Provisional AOI

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Name** | Vijayawada / Krishna River Corridor | Covers urban flood impact zone |
| **Center** | ~16.5062° N, 80.6480° E | Vijayawada city center |
| **Provisional bounds (WGS84 / EPSG:4326)** | 80.5° E – 81.2° E, 16.3° N – 16.7° N | Covers Krishna River through Vijayawada urban extent |
| **CRS** | EPSG:4326 (WGS84) | Matches DEM and reference map |
| **Dimensions** | ~0.7° × 0.4° ≈ 77 km × 44 km | Covers urban floodplain |
| **Area** | ~3,400 km² | — |

### DEM Tile Coverage Verification

| Tile | Bounds (EPSG:4326) | Covers AOI? |
|------|-------------------|-------------|
| N16E079 | 79°E–80°E, 16°N–17°N | Partial (western edge) |
| N16E080 | 80°E–81°E, 16°N–17°N | **Full coverage (core)** |
| N16E081 | 81°E–82°E, 16°N–17°N | Partial (eastern edge) |

**Conclusion**: The 3 acquired tiles (N16E079, N16E080, N16E081) **cover the provisional AOI**, but the AOI extends slightly beyond N16E080 into adjacent tiles. The final AOI should be refined by digitising the NRSC reference map extent and intersecting with available DEM tiles.

### Uncertainty

- **AOI is provisional**: Final bounds must be derived by digitising the NRSC reference map's inundation extent and adding a 1–2 km buffer.
- **Tile completeness**: If the digitised extent extends beyond the 3 acquired tiles, additional tiles (N15E080, N15E081, N17E080, N17E081) may be needed.

---

## 3. Raster Preparation (Common Grid)

All rasters (DEM, model output, reference inundation) must share a common grid before comparison.

### Target Grid Specification

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **CRS** | EPSG:4326 (WGS84) | Matches DEM and reference PDF georeferencing |
| **Resolution** | 30 m (1 arc-second) | Matches Copernicus DEM GLO-30 native resolution |
| **Grid alignment** | Aligned to 1 arc-second grid (multiples of 1/3600°) | Avoids resampling artifacts |
| **Extent** | Final AOI bounds snapped to 30 m grid | Defined after reference digitisation |
| **Resampling** | Nearest-neighbor (reference), bilinear (DEM) | Preserves binary mask integrity |

### Valid-Data Mask & NoData Treatment

| Layer | NoData Value | Treatment |
|-------|--------------|-----------|
| **Copernicus DEM** | None declared in COG; auxiliary HEM suggests -32768 | Use `build_validity_mask()` with explicit `nodata=-32768` |
| **Model output** | -32767 (written by preprocessing) | Already masked |
| **Reference inundation** | PDF background / no-data | Digitise as binary mask (1=inundated, 0=dry, NaN=outside AOI) |

### Avoiding Invalid Cells Counted as Dry Land

When computing metrics, **only pixels where BOTH model and reference have valid data** should be included in the contingency table:

```python
# Pseudo-code
valid = model_valid_mask & reference_valid_mask
tp = (model_flooded & reference_flooded & valid).sum()
fp = (model_flooded & ~reference_flooded & valid).sum()
fn = (~model_flooded & reference_flooded & valid).sum()
tn = (~model_flooded & ~reference_flooded & valid).sum()
```

Cells outside the DEM extent or reference digitisation bounds are excluded from all counts.

---

## 4. Evaluation Metrics

### Definitions

| Class | Model | Reference |
|-------|-------|-----------|
| **Positive (Flooded/Inundated)** | Elevation ≤ water_level AND connected to river source | SAR-detected surface water |
| **Negative (Dry)** | Elevation > water_level OR not connected | SAR-classified dry land |

> **Critical distinction**: Model "flooded" = potential steady-state connectivity. Reference "inundated" = observed wet surface at one time. False positives may include areas hydraulically connected but not actually wet on 13 Sep 2024 (e.g., disconnected low-lying areas, timing differences).

### Metric Formulas

Let:
- TP = True Positives (model flooded ∩ reference inundated)
- FP = False Positives (model flooded ∩ reference dry)
- FN = False Negatives (model dry ∩ reference inundated)
- TN = True Negatives (model dry ∩ reference dry)

All computed over the **valid intersection** (`valid = model_valid & ref_valid`).

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **IoU (Jaccard)** | TP / (TP + FP + FN) | Spatial overlap of flooded/inundated areas |
| **Precision** | TP / (TP + FP) | Of model-flooded cells, fraction actually inundated |
| **Recall (Sensitivity)** | TP / (TP + FN) | Of reference-inundated cells, fraction captured by model |
| **F1-Score** | 2 × Precision × Recall / (Precision + Recall) | Harmonic mean |
| **Inundated Area Ratio** | Model flooded area / Reference inundated area | >1 = overprediction, <1 = underprediction |

### Coverage Differences

If model coverage ≠ reference coverage (different AOI bounds), compute metrics **only over the intersection of valid data**. Report the area of the valid intersection as context.

---

## 5. Limitations & Caveats

| Category | Limitation | Impact on Metrics |
|----------|------------|-------------------|
| **Timing** | Reference = 13 Sep snapshot; Model = steady-state for arbitrary water level | FP/FN inflated by timing mismatch; cannot calibrate water level from single snapshot |
| **SAR Interpretation** | SAR detects all surface water (flood + rain ponds + wet vegetation) | FP inflated in urban/vegetated areas; FN in dense canopy |
| **DSM vs DTM** | Copernicus DEM = DSM (includes buildings/vegetation) | Overestimates elevation in built-up areas → underpredicts urban flooding (FN) |
| **Resolution** | 30 m DEM vs ~10–30 m SAR | Urban drainage (<30 m) not resolved; embankments not captured |
| **Vertical Datum** | DEM = EGM2008 orthometric; Water level = ? | Water level must be in same vertical datum for meaningful comparison |
| **Hydraulic Physics** | Threshold connectivity ≠ hydrodynamic model | No flow routing, no infiltration, no breach modeling |
| **River Source Mask** | Requires manual/automated river delineation | Source mask errors propagate to all metrics |
| **Water Level** | Single threshold vs time-varying stage | Model cannot match time-specific snapshot without stage hydrograph |

> **No calibration claimed**: Without a time series of observed stages and inundation extents, water level cannot be objectively calibrated. Any IoU reported is for a *hypothetical* water level chosen to maximise overlap (post-hoc fitting), not a predictive result.

---

## 6. Execution Checklist

### Phase A: Data Acquisition & Preparation
- [ ] **Digitise NRSC reference map** (`AP_2024_13_09_Map.pdf`)
  - [ ] Georeference PDF in QGIS (identify 4+ GCPs from known landmarks / grid lines)
  - [ ] Digitise inundation polygon (vector)
  - [ ] Rasterise to 30 m binary mask aligned to 1 arc-second grid
  - [ ] Save as GeoTIFF with valid-data mask (1=inundated, 0=dry, NaN=outside)
- [ ] **Verify DEM coverage**
  - [ ] Mosaic N16E079/080/081 with `mosaic_tiles()`
  - [ ] Crop mosaic to digitised AOI + 2 km buffer using `crop_raster()`
  - [ ] Inspect elevation range, NoData, valid pixel count
- [ ] **Generate river source mask**
  - [ ] Extract Krishna River polyline from OSM or HydroSHEDS within AOI
  - [ ] Rasterise to 30 m boolean mask (1 = river cell)
  - [ ] Optionally buffer by 30–90 m to account for DEM vertical error

### Phase B: Model Configuration
- [ ] **Select water level(s) to test**
  - [ ] Approach A: Sweep water levels (e.g., 5–30 m in 0.5 m steps) to find max IoU (post-hoc)
  - [ ] Approach B: Use observed Krishna River stage at Vijayawada gauge on 13 Sep 2024 (if available)
  - [ ] Document chosen approach clearly
- [ ] **Run model** using `prepare_model_input()` + `compute_flood_extent()`
  - [ ] Pass DEM elevation array, river source mask, water level, NoData=-32768
  - [ ] Obtain boolean flood extent array

### Phase C: Comparison & Metrics
- [ ] **Align rasters** (model output, reference mask) to common grid
- [ ] **Compute valid intersection mask**
- [ ] **Calculate TP, FP, FN, TN** over valid intersection
- [ ] **Compute IoU, Precision, Recall, F1, Area Ratio**
- [ ] **Generate visual comparison** (RGB composite: TP=green, FP=red, FN=blue)

### Phase D: Reporting
- [ ] **Record all parameters**: water level, source mask method, grid spec, AOI bounds
- [ ] **Report all metrics** with 95% confidence intervals (bootstrap if needed)
- [ ] **Document limitations** per Section 5
- [ ] **Save artifacts**: model output GeoTIFF, reference mask GeoTIFF, metrics JSON
- [ ] **Do not claim predictive validation** — frame as "plausibility comparison for a single hypothetical water level"

---

## Sources & References

| # | Source | Accessed | Notes |
|---|--------|----------|-------|
| [1] | APSAC Flood Mapping: https://apsac.ap.gov.in/?page_id=7156 | 2026-10-23 | Official collection page |
| [2] | AP_2024_13_09_Map.pdf | 2026-10-23 | Downloaded from APSAC |
| [3] | Copernicus DEM GLO-30: https://registry.opendata.aws/copernicus-dem/ | 2026-10-23 | AWS Open Data Registry |
| [4] | Copernicus DEM GLO-30 Product Handbook | 2026-10-23 | Technical specs |
| [5] | ISRO Bhuvan: https://bhuvan.nrsc.gov.in/ | 2026-10-23 | Official geoportal |
| [6] | Kshitij repository: `src/kshitij_model/` | 2026-10-26 | Current implementation |

---

## Unresolved Assumptions (Require Confirmation)

| # | Assumption | Status |
|---|------------|--------|
| 1 | NRSC map CRS is WGS84 / EPSG:4326 | **Unverified** — must check PDF metadata or GCPs |
| 2 | Krishna River gauge stage on 13 Sep 2024 is available | **Unknown** — need CWC/state data |
| 3 | Copernicus DEM EGM2008 vertical datum matches river gauge datum | **Unknown** — need gauge metadata |
| 4 | Reference map extent fully within 3 acquired DEM tiles | **Provisional** — depends on digitised extent |
| 5 | River source mask can be reliably derived from OSM/HydroSHEDS | **Planned** — not yet implemented |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-26 | Automated | Initial plan created |

> **Status**: This plan has **not been executed**. No validation results exist. All metrics, maps, and comparisons described are **planned only**.