"""Utilities for M1.5 historical flood validation.

Provides reusable functions for:
- Georeferencing PDF reference maps
- Computing validation metrics (IoU, Precision, Recall, F1, etc.)
- Aligning rasters to common grid
- Generating visual comparison composites
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.warp import reproject

# Constants
MIN_COORDS_FOR_LINESTRING = 2


@dataclass
class ValidationMetrics:
    """Container for validation metrics."""

    tp: int
    fp: int
    fn: int
    tn: int
    iou: float
    precision: float
    recall: float
    f1: float
    area_ratio: float
    valid_pixels: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "iou": self.iou,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "area_ratio": self.area_ratio,
            "valid_pixels": self.valid_pixels,
        }


def compute_confusion_matrix(
    model_flooded: np.ndarray,
    reference_inundated: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Compute TP, FP, FN, TN over valid intersection.

    Args:
        model_flooded: Boolean array from M1.4 model (True = flooded).
        reference_inundated: Boolean array from reference map (True = inundated).
        valid_mask: Optional boolean mask of valid pixels (intersection of both valid areas).

    Returns:
        Tuple of (tp, fp, fn, tn) counts.
    """
    if valid_mask is None:
        valid_mask = np.ones_like(model_flooded, dtype=bool)

    # Only consider valid pixels
    m = model_flooded & valid_mask
    r = reference_inundated & valid_mask

    tp = int(np.sum(m & r))
    fp = int(np.sum(m & ~r))
    fn = int(np.sum(~m & r))
    tn = int(np.sum(~m & ~r & valid_mask))

    return tp, fp, fn, tn


def compute_metrics(tp: int, fp: int, fn: int, tn: int) -> ValidationMetrics:
    """Compute validation metrics from confusion matrix.

    Args:
        tp: True positives.
        fp: False positives.
        fn: False negatives.
        tn: True negatives.

    Returns:
        ValidationMetrics object with all computed metrics.
    """
    # IoU (Jaccard index)
    iou_denom = tp + fp + fn
    iou = tp / iou_denom if iou_denom > 0 else 0.0

    # Precision
    prec_denom = tp + fp
    precision = tp / prec_denom if prec_denom > 0 else 0.0

    recall_denom = tp + fn
    recall = tp / recall_denom if recall_denom > 0 else 0.0

    # F1 Score
    f1_denom = precision + recall
    f1 = 2 * precision * recall / f1_denom if f1_denom > 0 else 0.0

    # Area Ratio
    area_ratio_denom = tp + fn
    area_ratio = (tp + fp) / area_ratio_denom if area_ratio_denom > 0 else 0.0

    return ValidationMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        iou=iou,
        precision=precision,
        recall=recall,
        f1=f1,
        area_ratio=area_ratio,
        valid_pixels=tp + fp + fn + tn,
    )


def compute_metrics_from_arrays(
    model_flooded: np.ndarray,
    reference_inundated: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> ValidationMetrics:
    """Compute all validation metrics directly from arrays.

    Args:
        model_flooded: Boolean array from M1.4 model (True = flooded).
        reference_inundated: Boolean array from reference map (True = inundated).
        valid_mask: Optional boolean mask of valid pixels.

    Returns:
        ValidationMetrics object with all computed metrics.
    """
    tp, fp, fn, tn = compute_confusion_matrix(
        model_flooded, reference_inundated, valid_mask
    )
    return compute_metrics(tp, fp, fn, tn)


def align_rasters_to_common_grid(  # noqa: PLR0913, PLR0917
    src_path: str | Path,
    dst_path: str | Path,
    reference_transform: rasterio.Affine,
    reference_crs: rasterio.crs.CRS,
    reference_width: int,
    reference_height: int,
    resampling: Resampling = Resampling.nearest,
    nodata: float | int | None = None,
) -> dict[str, Any]:
    """Reproject and resample a raster to a common reference grid.

    Args:
        src_path: Path to source raster.
        dst_path: Path to output aligned raster.
        reference_transform: Target affine transform.
        reference_crs: Target CRS.
        reference_width: Target width in pixels.
        reference_height: Target height in pixels.
        resampling: Resampling method (default: nearest for categorical data).
        nodata: NoData value for output.

    Returns:
        Dictionary with output metadata.
    """
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(
            {
                "crs": reference_crs,
                "transform": reference_transform,
                "width": reference_width,
                "height": reference_height,
                "driver": "GTiff",
                "compress": "lzw",
            }
        )
        if nodata is not None:
            profile["nodata"] = nodata

        output_path = Path(dst_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(output_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=reference_transform,
                dst_crs=reference_crs,
                resampling=resampling,
                dst_nodata=profile.get("nodata"),
            )

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


def create_comparison_rgb(
    model_flooded: np.ndarray,
    reference_inundated: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Create RGB comparison composite.

    Encoding:
    - Green (0, 255, 0): True Positive (model flooded, reference inundated)
    - Red (255, 0, 0): False Positive (model flooded, reference dry)
    - Blue (0, 0, 255): False Negative (model dry, reference inundated)
    - Gray (128, 128, 128): True Negative (model dry, reference dry)
    - Black (0, 0, 0): Invalid/NoData

    Args:
        model_flooded: Boolean array from M1.4 model.
        reference_inundated: Boolean array from reference map.
        valid_mask: Optional boolean mask of valid pixels.

    Returns:
        RGB array of shape (H, W, 3) with uint8 values.
    """
    if valid_mask is None:
        valid_mask = np.ones_like(model_flooded, dtype=bool)

    h, w = model_flooded.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)

    m = model_flooded & valid_mask
    r = reference_inundated & valid_mask

    # True Positive: Green
    tp_mask = m & r
    rgb[tp_mask] = [0, 255, 0]

    # False Positive: Red
    fp_mask = m & ~r
    rgb[fp_mask] = [255, 0, 0]

    # False Negative: Blue
    fn_mask = ~m & r & valid_mask
    rgb[fn_mask] = [0, 0, 255]

    # True Negative: Gray
    tn_mask = ~m & ~r & valid_mask
    rgb[tn_mask] = [128, 128, 128]

    # Invalid: Black (already zero)

    return rgb


def write_comparison_rgb(
    rgb_array: np.ndarray,
    dst_path: str | Path,
    reference_transform: rasterio.Affine,
    reference_crs: rasterio.crs.CRS,
    nodata: int = 0,
) -> dict[str, Any]:
    """Write RGB comparison composite as GeoTIFF.

    Args:
        rgb_array: RGB array of shape (H, W, 3).
        dst_path: Output path.
        reference_transform: Affine transform.
        reference_crs: CRS.
        nodata: NoData value.

    Returns:
        Dictionary with output metadata.
    """
    output_path = Path(dst_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": rgb_array.shape[1],
        "height": rgb_array.shape[0],
        "count": 3,
        "crs": reference_crs,
        "transform": reference_transform,
        "compress": "lzw",
        "nodata": nodata,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        for band_idx in range(3):
            dst.write(rgb_array[:, :, band_idx], band_idx + 1)

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


def extract_krishna_river_from_osm(
    bbox: tuple[float, float, float, float],
    output_path: str | Path,
    buffer_deg: float = 0.1,
) -> Path:
    """Extract Krishna River polyline from OSM within bounding box.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84.
        output_path: Output GeoJSON path.
        buffer_deg: Buffer around bbox in degrees.

    Returns:
        Path to output GeoJSON file.
    """

    min_lon, min_lat, max_lon, max_lat = bbox
    # Expand bbox by buffer
    min_lon -= buffer_deg
    min_lat -= buffer_deg
    max_lon += buffer_deg
    max_lat += buffer_deg

    overpass_query = f"""
    [out:json][timeout:60];
    (
      way["waterway"="river"]["name"="Krishna"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["waterway"="river"]["name"="Krishna"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body;
    >;
    out skel qt;
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": overpass_query},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    # Convert to GeoJSON
    features = []
    for element in data.get("elements", []):
        if element["type"] == "way" and "geometry" in element:
            coords = [[node["lon"], node["lat"]] for node in element["geometry"]]
            if len(coords) >= MIN_COORDS_FOR_LINESTRING:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords,
                        },
                        "properties": element.get("tags", {}),
                    }
                )

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(geojson, f)

    return Path(output_path)
