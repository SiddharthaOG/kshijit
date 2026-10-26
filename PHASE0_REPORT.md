# Kshitij M1.2 — Phase 0 Preflight Report

## Executive Summary

The M1.2 milestone (Real DEM Acquisition, Raster Preprocessing & Model Integration) is ready to proceed. All prerequisites are satisfied:
- M1.1 flood-connectivity core is implemented and tested (42 tests pass)
- Docker/PostGIS configuration is ready (PostGIS image updated to 17-3.5-alpine)
- Copernicus DEM GLO-30 tiles for the Vijayawada study area are confirmed accessible via AWS S3
- ISRO/NRSC September 2024 flood reference map is accessible

> **Note**: The study extent defined below is **provisional** pending focused validation against the September 2024 NRSC inundation map. The current tile selection (N16E079, N16E080, N16E081) is based on preliminary geographic analysis of the Krishna River corridor through Vijayawada.

## 1. Study Area Definition

### Geographic Context
- **Location**: Vijayawada, Andhra Pradesh, India
- **Coordinates**: ~16.5062° N, 80.6480° E
- **Hydrology**: Krishna River flows through the city
- **Event**: September 2024 flood event (heavy rainfall + Krishna River flooding)

### Proposed Study Area Extent (Provisional)
Based on the flood event geography and DEM tile availability; **extent is provisional pending focused validation against the September 2024 NRSC reference map**:

| Priority | Tiles | Coverage | Rationale |
|----------|-------|----------|-----------|
| **Core (Required)** | N16E079, N16E080, N16E081 | 16°N–17°N, 79°E–81°E | Krishna River corridor through Vijayawada; covers flood-affected urban area |
| **Extended (Recommended)** | N15E079, N15E080, N15E081 | 15°N–16°N, 79°E–81°E | Upstream/downstream flood extent, rural areas |
| **Extended (Optional)** | N17E079, N17E080, N17E081 | 17°N–18°N, 79°E–81°E | Northern catchment areas |

**Recommended Minimum**: 3 core tiles (N16E079, N16E080, N16E081) covering ~3°×1° ≈ 100km × 110km covering the Krishna River corridor through Vijayawada. **Note**: Exact flood extent boundaries require validation against the September 2024 NRSC inundation map; the above tile selection is based on preliminary geographic analysis.

### Evidence for Extent
- **Reference Map**: ISRO/NRSC AP_2024_13_09_Map.pdf (13 Sept 2024) shows flood inundation along Krishna River through Vijayawada urban area
- **APSAC Collection**: https://apsac.ap.gov.in/?page_id=7156 confirms flood mapping products
- **Downloaded PDF**: AP_2024_13_09_Map.pdf (952 KB) successfully retrieved from APSAC

## 2. Copernicus DEM GLO-30 Availability

### Access Method
- **Source**: AWS Open Data Registry `s3://copernicus-dem-30m/`
- **Access**: Anonymous (unsigned) requests supported
- **Format**: Cloud Optimized GeoTIFF (COG) with auxiliary files
- **Tile Scheme**: 1°×1° tiles, naming `Copernicus_DSM_COG_10_N{lat:02d}_E{lon:03d}_00_DEM/`

### Tile Availability (Verified)
| Tile | DEM Size | Status |
|------|----------|--------|
| N16E080 (Vijayawada core) | 47.5 MB | ✅ Available |
| N16E079 | ~50 MB | ✅ Available |
| N16E081 | ~36 MB | ✅ Available |
| N15E079, N15E080, N15E081 | 47–51 MB | ✅ Available |
| N17E079, N17E080, N17E081 | 49–52 MB | ✅ Available |

All 9 tiles in the 3×3 grid (N15–N17, E079–E081) are accessible and contain complete COG structures with:
- Main DEM (`*_HEM.tif`): 36–52 MB (Hillshade Elevation Model)
- Auxiliary files: EDM (Ellipsoidal), FLM (Fluvial), HEM (Hillshade), WBM (Water Body), ACM (Accuracy), FLM/EDM metadata
- Metadata XML, EULA PDF, preview images

### Data Characteristics
- **Product**: Copernicus DEM GLO-30 Public (DSM, not bare-earth DTM)
- **Resolution**: 30m (1 arc-second)
- **Vertical Reference**: EGM2008 geoid (orthometric heights via EGGM)
- **Horizontal CRS**: WGS84 (EPSG:4326)
- **Licence**: Copernicus Free & Open Data Policy (CC BY 4.0 compatible)
- **Limitation**: DSM includes buildings/vegetation; not bare-earth DTM

## 3. PostGIS Configuration

### Current State
- **compose.yaml**: Uses `postgis/postgis:3.5-3.5-alpine` (incorrect tag)
- **Available Image**: `postgis/postgis:17-3.5-alpine` (PostgreSQL 17 + PostGIS 3.5) ✅ Verified available
- **Correction Needed**: Update `compose.yaml` to use `postgis/postgis:17-3.5-alpine`

### Docker/PostGIS Status
- Docker 29.8.2 available
- `postgis/postgis:17-3.5-alpine` pulled and verified
- Compose config validates (only deprecation warning for `version` attribute)

## 4. Implementation Plan & Risks

### Phase 1: DEM Acquisition (Week 1)
- [ ] Implement tile discovery from AWS S3 catalogue
- [ ] Download core 3 tiles (N16E079, N16E080, N16E081)
- [ ] Verify checksums and manifest generation
- [ ] Cache management with local storage

**Risks**: 
- Network reliability for ~150 MB total download
- AWS rate limits (mitigated by retries/backoff)
- DSM vs DTM limitation (documented, not blocking)

### Phase 2: Raster Preprocessing (Week 2)
- [ ] Raster inspection (CRS, bounds, transform, NoData)
- [ ] Crop to study area extent
- [ ] Validity mask preservation
- [ ] GeoTIFF + JSON manifest output

### Phase 3: Model Adapter (Week 3)
- [ ] Raster → array adapter with validity mask
- [ ] CRS/transform preservation for output georeferencing
- [ ] Integration with existing `compute_flood_extent`

### Phase 4: Testing (Week 3-4)
- Synthetic raster fixtures
- Property tests (monotonicity, validity, immutability)
- Adapter regression tests

### Phase 5-6: Documentation (Week 4)
- Update all docs with acquisition/processing details
- Storage portability configuration

## 5. Recommendations & Decisions Needed

1. **Study Area Confirmation**: Confirm 3-tile core (N16E079/E080/E081) is sufficient, or expand to 9-tile grid
2. **DSM vs DTM**: Document DSM limitation; consider void-filling or building removal in future
3. **Vertical Datum**: Confirm EGM2008 geoid is appropriate for flood modeling
4. **Tile Mosaicking**: Decide whether to mosaic tiles before or after cropping

## 6. Next Steps

1. ✅ Phase 0 complete — this report
2. → Create new feature branch for M1.2 implementation (Phases 1-6)
3. → Phase 1: Implement DEM acquisition module
4. → Phase 2: Implement raster preprocessing pipeline
5. → Phase 3: Build model adapter
6. → Phase 4: Offline tests
7. → Phase 5-6: Documentation & PR

---

**Prepared by**: Automated preflight analysis  
**Date**: 2025-10-23  
**Branch**: feat/m1-2-dem-preprocessing (at 738154b)  
**Base**: origin/master (ac6005f)