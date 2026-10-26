"""Kshitij flood-connectivity model — synthetic terrain flood extent computation.

This package provides a standalone, deterministic flood-connectivity algorithm
that operates on a synthetic digital elevation model represented by a 2D NumPy
array. It identifies cells that are flooded given a water-level threshold and
river-source mask, using 4-neighbor (up/down/left/right) connectivity.

The core function ``compute_flood_extent`` is deliberately isolated from Django,
PostGIS, rasterio, GDAL, and any web-layer concerns so that it can be unit-tested
in isolation.

M1.2 Phase 2 adds raster preprocessing utilities for working with real DEM data:
- Inspecting raster metadata
- Cropping and mosaicking DEM tiles
- Building validity masks
- Writing georeferenced GeoTIFF output
- Adapting raster data for the flood-connectivity model
"""

from .connectivity import compute_flood_extent
from .raster_preprocessing import (
    RasterPreprocessingError,
    build_validity_mask,
    crop_raster,
    inspect_raster,
    mosaic_tiles,
    prepare_model_input,
    write_geotiff,
)

__all__ = [
    "RasterPreprocessingError",
    "build_validity_mask",
    "compute_flood_extent",
    "crop_raster",
    "inspect_raster",
    "mosaic_tiles",
    "prepare_model_input",
    "write_geotiff",
]