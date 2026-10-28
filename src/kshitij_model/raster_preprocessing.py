"""Raster preprocessing module for Kshitij flood-connectivity model.

Provides functionality to inspect, crop, mosaic, and prepare Copernicus DEM GLO-30
tiles for the flood-connectivity model, and to write flood extent outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds


@dataclass
class RasterMetadata:
    """Metadata for a raster dataset."""

    crs: str
    width: int
    height: int
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]  # (left, bottom, right, top)
    dtype: str
    nodata: float | None
    count: int
    driver: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "crs": self.crs,
            "width": self.width,
            "height": self.height,
            "transform": list(self.transform),
            "bounds": list(self.bounds),
            "dtype": self.dtype,
            "nodata": self.nodata,
            "count": self.count,
            "driver": self.driver,
        }


class RasterPreprocessingError(Exception):
    """Raised when raster preprocessing fails."""


def inspect_raster(path: Path | str) -> dict[str, Any]:
    """Inspect a raster file and return its metadata.

    Args:
        path: Path to the raster file.

    Returns:
        Dictionary with raster metadata including CRS, bounds, transform,
        dtype, NoData value, dimensions, and statistics.
    """
    with rasterio.open(path) as src:
        # Read basic metadata
        meta = {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": str(src.dtypes[0]) if src.dtypes else None,
            "nodata": src.nodata,
            "driver": src.driver,
            "transform": list(src.transform) if src.transform else None,
            "bounds": list(src.bounds) if src.bounds else None,
            "resolution": (src.res[0], src.res[1]) if src.res else None,
        }

        # Read first band for statistics
        if src.count > 0:
            data = src.read(1, masked=True)
            if hasattr(data, "mask"):
                valid_data = data[~data.mask]
            else:
                valid_data = data.flatten()
            if valid_data.size > 0:
                meta["min"] = float(np.nanmin(valid_data))
                meta["max"] = float(np.nanmax(valid_data))
                meta["mean"] = float(np.nanmean(valid_data))
                meta["std"] = float(np.nanstd(valid_data))
            else:
                meta["min"] = None
                meta["max"] = None
                meta["mean"] = None
                meta["std"] = None

        return meta


def _bounds_to_window(
    src: rasterio.DatasetReader, bounds: tuple[float, float, float, float]
) -> rasterio.windows.Window:
    """Convert geographic bounds to a rasterio window.

    Args:
        src: Open rasterio dataset.
        bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84.

    Returns:
        rasterio.windows.Window for the given bounds.
    """
    # Convert geographic bounds to pixel window
    left, bottom, right, top = bounds
    window = from_bounds(left, bottom, right, top, transform=src.transform)
    return window


def crop_raster(
    src_path: Path | str,
    dst_path: Path | str,
    bounds: tuple[float, float, float, float],
    nodata: float | None = None,
    dst_crs: str | None = None,
    dst_nodata: float | None = None,
    compression: str = "lzw",
) -> dict[str, Any]:
    """Crop a raster to the given bounds.

    Args:
        src_path: Path to source raster.
        dst_path: Path to output cropped raster.
        bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84 (EPSG:4326).
        nodata: NoData value to use for output (default: from source).
        dst_crs: Output CRS (default: same as source).
        dst_nodata: NoData value for output (default: from source or -32767).
        compression: Compression method for output (default: lzw).

    Returns:
        Dictionary with output metadata.
    """
    with rasterio.open(src_path) as src:
        # Get source CRS
        src_crs = src.crs or "EPSG:4326"

        # Determine output CRS
        dst_crs = dst_crs or src_crs

        # Calculate output bounds in destination CRS
        # For now, assume source and destination CRS are the same (EPSG:4326)
        # If they differ, we'd need to reproject bounds
        if dst_crs != src.crs:
            raise NotImplementedError("Reprojection not yet supported")

        # Calculate window for cropping
        left, bottom, right, top = bounds
        window = from_bounds(left, bottom, right, top, transform=src.transform)

        # Read data within window
        data = src.read(1, window=window, masked=True)

        # Update transform for cropped window
        new_transform = src.window_transform(window)

        # Update profile for output
        profile = src.profile.copy()
        profile.update(
            {
                "height": data.shape[0],
                "width": data.shape[1],
                "transform": new_transform,
                "compress": "lzw",
                "driver": "GTiff",
            }
        )

        # Set nodata value
        if dst_nodata is not None:
            profile["nodata"] = dst_nodata
        elif nodata is not None:
            profile["nodata"] = nodata
        else:
            profile["nodata"] = -32767

        # Write output
        output_path = Path(dst_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(dst_path, "w", **profile) as dst:
            if hasattr(data, "mask"):
                dst.write(data.filled(profile.get("nodata", -32767)), 1)
            else:
                dst.write(data, 1)

    # Return metadata
    with rasterio.open(dst_path) as src:
        return {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "transform": list(src.transform),
            "bounds": list(src.bounds),
            "dtype": str(src.dtypes[0]) if src.dtypes else None,
            "nodata": src.nodata,
        }


def build_validity_mask(
    data: np.ndarray,
    nodata: float | None = None,
    config_nodata: float | None = None,
) -> np.ndarray:
    """Build a validity mask for raster data.

    Valid pixels are those that are:
    - Not NaN
    - Not +/- infinity
    - Not equal to the nodata sentinel value (if provided)

    Valid zero and negative elevations are PRESERVED as valid data.

    Args:
        data: Input elevation array.
        nodata: Explicit NoData value to mask (overrides config).
        config_nodata: NoData value from config (fallback).

    Returns:
        Boolean array where True = valid data, False = invalid/NoData.
    """
    # Start with all valid
    valid = np.ones(data.shape, dtype=bool)

    # Mask NaN
    valid = valid & ~np.isnan(data)

    # Mask infinities
    valid = valid & ~np.isinf(data)

    # Determine NoData sentinel
    nodata_value = nodata if nodata is not None else config_nodata

    # If no explicit nodata, we don't mask any sentinel values
    # (Copernicus DEM GLO-30 doesn't set a NoData tag in the COG metadata)
    if nodata_value is not None:
        valid = valid & (data != nodata_value)

    return valid


def mosaic_tiles(
    tile_paths: list[Path | str],
    dst_path: Path | str,
    bounds: tuple[float, float, float, float] | None = None,
    dst_nodata: float = -32767,
    compression: str = "lzw",
    resampling: Resampling = Resampling.nearest,
) -> dict[str, Any]:
    """Mosaic multiple raster tiles into a single output.

    Uses 'first' method for overlapping areas (first tile wins).

    Args:
        tile_paths: List of paths to input GeoTIFF tiles.
        dst_path: Output path for mosaicked raster.
        bounds: Optional output bounds (min_lon, min_lat, max_lon, max_lat).
                If None, uses union of all input tile bounds.
        dst_nodata: NoData value for output.
        compression: Compression method (default: lzw).
        resampling: Resampling method for overlapping areas.

    Returns:
        Dictionary with output metadata.
    """
    # Open all source datasets
    src_files = [rasterio.open(p) for p in tile_paths]

    try:
        # Mosaic the tiles
        mosaic_data, mosaic_transform = merge(
            src_files,
            bounds=bounds,
            nodata=np.nan,
            method="first",
            resampling=resampling,
        )

        # Get metadata from first source
        src = src_files[0]
        profile = src.profile.copy()

        # Update profile for output
        profile = src.profile.copy()
        profile.update(
            {
                "height": mosaic_data.shape[1],
                "width": mosaic_data.shape[2],
                "transform": mosaic_transform,
                "compress": "lzw",
                "driver": "GTiff",
                "nodata": -32767,
            }
        )

        # Write output
        output_path = Path(dst_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(dst_path, "w", **profile) as dst:
            # Replace NaN with nodata value for output
            output_data = np.where(np.isnan(mosaic_data), -32767, mosaic_data)
            # merge() returns (bands, height, width); write expects (height, width) for single band
            if output_data.ndim == 3 and output_data.shape[0] == 1:
                output_data = output_data[0]
            dst.write(output_data.astype(src.dtypes[0]), 1)

        # Return metadata
        with rasterio.open(dst_path) as src:
            return {
                "crs": str(src.crs) if src.crs else None,
                "width": src.width,
                "height": src.height,
                "transform": list(src.transform),
                "bounds": list(src.bounds),
                "dtype": str(src.dtypes[0]) if src.dtypes else None,
                "nodata": src.nodata,
            }
    finally:
        for src in src_files:
            src.close()


def write_geotiff(
    dst_path: Path | str,
    data: np.ndarray,
    profile: dict[str, Any],
    nodata: float | None = -32767,
) -> dict[str, Any]:
    """Write a NumPy array as a GeoTIFF with proper metadata.

    Args:
        dst_path: Output path.
        data: 2D numpy array to write.
        profile: Rasterio profile dictionary.
        nodata: NoData value to write (default: -32767).

    Returns:
        Dictionary with output metadata.
    """
    output_path = Path(dst_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile = profile.copy()
    profile.update(
        {
            "compress": "lzw",
            "driver": "GTiff",
            "nodata": nodata if nodata is not None else -32767,
        }
    )

    # Replace NaN with nodata value for output
    output_data = data.copy()
    output_data[np.isnan(data)] = -32767

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(output_data.astype(profile["dtype"]), 1)

    with rasterio.open(dst_path) as src:
        return {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "transform": list(src.transform),
            "bounds": list(src.bounds),
            "dtype": str(src.dtypes[0]) if src.dtypes else None,
            "nodata": src.nodata,
        }


def prepare_model_input(
    raster_path: Path | str,
    nodata: float | None = None,
    config_nodata: float | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Prepare raster data for the flood connectivity model.

    Reads a GeoTIFF, builds a validity mask, and returns data ready for
    compute_flood_extent().

    Args:
        raster_path: Path to GeoTIFF file.
        nodata: Explicit NoData value to use (overrides config and source).
        config_nodata: NoData value from config (fallback, overrides source).

    Returns:
        Tuple of (elevation_array, validity_mask, metadata_dict).
    """
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        transform = src.transform
        crs = src.crs
        bounds = src.bounds

        # Build validity mask: explicit nodata > config_nodata > source nodata
        # If all are None, build_validity_mask will only mask NaN/inf
        nodata_val = nodata if nodata is not None else config_nodata
        # Fall back to source's declared nodata if no explicit override
        if nodata_val is None:
            nodata_val = src.nodata
        validity_mask = build_validity_mask(data, nodata=nodata_val, config_nodata=None)

        metadata = {
            "crs": str(src.crs) if src.crs else None,
            "transform": src.transform,
            "bounds": src.bounds,
            "width": src.width,
            "height": src.height,
            "dtype": str(src.dtypes[0]) if src.dtypes else None,
            "nodata": src.nodata,
        }

        return data, validity_mask, metadata


def write_flood_extent(
    dst_path: Path | str,
    flooded: np.ndarray,
    validity_mask: np.ndarray,
    dem_metadata: dict[str, Any],
    nodata: int = 255,
    compression: str = "lzw",
) -> dict[str, Any]:
    """Write flood extent as a GeoTIFF with three-state encoding.

    Output encoding (uint8):
    - 1: flooded valid cell
    - 0: valid, non-flooded (dry) cell
    - nodata (default 255): invalid terrain or outside modeled domain

    Args:
        dst_path: Output path for flood extent GeoTIFF.
        flooded: Boolean array from compute_flood_extent (True = flooded).
        validity_mask: Boolean array from prepare_model_input (True = valid terrain).
        dem_metadata: Metadata dict from prepare_model_input containing
            crs, transform, bounds, width, height.
        nodata: NoData value for output (default 255 for uint8).
        compression: Compression method (default: lzw).

    Returns:
        Dictionary with output metadata.

    Raises:
        ValueError: If flooded and validity_mask shapes don't match dem_metadata.
    """
    # Validate shapes
    expected_height = dem_metadata["height"]
    expected_width = dem_metadata["width"]
    if flooded.shape != (expected_height, expected_width):
        raise ValueError(
            f"flooded shape {flooded.shape} does not match dem_metadata "
            f"({expected_height}, {expected_width})"
        )
    if validity_mask.shape != (expected_height, expected_width):
        raise ValueError(
            f"validity_mask shape {validity_mask.shape} does not match dem_metadata "
            f"({expected_height}, {expected_width})"
        )

    # Create output array with three states
    output_data = np.full(flooded.shape, nodata, dtype=np.uint8)
    output_data[validity_mask & ~flooded] = 0  # valid dry
    output_data[validity_mask & flooded] = 1  # valid flooded
    # validity_mask == False remains nodata (invalid terrain)

    output_path = Path(dst_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": expected_width,
        "height": expected_height,
        "count": 1,
        "crs": dem_metadata["crs"],
        "transform": dem_metadata["transform"],
        "compress": compression,
        "nodata": nodata,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(output_data, 1)

    # Verify by reopening
    with rasterio.open(output_path) as src:
        return {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "transform": list(src.transform),
            "bounds": list(src.bounds),
            "dtype": str(src.dtypes[0]) if src.dtypes else None,
            "nodata": src.nodata,
        }
