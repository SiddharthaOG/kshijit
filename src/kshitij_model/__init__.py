"""Kshitij flood-connectivity model — synthetic terrain flood extent computation.

This package provides a standalone, deterministic flood-connectivity algorithm
that operates on a synthetic digital elevation model represented by a 2D NumPy
array. It identifies cells that are flooded given a water-level threshold and
river-source mask, using 4-neighbor (up/down/left/right) connectivity.

The core function ``compute_flood_extent`` is deliberately isolated from Django,
PostGIS, rasterio, GDAL, and any web-layer concerns so that it can be unit-tested
in isolation.
"""

from .connectivity import compute_flood_extent

__all__ = ["compute_flood_extent"]