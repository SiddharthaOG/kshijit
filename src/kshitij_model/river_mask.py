"""River mask generation for Kshitij flood-connectivity model.

Provides functionality to rasterize river vector geometries into a Boolean mask
aligned with a reference DEM grid.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom

# Optional dependencies for river buffering
try:
    import pyproj
    from shapely.geometry import shape
    from shapely.ops import transform as shapely_transform

    BUFFERING_AVAILABLE = True
except ImportError:
    pyproj = None
    shape = None
    shapely_transform = None
    BUFFERING_AVAILABLE = False

try:
    import fiona

    FIONA_AVAILABLE = True
except ImportError:
    FIONA_AVAILABLE = False


class RiverMaskError(Exception):
    """Raised when river mask generation fails."""


class RiverVectorError(RiverMaskError):
    """Raised when river vector file is invalid or cannot be read."""


class RiverGeometryError(RiverMaskError):
    """Raised when river geometry is invalid or empty."""


class RiverMaskEmptyError(RiverMaskError):
    """Raised when rasterized river mask contains no True cells."""


class MissingDependencyError(RiverMaskError):
    """Raised when required dependency (fiona) is not installed."""


# Error messages
ERROR_FIONA_REQUIRED = (
    "fiona is required to read vector files. "
    "Install with 'pip install fiona' or use the 'river' extra."
)
ERROR_VECTOR_NOT_FOUND = "Vector file not found: {path}"
ERROR_VECTOR_NO_FEATURES = "Vector file contains no features"
ERROR_VECTOR_READ_FAILED = "Failed to read vector file {path}: {e}"
ERROR_NO_VALID_GEOMETRIES = "No valid geometries found in vector file"
ERROR_TRANSFORM_FAILED = (
    "Failed to transform geometry from {src_crs} to {target_crs}: {e}"
)
ERROR_NO_RIVER_GEOMETRIES = "No river-like geometries (LineString, MultiLineString, Polygon, MultiPolygon) found"
ERROR_BUFFER_NEGATIVE = "buffer_meters must be non-negative"
ERROR_BUFFER_FINITE = "buffer_meters must be finite"
ERROR_BUFFER_DEPS_MISSING = (
    "pyproj and shapely are required for river buffering. "
    "Install with 'pip install pyproj shapely' or use the 'river' extra."
)
ERROR_MASK_EMPTY = (
    "Rasterized river mask contains no True cells. "
    "Check that river geometry overlaps with DEM extent."
)
ERROR_MASK_EMPTY_SIMPLE = "Rasterized river mask contains no True cells"
ERROR_NOT_FEATURE_COLLECTION = "Input must be a FeatureCollection"
ERROR_VECTOR_READ_FAILED_FMT = "Failed to read vector file {path}: {e}"
ERROR_TRANSFORM_FAILED_FMT = (
    "Failed to transform geometry from {src_crs} to {target_crs}: {e}"
)
ERROR_NO_RIVER_GEOMETRIES_FMT = "No river-like geometries (LineString, MultiLineString, Polygon, MultiPolygon) found"
ERROR_BUFFER_NEGATIVE_FMT = "buffer_meters must be non-negative"
ERROR_BUFFER_FINITE_FMT = "buffer_meters must be finite"
ERROR_BUFFER_DEPS_MISSING_FMT = (
    "pyproj and shapely are required for river buffering. "
    "Install with 'pip install pyproj shapely' or use the 'river' extra."
)
ERROR_MASK_EMPTY_FMT = (
    "Rasterized river mask contains no True cells. "
    "Check that river geometry overlaps with DEM extent."
)
ERROR_NOT_FEATURE_COLLECTION_FMT = "Input must be a FeatureCollection"
ERROR_MASK_EMPTY_SIMPLE_FMT = "Rasterized river mask contains no True cells"


def _read_vector_file(vector_path: Path | str) -> list[dict[str, Any]]:
    """Read geometries from a vector file (GeoJSON, GeoPackage, Shapefile).

    Args:
        vector_path: Path to vector file.

    Returns:
        List of feature dictionaries with 'geometry' and 'properties' keys.

    Raises:
        RiverVectorError: If file cannot be read or is not a supported format.
        MissingDependencyError: If fiona is not installed.
    """
    if not FIONA_AVAILABLE:
        raise MissingDependencyError(ERROR_FIONA_REQUIRED)

    vector_path = Path(vector_path)
    if not vector_path.exists():
        raise RiverVectorError(ERROR_VECTOR_NOT_FOUND.format(path=vector_path))

    features = []
    try:
        with fiona.open(vector_path) as src:
            if len(src) == 0:
                raise RiverGeometryError(ERROR_VECTOR_NO_FEATURES)  # noqa: TRY301
            # Check CRS
            src_crs = src.crs
            for feat in src:
                geom = feat.get("geometry")
                if geom is not None:
                    features.append(
                        {
                            "geometry": geom,
                            "properties": feat.get("properties", {}),
                            "crs": src_crs,
                        }
                    )
    except Exception as e:
        raise RiverVectorError(
            ERROR_VECTOR_READ_FAILED_FMT.format(path=vector_path, e=e)
        ) from e

    if not features:
        raise RiverGeometryError(ERROR_NO_VALID_GEOMETRIES)

    return features


def _transform_geometries(
    features: list[dict[str, Any]],
    target_crs: CRS | str,
) -> list[dict[str, Any]]:
    """Transform geometries to target CRS if necessary.

    Args:
        features: List of feature dictionaries with 'geometry' and 'crs' keys.
        target_crs: Target CRS as rasterio CRS object or string.

    Returns:
        List of features with geometries transformed to target CRS.
    """
    target_crs = CRS.from_user_input(target_crs)
    transformed = []

    for feat in features:
        geom = feat["geometry"]
        src_crs = feat.get("crs")
        if src_crs is None:
            warnings.warn(
                "Feature has no CRS; assuming it matches target CRS. "
                "This may cause misalignment.",
                UserWarning,
                stacklevel=2,
            )
            transformed.append(feat)
            continue

        src_crs = CRS.from_user_input(src_crs)
        if src_crs != target_crs:
            try:
                geom = transform_geom(src_crs, target_crs, geom)
            except Exception as e:
                raise RiverGeometryError(
                    ERROR_TRANSFORM_FAILED_FMT.format(
                        src_crs=src_crs, target_crs=target_crs, e=e
                    )
                ) from e
        transformed.append({**feat, "geometry": geom})

    return transformed


def _filter_river_geometries(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter features to keep only river-like geometries.

    Args:
        features: List of feature dictionaries.

    Returns:
        Filtered list of river features.
    """
    river_features = []
    for feat in features:
        geom = feat["geometry"]
        geom_type = geom.get("type", "")
        # Accept LineString, MultiLineString, Polygon, MultiPolygon
        # (rivers may be represented as centerlines or polygons)
        if geom_type in ("LineString", "MultiLineString", "Polygon", "MultiPolygon"):
            river_features.append(feat)
        elif geom_type == "GeometryCollection":
            # Extract valid sub-geometries
            for sub_geom in geom.get("geometries", []):
                sub_type = sub_geom.get("type", "")
                if sub_type in (
                    "LineString",
                    "MultiLineString",
                    "Polygon",
                    "MultiPolygon",
                ):
                    river_features.append({**feat, "geometry": sub_geom})

    if not river_features:
        raise RiverGeometryError(ERROR_NO_RIVER_GEOMETRIES_FMT)

    return river_features


def rasterize_river_mask(  # noqa: PLR0913, PLR0917, PLR0912
    vector_path: Path | str,
    reference_transform: Affine | tuple[float, ...],
    reference_width: int,
    reference_height: int,
    reference_crs: CRS | str = "EPSG:4326",
    buffer_meters: float = 0.0,
    all_touched: bool = True,
) -> np.ndarray:
    """Rasterize river vector into a Boolean mask aligned to reference grid.

    Args:
        vector_path: Path to river vector file (GeoJSON, GeoPackage, Shapefile).
        reference_transform: Affine transform of reference DEM (6-tuple or Affine).
        reference_width: Width of reference DEM in pixels.
        reference_height: Height of reference DEM in pixels.
        reference_crs: CRS of reference DEM (default: EPSG:4326).
        buffer_meters: Buffer distance in meters to apply to river geometries.
                       For geographic CRS, this is in meters.
                       For projected CRS, this is in the CRS linear units.
        all_touched: If True, all pixels touched by geometry are burned.
                     If False, only pixels whose center is within geometry.

    Returns:
        Boolean array of shape (reference_height, reference_width) where
        True marks river cells.

    Raises:
        RiverVectorError: If vector file cannot be read.
        RiverGeometryError: If no valid river geometries found, or invalid buffer distance.
        RiverMaskEmptyError: If rasterized mask contains no True cells.
        MissingDependencyError: If fiona is not installed, or pyproj/shapely for buffering.
    """
    reference_transform = (
        Affine(*reference_transform)
        if not isinstance(reference_transform, Affine)
        else reference_transform
    )
    reference_crs = CRS.from_user_input(reference_crs)

    # Validate buffer distance
    if buffer_meters < 0:
        raise RiverGeometryError(ERROR_BUFFER_NEGATIVE_FMT)
    if not np.isfinite(buffer_meters):
        raise RiverGeometryError(ERROR_BUFFER_FINITE_FMT)

    # Read vector file
    features = _read_vector_file(vector_path)

    # Filter river geometries
    features = _filter_river_geometries(features)

    # Transform to reference CRS if needed
    features = _transform_geometries(features, reference_crs)

    # Apply buffer if requested
    if buffer_meters > 0:
        if not BUFFERING_AVAILABLE:
            raise MissingDependencyError(ERROR_BUFFER_DEPS_MISSING_FMT)

        # Create transformer for buffering in meters
        if reference_crs.is_geographic:
            # Geographic CRS: buffer_meters is in meters, use local azimuthal equidistant projection
            bounds = rasterio.transform.array_bounds(
                reference_height, reference_width, reference_transform
            )
            center_lon = (bounds[0] + bounds[2]) / 2
            center_lat = (bounds[1] + bounds[3]) / 2
            proj_crs = CRS.from_proj4(
                f"+proj=aeqd +lat_0={center_lat} +lon_0={center_lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
            )
            transformer = pyproj.Transformer.from_crs(
                reference_crs, proj_crs, always_xy=True
            )
            inverse_transformer = pyproj.Transformer.from_crs(
                proj_crs, reference_crs, always_xy=True
            )

            buffered_geoms = []
            for feat in features:
                geom = shape(feat["geometry"])
                # Transform to projected CRS, buffer, transform back
                geom_proj = shapely_transform(transformer.transform, geom)
                geom_buffered = geom_proj.buffer(buffer_meters)
                geom_back = shapely_transform(
                    inverse_transformer.transform, geom_buffered
                )
                buffered_geoms.append(geom_back.__geo_interface__)
            # Replace geometries with buffered versions
            for i, feat in enumerate(features):
                feat["geometry"] = buffered_geoms[i]
        else:
            # Projected CRS: buffer distance is in CRS linear units
            # Convert buffer_meters to CRS units
            # Check if CRS uses meters as units
            if reference_crs.is_projected:
                unit_name = reference_crs.linear_units
                if unit_name in ("metre", "meter"):
                    buffer_distance = buffer_meters
                else:
                    # For other units, convert using unit conversion factor
                    unit_factor = getattr(reference_crs, "linear_units_factor", 1.0)
                    buffer_distance = (
                        buffer_meters / unit_factor
                        if unit_factor > 0
                        else buffer_meters
                    )
            else:
                # Geographic CRS fallback - buffer_meters is already in meters
                buffer_distance = buffer_meters

            buffered_geoms = []
            for feat in features:
                geom = shape(feat["geometry"])
                geom_buffered = geom.buffer(buffer_distance)
                buffered_geoms.append(geom_buffered.__geo_interface__)
            for i, feat in enumerate(features):
                feat["geometry"] = buffered_geoms[i]

    # Prepare geometries for rasterization
    geometries = [(feat["geometry"], 1) for feat in features]

    # Rasterize
    mask = rasterize(
        geometries,
        out_shape=(reference_height, reference_width),
        transform=reference_transform,
        fill=0,
        dtype=np.uint8,
        all_touched=all_touched,
    )

    # Convert to boolean
    bool_mask = mask.astype(bool)

    if not bool_mask.any():
        raise RiverMaskEmptyError(ERROR_MASK_EMPTY_FMT)

    return bool_mask


def create_river_mask_from_geojson_dict(  # noqa: PLR0913, PLR0917
    geojson_dict: dict[str, Any],
    reference_transform: Affine | tuple[float, ...],
    reference_width: int,
    reference_height: int,
    reference_crs: CRS | str = "EPSG:4326",
    all_touched: bool = True,
) -> np.ndarray:
    """Create river mask from a GeoJSON-like dictionary (for testing).

    Args:
        geojson_dict: Dictionary with 'type' (FeatureCollection) and 'features'.
        reference_transform: Affine transform of reference DEM.
        reference_width: Width of reference DEM.
        reference_height: Height of reference DEM.
        reference_crs: CRS of reference DEM.
        all_touched: If True, all pixels touched by geometry are burned.

    Returns:
        Boolean array of shape (reference_height, reference_width).
    """
    reference_transform = (
        Affine(*reference_transform)
        if not isinstance(reference_transform, Affine)
        else reference_transform
    )
    reference_crs = CRS.from_user_input(reference_crs)

    if geojson_dict.get("type") != "FeatureCollection":
        raise RiverGeometryError(ERROR_NOT_FEATURE_COLLECTION_FMT)

    features = []
    for feat in geojson_dict.get("features", []):
        geom = feat.get("geometry")
        if geom is not None:
            features.append(
                {
                    "geometry": geom,
                    "properties": feat.get("properties", {}),
                    "crs": reference_crs,  # Assume same CRS for test fixtures
                }
            )

    features = _filter_river_geometries(features)
    features = _transform_geometries(features, reference_crs)

    geometries = [(feat["geometry"], 1) for feat in features]

    mask = rasterize(
        geometries,
        out_shape=(reference_height, reference_width),
        transform=reference_transform,
        fill=0,
        dtype=np.uint8,
        all_touched=all_touched,
    )

    bool_mask = mask.astype(bool)

    if not bool_mask.any():
        raise RiverMaskEmptyError(ERROR_MASK_EMPTY_SIMPLE_FMT)

    return bool_mask


def write_river_mask_geotiff(
    mask: np.ndarray,
    dst_path: Path | str,
    reference_transform: Affine | tuple[float, ...],
    reference_crs: CRS | str = "EPSG:4326",
    nodata: int = 255,
) -> dict[str, Any]:
    """Write river mask as GeoTIFF for inspection.

    Args:
        mask: Boolean river mask array.
        dst_path: Output path.
        reference_transform: Affine transform.
        reference_crs: CRS string or object.
        nodata: NoData value for output (default 255 for uint8).

    Returns:
        Dictionary with output metadata.
    """
    reference_transform = (
        Affine(*reference_transform)
        if not isinstance(reference_transform, Affine)
        else reference_transform
    )
    reference_crs = CRS.from_user_input(reference_crs)

    output_path = Path(dst_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": mask.shape[1],
        "height": mask.shape[0],
        "count": 1,
        "crs": reference_crs,
        "transform": reference_transform,
        "compress": "lzw",
        "nodata": nodata,
    }

    # Write: 1 = river, 0 = non-river, nodata = outside domain
    output_data = mask.astype(np.uint8)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(output_data, 1)

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
