# Kshitij — Data Sources (Updated M1.2)

This document lists the data sources that Kshitij intends to use across its roadmap, with acquisition status updated after M1.2.

## 1. Open-Meteo Historical Rainfall

- **Purpose:** Historical rainfall series for replay-based flood estimation.
- **API:** https://open-meteo.com/en/docs#historical-weather
- **Constraints & Limitations:**
  - Coarse reanalysis data (tens of kilometres resolution).
  - Local extreme weather anomalies will be underestimated.
  - Free tier has rate limits; all results must be cached locally.
- **Planned usage:** Scripts in `scripts/` will fetch and parse historical rainfall for the September 2024 Vijayawada event.
- **Status:** *Planned* (M1+)

## 2. Copernicus DEM GLO-30 (Digital Surface Model)

- **Purpose:** Terrain elevation mapping for the threshold flood-connectivity model.
- **Source:** Copernicus DEM GLO-30 Public via AWS Open Data Registry
  - S3 Bucket: `s3://copernicus-dem-30m/`
  - Access: Anonymous (unsigned) requests supported
  - Format: Cloud Optimized GeoTIFF (COG) with auxiliary files
- **Tiles acquired (M1.2 Phase 1):**
  - N16E079 (42.9 MB) — `s3://copernicus-dem-30m/Copernicus_DSM_COG_10_N16_00_E079_00_DEM/`
  - N16E080 (47.5 MB) — `s3://copernicus-dem-30m/Copernicus_DSM_COG_10_N16_00_E080_00_DEM/`
  - N16E081 (35.8 MB) — `s3://copernicus-dem-30m/Copernicus_DSM_COG_10_N16_00_E081_00_DEM/`
- **Constraints & Limitations:**
  - **DSM, not bare-earth DTM:** Includes buildings, vegetation, and surface features.
  - Vertical resolution: ~30m horizontal (1 arc-second), vertical accuracy ~1-2m.
  - Unable to capture localized urban drainage networks or Krishna River embankments at this resolution.
  - Vertical datum: EGM2008 geoid (orthometric heights); horizontal: WGS84 (EPSG:4326).
  - NoData value not explicitly set in COG metadata; auxiliary HEM files indicate nodata as -32768.
  - Data coverage complete for core study area (tiles N16E079, N16E080, N16E081).
- **Acquisition details:**
  - Source: AWS Open Data Registry `s3://copernicus-dem-30m/`
  - Access: Anonymous (unsigned) S3 requests
  - Format: Cloud Optimized GeoTIFF (COG) with auxiliary files (HEM, EDM, FLM, WBM, ACM, XML metadata)
  - Retrieval: 2026-10-23, total 126.3 MB (3 tiles)
  - SHA-256 checksums verified and recorded in `data/cache/manifest.json`
- **Planned usage:** Cropped to study area, used as elevation input for threshold flood-connectivity model.

## 3. SRTM 30m (Alternative DEM)

- **Purpose:** Alternative/fallback terrain elevation mapping.
- **Source:** NASA Shuttle Radar Topography Mission (public domain).
- **Status:** *Planned* (fallback if Copernicus DEM proves insufficient).
- **Constraints & Limitations:** Older dataset (2000), coarser vertical accuracy, similar resolution.

## 4. OpenStreetMap Road Network

- **Purpose:** Road network intersections for the "road-impact view" (which roads may be cut by flooding).
- **Source:** Overpass API — https://overpass-turbo.eu/
- **Constraints & Limitations:**
  - Subject to strict API rate-limiting; all results must be cached locally.
  - Data accuracy depends on OSM contributor contributions; may be incomplete in rural areas.
- **Planned usage:** Road topologies loaded into PostGIS via `shp`/`.gpkg` formats; spatially joined to flood extents.
- **Status:** *Planned* (M1+)

## 5. ISRO Bhuvan / NRSC Flood-Inundation Reference Data

- **Purpose:** Satellite-derived flood-inundation maps for validation against the September 2024 event.
- **Sources:** ISRO Bhuvan https://bhuvan.nrsc.gov.in/; NRSC rapid flood mapping products.
- **Reference map acquired:** 13 September 2024 flood map (AP_2024_13_09_Map.pdf, 952 KB) from APSAC.
- **Constraints & Limitations:**
  - Used purely as secondary visual context and validation reference.
  - Subject to registration terms and download restrictions.
  - Official maps lack extensive ground-truth verification and capture accumulated rainwater pools.
  - **Not ground truth**; must not be described as proof of predictive accuracy.
- **Planned usage:** Digitized reference maps in QGIS; Intersection over Union (IoU) metric computed for model validation.
- **Status:** *Acquired* (reference map downloaded 2026-10-23)

## Summary

| Data Source | Status | Milestone |
| ----------- | ------ | --------- |
| Open-Meteo Historical Rainfall | Planned | M1+ |
| Copernicus DEM GLO-30 | **Acquired (M1.2 Phase 1)** | M1.2 |
| SRTM 30m (alternative) | Planned | M1.2+ |
| OpenStreetMap Roads | Planned | M1+ |
| ISRO/NRSC Flood Inundation (13 Sep 2024) | **Acquired** (reference map) | M3 (validation) |

> **Note:** This document is a living artifact. Update it as sources are acquired, tested, or rejected.