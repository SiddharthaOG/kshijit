# Kshitij — Planned Data Sources (Milestone M0)

This document lists the data sources that Kshitij intends to use across its roadmap.
**No data has been downloaded, processed, or validated in this milestone.**
All entries are marked as *planned* and will be activated in later milestones.

## 1. Open-Meteo Historical Rainfall

- **Purpose:** Historical rainfall series for replay-based flood estimation.
- **API:** https://open-meteo.com/en/docs#historical-weather
- **Constraints & Limitations:**
  - Coarse reanalysis data (tens of kilometres resolution).
  - Local extreme weather anomalies will be underestimated.
  - Free tier has rate limits; all results must be cached locally.
- **Planned usage:** Scripts in `scripts/` will fetch and parse historical rainfall for the September 2024 Vijayawada event.

## 2. Free Digital Elevation Model (DEM)

- **Purpose:** Terrain elevation mapping for the threshold flood-connectivity model.
- **Sources considered:**
  - **Copernius GLO-30** (global 30m DEM, free access).
  - **SRTM 30m** (NASA Shuttle Radar Topography Mission, public domain).
- **Constraints & Limitations:**
  - Coarse vertical resolution; unable to capture localized urban drainage networks.
  - Unable to capture crucial Krishna River embankments at this resolution.
  - Data coverage may have gaps in certain regions.
- **Planned usage:** DEM tiles will be loaded into PostGIS/PostGIS raster for the flood model.

## 3. OpenStreetMap Road Network

- **Purpose:** Road network intersections for the "road-impact view" (which roads may be cut by flooding).
- **Source:** Overpass API — https://overpass-turbo.eu/
- **Constraints & Limitations:**
  - Subject to strict API rate-limiting; all results must be cached locally.
  - Data accuracy depends on OSM contributor contributions; may be incomplete in rural areas.
- **Planned usage:** Road topologies loaded into PostGIS via `shp`/`.gpkg` formats; spatially joined to flood extents.

## 4. ISRO Bhuvan / NRSC Flood-Inundation Reference Data

- **Purpose:** Satellite-derived flood-inundation maps for validation against the September 2024 event.
- **Sources:** ISRO Bhuvan https://bhuvan.nrsc.gov.in/; NRSC rapid flood mapping products.
- **Constraints & Limitations:**
  - Used purely as secondary visual context and validation reference.
  - Subject to registration terms and download restrictions.
  - Official maps lack extensive ground-truth verification and capture accumulated rainwater pools.
- **Planned usage:** Digitized reference maps in QGIS; Intersection over Union (IoU) metric computed for model validation.

## Summary

| Data Source | Status | Milestone |
| ----------- | ------ | --------- |
| Open-Meteo Historical Rainfall | Planned | M1+ |
| Free DEM (Copernicus/SRTM) | Planned | M1+ |
| OpenStreetMap Roads | Planned | M1+ |
| ISRO/NRSC Flood Inundation | Planned | M3 (validation) |

> **Note:** This document is a living artifact. Update it as sources are acquired, tested, or rejected.