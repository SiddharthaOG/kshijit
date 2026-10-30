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

M1.4 adds:
- River vector rasterization for source mask generation
- End-to-end pipeline orchestration from DEM to flood extent
- Flood extent output writing with three-state encoding
"""

from .connectivity import compute_flood_extent
from .pipeline import PipelineConfig, PipelineError, PipelineResult, run_pipeline
from .raster_preprocessing import (
    RasterPreprocessingError,
    build_validity_mask,
    crop_raster,
    inspect_raster,
    mosaic_tiles,
    prepare_model_input,
    write_flood_extent,
    write_geotiff,
)
from .river_mask import (
    MissingDependencyError,
    RiverGeometryError,
    RiverMaskEmptyError,
    RiverMaskError,
    RiverVectorError,
    create_river_mask_from_geojson_dict,
    rasterize_river_mask,
    write_river_mask_geotiff,
)
from .validation import (
    ValidationMetrics,
    compute_confusion_matrix,
    compute_metrics,
    compute_metrics_from_arrays,
    align_rasters_to_common_grid,
    create_comparison_rgb,
    write_comparison_rgb,
    extract_krishna_river_from_osm,
)

__all__ = [
    "MissingDependencyError",
    "PipelineConfig",
    "PipelineError",
    "PipelineResult",
    "RasterPreprocessingError",
    "RiverGeometryError",
    "RiverMaskEmptyError",
    "RiverMaskError",
    "RiverVectorError",
    "ValidationMetrics",
    "align_rasters_to_common_grid",
    "build_validity_mask",
    "compute_confusion_matrix",
    "compute_flood_extent",
    "compute_metrics",
    "compute_metrics_from_arrays",
    "create_comparison_rgb",
    "create_river_mask_from_geojson_dict",
    "crop_raster",
    "extract_krishna_river_from_osm",
    "inspect_raster",
    "mosaic_tiles",
    "prepare_model_input",
    "rasterize_river_mask",
    "run_pipeline",
    "write_comparison_rgb",
    "write_flood_extent",
    "write_geotiff",
    "write_river_mask_geotiff",
]
