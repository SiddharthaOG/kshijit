"""Pipeline orchestration for Kshitij M1.4: DEM to flood extent.

Composes existing APIs into a reproducible workflow:
1. Acquire or reuse DEM tiles
2. Mosaic tiles
3. Crop to AOI
4. Prepare model input (elevation + validity mask)
5. Generate river source mask
6. Compute flood extent
7. Write output GeoTIFF
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from .config import DEMConfig, get_config
from .connectivity import compute_flood_extent
from .dem_acquisition import DEMAcquisition, acquire_dem
from .raster_preprocessing import (
    crop_raster,
    mosaic_tiles,
    prepare_model_input,
    write_flood_extent,
)
from .river_mask import (
    RiverGeometryError,
    RiverMaskEmptyError,
    RiverMaskError,
    RiverVectorError,
    rasterize_river_mask,
    write_river_mask_geotiff,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when pipeline execution fails."""


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid."""


@dataclass
class PipelineConfig:
    """Configuration for M1.4 flood extent pipeline."""

    # DEM acquisition
    dem_tiles: list[tuple[int, int]] | None = None
    cache_dir: str | Path = "data/cache"
    raw_dir: str | Path = "data/raw/dem"
    processed_dir: str | Path = "data/processed"

    # AOI cropping
    aoi_bounds: tuple[float, float, float, float] | None = (
        None  # (min_lon, min_lat, max_lon, max_lat)
    )

    # River mask
    river_vector_path: str | Path | None = None
    river_buffer_meters: float = 0.0
    river_all_touched: bool = True

    # Flood model
    water_level: float = 10.0
    nodata_value: float = -32767.0

    # Output
    output_path: str | Path = "data/processed/flood_extent.tif"
    write_river_mask: bool = False
    river_mask_output_path: str | Path | None = None

    # Processing
    use_cached_dem: bool = True
    compression: str = "lzw"

    def __post_init__(self):
        """Validate configuration."""
        if self.water_level is None:
            raise PipelineConfigError("water_level is required")
        if not np.isfinite(self.water_level):
            raise PipelineConfigError("water_level must be finite")
        if self.river_vector_path is None:
            raise PipelineConfigError("river_vector_path is required")
        if self.aoi_bounds is not None:
            if len(self.aoi_bounds) != 4:
                raise PipelineConfigError(
                    "aoi_bounds must be (min_lon, min_lat, max_lon, max_lat)"
                )
            min_lon, min_lat, max_lon, max_lat = self.aoi_bounds
            # Check for finite coordinates
            if not all(np.isfinite(c) for c in self.aoi_bounds):
                raise PipelineConfigError("aoi_bounds coordinates must be finite")
            # Check min/max ordering
            if min_lon >= max_lon:
                raise PipelineConfigError("aoi_bounds min_lon must be less than max_lon")
            if min_lat >= max_lat:
                raise PipelineConfigError("aoi_bounds min_lat must be less than max_lat")
            # Check geographic bounds for WGS84
            if min_lon < -180 or max_lon > 180:
                raise PipelineConfigError("aoi_bounds longitude must be in [-180, 180]")
            if min_lat < -90 or max_lat > 90:
                raise PipelineConfigError("aoi_bounds latitude must be in [-90, 90]")

        # Validate buffer distance
        if self.river_buffer_meters < 0:
            raise PipelineConfigError("river_buffer_meters must be non-negative")
        if not np.isfinite(self.river_buffer_meters):
            raise PipelineConfigError("river_buffer_meters must be finite")


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    flood_extent_path: Path
    flood_extent_meta: dict[str, Any]
    dem_mosaic_path: Path | None = None
    dem_cropped_path: Path | None = None
    river_mask_path: Path | None = None
    river_mask_meta: dict[str, Any] | None = None
    elevation_shape: tuple[int, int] | None = None
    flooded_cell_count: int | None = None
    valid_cell_count: int | None = None


def _ensure_dem_tiles(
    config: PipelineConfig,
    dem_config: DEMConfig,
) -> list[Path]:
    """Ensure DEM tiles are available locally, downloading only missing tiles if necessary.

    Args:
        config: Pipeline configuration.
        dem_config: DEM configuration.

    Returns:
        List of paths to DEM tile files in the same order as requested tiles.

    Raises:
        PipelineError: If a requested tile is still missing after acquisition.
    """
    tiles = config.dem_tiles or dem_config.study_tiles
    tile_paths = []

    if config.use_cached_dem:
        acquisition = DEMAcquisition(
            cache_dir=config.cache_dir,
            raw_dir=config.raw_dir,
            config=dem_config,
        )
        for lat, lon in tiles:
            tile_id = f"N{lat:02d}E{lon:03d}"
            tile_path = Path(config.raw_dir) / f"{tile_id}.tif"
            if tile_path.exists():
                logger.info("Using cached DEM tile: %s", tile_id)
                tile_paths.append(tile_path)
            else:
                logger.info("Tile not cached, will download: %s", tile_id)
                # Collect missing tiles for batch acquisition

    # If some tiles are missing, acquire only those
    if len(tile_paths) != len(tiles):
        missing_tiles = []
        for lat, lon in tiles:
            tile_id = f"N{lat:02d}E{lon:03d}"
            tile_path = Path(config.raw_dir) / f"{tile_id}.tif"
            if not tile_path.exists():
                missing_tiles.append((lat, lon))

        logger.info("Acquiring %d missing DEM tiles...", len(missing_tiles))
        manifest = acquire_dem(
            tiles=missing_tiles,
            cache_dir=config.cache_dir,
            raw_dir=config.raw_dir,
        )
        for tile_info in manifest.tiles:
            tile_paths.append(Path(tile_info.local_path))

    # Verify all tiles are present
    if len(tile_paths) != len(tiles):
        missing = []
        for lat, lon in tiles:
            tile_id = f"N{lat:02d}E{lon:03d}"
            tile_path = Path(config.raw_dir) / f"{tile_id}.tif"
            if not tile_path.exists():
                missing.append(tile_id)
        raise PipelineError(f"DEM tiles still missing after acquisition: {missing}")

    # Ensure paths are in the same order as requested tiles
    ordered_paths = []
    for lat, lon in tiles:
        tile_id = f"N{lat:02d}E{lon:03d}"
        tile_path = Path(config.raw_dir) / f"{tile_id}.tif"
        ordered_paths.append(tile_path)

    return ordered_paths


def _mosaic_and_crop_dem(
    tile_paths: list[Path],
    config: PipelineConfig,
    dem_config: DEMConfig,
) -> tuple[Path, Path]:
    """Mosaic DEM tiles and crop to AOI.

    Args:
        tile_paths: Paths to DEM tile files.
        config: Pipeline configuration.
        dem_config: DEM configuration.

    Returns:
        Tuple of (mosaic_path, cropped_path).
    """
    processed_dir = Path(config.processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    mosaic_path = processed_dir / "dem_mosaic.tif"
    cropped_path = processed_dir / "dem_cropped.tif"

    # Determine mosaic bounds
    mosaic_bounds = config.aoi_bounds or dem_config.study_area_bounds

    logger.info("Mosaicking %d DEM tiles...", len(tile_paths))
    mosaic_tiles(
        tile_paths=[str(p) for p in tile_paths],
        dst_path=str(mosaic_path),
        bounds=mosaic_bounds,
        dst_nodata=config.nodata_value,
        compression=config.compression,
    )

    # Crop to AOI if different from mosaic bounds
    if config.aoi_bounds is not None:
        logger.info("Cropping mosaic to AOI: %s", config.aoi_bounds)
        crop_raster(
            src_path=str(mosaic_path),
            dst_path=str(cropped_path),
            bounds=config.aoi_bounds,
            nodata=config.nodata_value,
            dst_nodata=config.nodata_value,
            compression=config.compression,
        )
    else:
        # No cropping needed, use mosaic directly
        cropped_path = mosaic_path

    return mosaic_path, cropped_path


def _generate_river_mask(
    cropped_dem_path: Path,
    config: PipelineConfig,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Generate river source mask aligned to cropped DEM.

    Args:
        cropped_dem_path: Path to cropped DEM GeoTIFF.
        config: Pipeline configuration.

    Returns:
        Tuple of (river_mask_array, river_mask_metadata).
    """
    logger.info("Generating river mask from %s", config.river_vector_path)

    # Get reference grid from cropped DEM
    with rasterio.open(cropped_dem_path) as src:
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs

    river_mask = rasterize_river_mask(
        vector_path=config.river_vector_path,
        reference_transform=transform,
        reference_width=width,
        reference_height=height,
        reference_crs=crs,
        buffer_meters=config.river_buffer_meters,
        all_touched=config.river_all_touched,
    )

    # Write river mask for inspection if requested
    river_mask_meta = {}
    if config.write_river_mask and config.river_mask_output_path:
        river_mask_meta = write_river_mask_geotiff(
            mask=river_mask,
            dst_path=config.river_mask_output_path,
            reference_transform=transform,
            reference_crs=crs,
        )
        logger.info("River mask written to %s", config.river_mask_output_path)

    return river_mask, river_mask_meta


def _compute_flood_extent(
    elevation: np.ndarray,
    validity_mask: np.ndarray,
    river_mask: np.ndarray,
    config: PipelineConfig,
) -> np.ndarray:
    """Compute flood extent using threshold connectivity.

    Args:
        elevation: Elevation array from prepare_model_input.
        validity_mask: Validity mask from prepare_model_input.
        river_mask: River source mask from rasterize_river_mask.
        config: Pipeline configuration.

    Returns:
        Boolean flood extent array.
    """
    logger.info("Computing flood extent at water level %.2f m", config.water_level)

    # The river_mask is the source_mask for compute_flood_extent
    # compute_flood_extent will validate that source cells are eligible
    # (valid terrain AND elevation <= water_level)
    flooded = compute_flood_extent(
        elevation=elevation,
        source_mask=river_mask,
        water_level=config.water_level,
        nodata=config.nodata_value,
    )

    logger.info(
        "Flood extent computed: %d flooded cells out of %d valid cells",
        flooded.sum(),
        validity_mask.sum(),
    )

    return flooded


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the full M1.4 flood extent pipeline.

    Args:
        config: Pipeline configuration.

    Returns:
        PipelineResult with output paths and metadata.

    Raises:
        PipelineError: If any pipeline step fails.
    """
    logger.info("Starting M1.4 flood extent pipeline")
    logger.info(
        "Config: water_level=%.2f, nodata=%.0f", config.water_level, config.nodata_value
    )

    # Get DEM configuration
    dem_config = get_config()
    if config.dem_tiles:
        dem_config.study_tiles = config.dem_tiles
    if config.aoi_bounds:
        dem_config.study_area_bounds = config.aoi_bounds

    try:
        # Step 1: Ensure DEM tiles available
        tile_paths = _ensure_dem_tiles(config, dem_config)

        # Step 2: Mosaic and crop
        mosaic_path, cropped_path = _mosaic_and_crop_dem(tile_paths, config, dem_config)

        # Step 3: Prepare model input
        logger.info("Preparing model input from %s", cropped_path)
        elevation, validity_mask, dem_metadata = prepare_model_input(
            raster_path=cropped_path,
            nodata=config.nodata_value,
        )

        # Step 4: Generate river mask
        river_mask, river_mask_meta = _generate_river_mask(cropped_path, config)

        # Step 5: Compute flood extent
        flooded = _compute_flood_extent(elevation, validity_mask, river_mask, config)

        # Step 6: Write output
        flood_meta = write_flood_extent(
            dst_path=config.output_path,
            flooded=flooded,
            validity_mask=validity_mask,
            dem_metadata=dem_metadata,
            nodata=255,
            compression=config.compression,
        )

        # Compile result
        result = PipelineResult(
            flood_extent_path=Path(config.output_path),
            flood_extent_meta=flood_meta,
            dem_mosaic_path=mosaic_path if mosaic_path != cropped_path else None,
            dem_cropped_path=cropped_path,
            river_mask_path=Path(config.river_mask_output_path)
            if config.write_river_mask and config.river_mask_output_path
            else None,
            river_mask_meta=river_mask_meta if river_mask_meta else None,
            elevation_shape=elevation.shape,
            flooded_cell_count=int(flooded.sum()),
            valid_cell_count=int(validity_mask.sum()),
        )

        logger.info("Pipeline completed successfully")
        logger.info("Output: %s", result.flood_extent_path)
        logger.info(
            "Flooded cells: %d / %d valid",
            result.flooded_cell_count,
            result.valid_cell_count,
        )

        return result

    except (
        RiverMaskError,
        RiverVectorError,
        RiverGeometryError,
        RiverMaskEmptyError,
    ) as e:
        raise PipelineError(f"River mask generation failed: {e}") from e
    except Exception as e:
        raise PipelineError(f"Pipeline execution failed: {e}") from e
