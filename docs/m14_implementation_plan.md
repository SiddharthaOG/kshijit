# Kshitij M1.4 — Real-DEM Flood Extent Pipeline

## Objective

Implement a reproducible, tested pipeline that takes a real Copernicus DEM GLO-30 and a supplied river vector, computes a threshold-connected flood extent using the existing `compute_flood_extent` model, and writes a correctly georeferenced output GeoTIFF with three-state encoding (flooded, dry, NoData).

**Non-goals (explicitly out of scope for M1.4):**
- Automatic OSM/HydroSHEDS retrieval or fallback systems
- Georeferencing or digitizing `AP_2024_13_09_Map.pdf`
- IoU, precision, recall, F1, confusion-matrix metrics, or historical validation
- Water-level calibration or claims of predictive accuracy
- Hydrodynamic simulation, flow routing, infiltration, or time evolution
- PostGIS persistence, dashboards, or live alerts

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        M1.4 Pipeline                                │
├─────────────────────────────────────────────────────────────────────┤
│  1. DEM Acquisition      →  data/raw/dem/N16E079/080/081.tif       │
│  2. Mosaic Tiles         →  data/processed/dem_mosaic.tif          │
│  3. Crop to AOI          →  data/processed/dem_cropped.tif         │
│  4. Prepare Model Input  →  elevation (float32), validity (bool)   │
│  5. River Mask           →  river_mask (bool, aligned to DEM)      │
│  6. Compute Flood Extent →  flooded (bool)                         │
│  7. Write Output         →  data/processed/flood_extent.tif        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Module | Purpose |
|--------|---------|
| `kshitij_model.dem_acquisition` | Download/verify Copernicus DEM tiles from AWS S3 (anonymous) |
| `kshitij_model.raster_preprocessing` | Mosaic, crop, inspect, prepare model input, write outputs |
| `kshitij_model.river_mask` | Rasterize river vector (GeoJSON/GPKG) to Boolean mask aligned to DEM grid |
| `kshitij_model.pipeline` | Orchestrate the full workflow with config validation |
| `kshitij_model.connectivity` | Core `compute_flood_extent` (threshold connectivity, 4-neighbor) |

---

## Installation

```bash
# Core dependencies (numpy, rasterio)
pip install -e .

# River vector support (fiona, shapely, pyproj for buffering)
pip install -e .[river]

# Or install test dependencies including river
pip install -e .[test]
```

---

## Usage

### Command-Line Interface

```bash
python scripts/run_m14_pipeline.py \
    --river-vector data/river.geojson \
    --water-level 15.0 \
    --output data/processed/flood_extent.tif \
    --aoi-bounds 80.5 16.3 81.2 16.7 \
    --river-buffer 30 \
    --write-river-mask \
    --river-mask-output data/processed/river_mask.tif
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `--river-vector` | Yes | Path to river vector (GeoJSON, GeoPackage, Shapefile) |
| `--water-level` | Yes | Water level threshold in meters (EGM2008 datum) |
| `--output` | No | Output flood extent GeoTIFF (default: `data/processed/flood_extent.tif`) |
| `--aoi-bounds` | No | AOI bounds as `min_lon min_lat max_lon max_lat` (WGS84) |
| `--dem-tiles` | No | DEM tiles as `lat lon` pairs (default: study tiles from config) |
| `--cache-dir` | No | DEM cache directory (default: `data/cache`) |
| `--raw-dir` | No | Raw DEM directory (default: `data/raw/dem`) |
| `--processed-dir` | No | Processed output directory (default: `data/processed`) |
| `--no-cache` | No | Force re-download DEM tiles |
| `--river-buffer` | No | Buffer distance in meters (requires pyproj) |
| `--river-all-touched` / `--river-center-only` | No | Rasterization mode (default: all_touched=True) |
| `--write-river-mask` | No | Write river mask GeoTIFF for inspection |
| `--river-mask-output` | No | River mask output path |
| `--nodata` | No | DEM NoData sentinel (default: -32767) |
| `--compression` | No | Output compression: lzw/deflate/none (default: lzw) |
| `-v` / `-q` | No | Verbose/quiet logging |

### Python API

```python
from kshitij_model import PipelineConfig, run_pipeline

config = PipelineConfig(
    dem_tiles=[(16, 79), (16, 80), (16, 81)],
    river_vector_path="data/river.geojson",
    water_level=15.0,
    aoi_bounds=(80.5, 16.3, 81.2, 16.7),
    river_buffer_meters=30.0,
    output_path="data/processed/flood_extent.tif",
    write_river_mask=True,
    river_mask_output_path="data/processed/river_mask.tif",
)

result = run_pipeline(config)
print(f"Flooded: {result.flooded_cell_count} / {result.valid_cell_count}")
print(f"Output: {result.flood_extent_path}")
```

### River Vector Requirements

- **Formats**: GeoJSON, GeoPackage (.gpkg), Shapefile (.shp)
- **Geometry types**: LineString, MultiLineString, Polygon, MultiPolygon
- **CRS**: Any CRS supported by PROJ (auto-transformed to DEM CRS)
- **Properties**: Optional `name` property for identification

**Example GeoJSON:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [80.5, 16.5],
          [80.6, 16.5],
          [80.7, 16.5]
        ]
      },
      "properties": {"name": "Krishna River"}
    }
  ]
}
```

---

## Output Specification

### Flood Extent GeoTIFF (`flood_extent.tif`)

| Property | Value |
|----------|-------|
| **CRS** | EPSG:4326 (WGS84) — same as input DEM |
| **Resolution** | 1 arc-second (~30 m at equator) |
| **Data type** | `uint8` |
| **NoData value** | 255 |
| **Compression** | LZW (configurable) |

### Pixel Encoding

| Value | Meaning |
|-------|---------|
| `1` | Flooded valid cell (connected to river, elevation ≤ water_level) |
| `0` | Valid dry cell (elevation > water_level or not connected) |
| `255` (NoData) | Invalid terrain (DEM NoData, NaN, inf, or outside AOI) |

### Verification

```python
import rasterio
import numpy as np

with rasterio.open("data/processed/flood_extent.tif") as src:
    data = src.read(1)
    print("CRS:", src.crs)
    print("Shape:", data.shape)
    print("NoData:", src.nodata)
    print("Flooded:", np.sum(data == 1))
    print("Dry:", np.sum(data == 0))
    print("NoData:", np.sum(data == 255))
```

---

## River Mask Generation

### `rasterize_river_mask()`

Rasterizes a river vector file into a Boolean mask exactly aligned to the reference DEM grid.

```python
from kshitij_model import rasterize_river_mask

mask = rasterize_river_mask(
    vector_path="data/river.geojson",
    reference_transform=dem_transform,
    reference_width=dem_width,
    reference_height=dem_height,
    reference_crs="EPSG:4326",
    buffer_meters=30.0,      # Optional buffer (requires pyproj)
    all_touched=True,        # True: all touched pixels; False: center-only
)
```

**Buffering behavior:**
- If `buffer_meters > 0` and CRS is geographic (EPSG:4326), uses an Azimuthal Equidistant projection centered on the data bounds for approximate meter buffering.
- For projected CRS, buffering is exact in CRS units.

### `create_river_mask_from_geojson_dict()`

For testing with synthetic geometries (no file I/O, no fiona required):

```python
from kshitij_model import create_river_mask_from_geojson_dict

geojson = {
    "type": "FeatureCollection",
    "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 0]]}}]
}

mask = create_river_mask_from_geojson_dict(
    geojson, transform, width, height, "EPSG:4326"
)
```

---

## Configuration

### `PipelineConfig` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dem_tiles` | `list[tuple[int,int]]` | from `DEMConfig` | DEM tiles to acquire |
| `cache_dir` | `Path` | `data/cache` | DEM metadata cache |
| `raw_dir` | `Path` | `data/raw/dem` | Raw DEM tile storage |
| `processed_dir` | `Path` | `data/processed` | Output directory |
| `aoi_bounds` | `tuple[float,float,float,float]` | `None` | Crop bounds (min_lon, min_lat, max_lon, max_lat) |
| `river_vector_path` | `Path` | **required** | River vector file |
| `river_buffer_meters` | `float` | `0.0` | Buffer distance |
| `river_all_touched` | `bool` | `True` | Rasterization mode |
| `water_level` | `float` | **required** | Water level threshold (m, EGM2008) |
| `nodata_value` | `float` | `-32767.0` | DEM NoData sentinel |
| `output_path` | `Path` | `data/processed/flood_extent.tif` | Output flood extent |
| `write_river_mask` | `bool` | `False` | Write river mask GeoTIFF |
| `river_mask_output_path` | `Path` | `None` | River mask output |
| `use_cached_dem` | `bool` | `True` | Use cached tiles if available |
| `compression` | `str` | `"lzw"` | Output compression |

---

## Testing

### Run All Tests

```bash
# Core tests (no network)
pytest tests/ -v

# Specific modules
pytest tests/test_river_mask.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_raster_preprocessing.py -v
pytest tests/test_connectivity.py -v
pytest tests/test_dem_acquisition.py -v
```

### Test Categories

| Test Module | Description |
|-------------|-------------|
| `test_river_mask.py` | River vector rasterization, GeoJSON reading, error handling |
| `test_pipeline.py` | Pipeline orchestration, config validation, output writing |
| `test_raster_preprocessing.py` | Mosaic, crop, prepare_model_input, write_flood_extent |
| `test_connectivity.py` | Core flood connectivity algorithm (884 tests) |
| `test_dem_acquisition.py` | DEM download, caching, verification |

### Integration Test (Real DEM)

```bash
# Requires cached DEM tiles in data/raw/dem/
pytest tests/test_pipeline.py::TestPipelineWithRealDEM -v
```

**Skipped if** DEM tiles not available locally.

### Lint & Format

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

---

## Limitations & Assumptions

| Category | Limitation | Impact |
|----------|------------|--------|
| **DEM Type** | Copernicus DEM is a DSM (includes buildings/vegetation) | Overestimates urban elevation → underpredicts urban flooding |
| **Vertical Datum** | DEM = EGM2008 orthometric; gauge datum unknown | Water level must match DEM datum for meaningful results |
| **Resolution** | 30 m DEM vs ~10–30 m SAR reference | Urban drainage/embankments <30 m not resolved |
| **Model Physics** | Static threshold connectivity (no hydrodynamics) | No flow routing, infiltration, breach modeling, time evolution |
| **River Mask** | Requires supplied vector; no automatic OSM/HydroSHEDS | User must provide accurate river centerlines |
| **Water Level** | Single threshold; no calibration from gauge data | Sweeping water levels is post-hoc fitting, not prediction |
| **CRS Alignment** | Assumes EPSG:4326 for DEM and reference | Unverified for NRSC reference map |
| **Buffering** | Approximate for geographic CRS | Buffer meters are approximate at mid-latitudes |

---

## Known Issues

1. **Pytest cleanup on Windows**: PermissionError during temp directory cleanup (pytest infrastructure issue, not test failure)
2. **River buffering in EPSG:4326**: Uses approximate Azimuthal Equidistant projection; exact only for projected CRS
3. **GeometryCollection handling**: Extracts valid sub-geometries but may lose properties

---

## Follow-Up Work (M1.5+)

- [ ] Automatic OSM/HydroSHEDS river retrieval with fallback
- [ ] NRSC reference map digitisation and georeferencing
- [ ] IoU/Precision/Recall/F1 metrics computation
- [ ] Water-level calibration from gauge data (datum resolution)
- [ ] Hydrodynamic model integration (e.g., LISFLOOD-FP, HEC-RAS)
- [ ] PostGIS persistence and web visualization
- [ ] Uncertainty quantification (Monte Carlo water levels, DEM error)

---

## File Summary

### New Files
| File | Purpose |
|------|---------|
| `src/kshitij_model/river_mask.py` | River vector rasterization |
| `src/kshitij_model/pipeline.py` | Pipeline orchestration |
| `scripts/run_m14_pipeline.py` | CLI entry point |
| `tests/test_river_mask.py` | River mask tests |
| `tests/test_pipeline.py` | Pipeline tests |
| `docs/m14_implementation_plan.md` | This document |

### Modified Files
| File | Changes |
|------|---------|
| `src/kshitij_model/__init__.py` | Export new public APIs |
| `src/kshitij_model/raster_preprocessing.py` | Add `write_flood_extent()` |
| `pyproject.toml` | Add `river` optional dependency (fiona, shapely, pyproj) |

---

## License

Same as Kshitij project (see LICENSE file).