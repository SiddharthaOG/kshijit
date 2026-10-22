"""Synthetic-terrain flood-connectivity model.

Provides ``compute_flood_extent`` — a threshold-connectivity flood model that
identifies cells flooded given a water-level threshold and a river-source mask,
using 4-neighbor (cardinal) connectivity.
"""

from __future__ import annotations

import numpy as np


def compute_flood_extent(
    elevation: np.ndarray,
    source_mask: np.ndarray,
    water_level: float,
) -> np.ndarray:
    """Compute flood extent using threshold connectivity.

    For a given terrain grid, river-source mask, and water-level threshold,
    identifies cells that:

    1. Have valid (finite) elevation data.
    2. Have elevation less than or equal to the specified water level.
    3. Are connected to an eligible river-source cell through eligible
       terrain cells (4-neighbor connectivity: up, down, left, right).

    Parameters
    ----------
    elevation:
        2-D NumPy array of terrain elevations.  NaN and ``inf`` are treated
        as invalid terrain that cannot be flooded or traversed.
    source_mask:
        2-D boolean NumPy array of the same shape as *elevation*.  True
        marks cells that are designated as river-source cells.
    water_level:
        Water-level threshold.  Must be finite (not NaN or ``inf``).

        A source cell is eligible only if its terrain is valid (finite) and
        its elevation is at or below *water_level*.

    Returns
    -------
    flooded:
        2-D boolean NumPy array of the same shape as the inputs.  True marks
        cells that are flooded (i.e. connected to an eligible source cell
        through cells whose elevation is at or below the threshold).

    Raises
    ------
    TypeError
        If *elevation* or *source_mask* is not a NumPy array, or if they are
        not 2-D, or if *source_mask* is not Boolean.
    ValueError
        If *elevation* and *source_mask* shapes differ, or if *elevation* or
        *source_mask* is empty, or if *water_level* is not finite.
    """
    # ---- validate elevation ---------------------------------------------------
    if not isinstance(elevation, np.ndarray):
        raise TypeError("elevation must be a NumPy array.")
    if elevation.ndim != 2:
        raise TypeError(f"elevation must be 2-D, got {elevation.ndim}-D array.")
    if elevation.size == 0:
        raise ValueError("elevation must be a non-empty array.")

    # ---- validate source_mask -------------------------------------------------
    if not isinstance(source_mask, np.ndarray):
        raise TypeError("source_mask must be a NumPy array.")
    if source_mask.ndim != 2:
        raise TypeError(f"source_mask must be 2-D, got {source_mask.ndim}-D array.")
    if source_mask.size == 0:
        raise ValueError("source_mask must be a non-empty array.")
    if source_mask.dtype != np.bool_:
        raise TypeError("source_mask must be Boolean.")
    if elevation.shape != source_mask.shape:
        raise ValueError(
            f"elevation and source_mask must have the same shape: "
            f"{elevation.shape} vs {source_mask.shape}."
        )

    # ---- validate water_level -------------------------------------------------
    if not np.isfinite(water_level):
        raise ValueError("water_level must be a finite number (not NaN or inf).")

    # ---- work on copies so we don't modify caller's arrays --------------------
    elev = elevation.copy()
    src = source_mask.copy()

    # ---- treat NaN / inf elevation as invalid (cannot be flooded/traversed) ---
    # NaN and ±inf elevations are invalid; they block connectivity.
    elev_is_invalid = np.isnan(elev) | np.isinf(elev)

    # ---- identify eligible source cells: finite elevation AND at or below threshold
    # Use the original elevation array to avoid sentinel-value issues when
    # water_level is near the maximum representable finite float.
    eligible_sources = src & ~elev_is_invalid & (elevation <= water_level)

    # Mark invalid elevations as above threshold so they are never traversed during BFS.
    # The sentinel value is a pragmatic choice; invalid cells are already excluded
    # from eligible_sources and the BFS neighbor check also guards against them.
    elev[elev_is_invalid] = water_level + 1.0

    # ---- if no eligible source cells, return all-false mask ------------------
    if not eligible_sources.any():
        return np.zeros_like(elev, dtype=bool)

    # ---- 4-neighbor BFS flood fill -------------------------------------------
    rows, cols = elev.shape
    flooded = np.zeros_like(elev, dtype=bool)

    # Collect all eligible source cells as starting points
    queue = []
    for r in range(rows):
        for c in range(cols):
            if eligible_sources[r, c]:
                flooded[r, c] = True
                queue.append((r, c))

    # BFS using a list + index pointer (no deque import needed for simplicity)
    idx = 0
    while idx < len(queue):
        r, c = queue[idx]
        idx += 1

        # Explore 4 neighbors: up, down, left, right
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not flooded[nr, nc]:
                # Cell is floodable only if its elevation is valid and at or below threshold
                if not elev_is_invalid[nr, nc] and elev[nr, nc] <= water_level:
                    flooded[nr, nc] = True
                    queue.append((nr, nc))

    return flooded