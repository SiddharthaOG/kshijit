"""Synthetic-terrain flood-connectivity model.

Provides ``compute_flood_extent`` — a threshold-connectivity flood model that
identifies cells flooded given a water-level threshold and a river-source mask,
using 4-neighbor (cardinal) connectivity.
"""

from __future__ import annotations

from numbers import Real

import numpy as np


def _is_supported_numeric_dtype(dtype: np.dtype) -> bool:
    """Return True if dtype is a supported real numeric type.

    Supported: integer (signed/unsigned) and real floating-point dtypes.
    Rejected: bool, complex, object, string, datetime, timedelta, void.
    """
    return dtype.kind in ("i", "u", "f")  # signed int, unsigned int, float


def _validate_water_level(water_level) -> float:
    """Validate and coerce water_level to a finite Python float.

    Accepts Python int/float, NumPy integer/floating scalars.
    Rejects: strings, None, complex, bool, non-finite values.
    """
    # Reject bool explicitly (bool is subclass of int in Python)
    if isinstance(water_level, bool):
        raise TypeError("water_level must be a real number, not bool.")
    # Must be a real number (int, float, np.integer, np.floating)
    if not isinstance(water_level, Real):
        raise TypeError(
            f"water_level must be a real number (int or float), got {type(water_level).__name__}."
        )
    # Convert to Python float for consistency
    try:
        wl = float(water_level)
    except OverflowError:
        raise ValueError("water_level is too large to convert to float.")
    if not np.isfinite(wl):
        raise ValueError("water_level must be a finite number (not NaN or inf).")
    return wl


def _validate_nodata(nodata):
    """Validate optional nodata sentinel.

    Accepts None, or real numbers (int, float, NumPy integer/floating scalars),
    including NaN and infinity.
    Rejects: bool, complex, string, sequences, and arbitrary objects.
    Rejects integer values that exceed the range of supported 64-bit integers.
    """
    if nodata is None:
        return None
    if isinstance(nodata, bool):
        raise TypeError(
            "nodata must be a real number (int or float) or None, not bool."
        )
    if not isinstance(nodata, Real):
        raise TypeError(
            f"nodata must be a real number (int or float) or None, got {type(nodata).__name__}."
        )
    if isinstance(nodata, (int, np.integer)) and (
        nodata < -9223372036854775808 or nodata > 18446744073709551615
    ):
        raise ValueError("nodata integer value is too large to be represented.")
    return nodata


def compute_flood_extent(
    elevation: np.ndarray,
    source_mask: np.ndarray,
    water_level,
    nodata: Real | None = None,
) -> np.ndarray:
    """Compute flood extent using threshold connectivity.

    For a given terrain grid, river-source mask, and water-level threshold,
    identifies cells that:

    1. Have valid (finite and non-sentinel) elevation data.
    2. Have elevation less than or equal to the specified water level.
    3. Are connected to an eligible river-source cell through eligible
       terrain cells (4-neighbor connectivity: up, down, left, right).

    Parameters
    ----------
    elevation:
        2-D NumPy array of terrain elevations with a supported numeric dtype
        (integer or real floating-point). NaN and ``inf`` are treated as
        invalid terrain that cannot be flooded or traversed.
    source_mask:
        2-D boolean NumPy array of the same shape as *elevation*. True
        marks cells that are designated as river-source cells.
    water_level:
        Water-level threshold. Must be a finite real number (int or float;
        NumPy integer/floating scalars accepted). Must not be NaN, inf,
        -inf, bool, complex, string, or None.

        A source cell is eligible only if its terrain is valid (finite and
        non-sentinel) and its elevation is at or below *water_level*.
    nodata:
        Optional NoData sentinel value. Can be a real numeric scalar (int, float,
        NumPy integer/floating scalar) or None (default). When specified as a
        finite number, cells in *elevation* that are exactly equal to *nodata*
        are treated as invalid terrain (cannot be flooded, cannot serve as
        eligible sources, and cannot be traversed). If specified as NaN
        (e.g. ``np.nan``) or infinity, all NaN or infinite cells are treated as
        invalid (matching the default handling). No tolerance (such as
        ``np.isclose``) is applied; matching is exact, preserving genuine
        negative elevations.

    Returns
    -------
    flooded:
        2-D boolean NumPy array of the same shape as the inputs. True marks
        cells that are flooded (i.e. connected to an eligible source cell
        through cells whose elevation is at or below the threshold).

    Raises
    ------
    TypeError
        If *elevation* or *source_mask* is not a NumPy array, or if they are
        not 2-D, or if *source_mask* is not Boolean, or if *elevation* dtype
        is not a supported numeric type, or if *water_level* is not a real
        scalar (e.g., string, None, complex, bool), or if *nodata* is not a
        real numeric scalar or None (e.g., bool, string).
    ValueError
        If *elevation* and *source_mask* shapes differ, or if *elevation* or
        *source_mask* is empty, or if *water_level* is not finite, or if
        *nodata* is an integer too large to be represented.
    """
    # ---- validate elevation ---------------------------------------------------
    if not isinstance(elevation, np.ndarray):
        raise TypeError("elevation must be a NumPy array.")
    if elevation.ndim != 2:
        raise TypeError(f"elevation must be 2-D, got {elevation.ndim}-D array.")
    if elevation.size == 0:
        raise ValueError("elevation must be a non-empty array.")
    if not _is_supported_numeric_dtype(elevation.dtype):
        raise TypeError(
            f"elevation must have a supported numeric dtype (integer or real float), "
            f"got {elevation.dtype}."
        )

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

    # ---- validate water_level and nodata --------------------------------------
    water_level = _validate_water_level(water_level)
    nodata = _validate_nodata(nodata)

    # ---- work on copies so we don't modify caller's arrays --------------------
    elev = elevation.copy()
    src = source_mask.copy()

    # ---- treat NaN / inf elevation and nodata sentinel as invalid ------------
    # NaN and ±inf elevations are invalid; they block connectivity.
    elev_is_invalid = np.isnan(elev) | np.isinf(elev)

    if nodata is not None:
        if isinstance(nodata, (float, np.floating)) and np.isnan(nodata):
            # NaN sentinel is already covered by np.isnan(elev) above
            pass
        elif isinstance(nodata, (float, np.floating)) and np.isinf(nodata):
            # Infinite sentinel is already covered by np.isinf(elev) above
            pass
        else:
            # Exact equality matching without tolerance (preserves valid negative elevations)
            elev_is_invalid |= elev == nodata

    # ---- identify eligible source cells: finite non-sentinel AND at or below threshold
    # Use the original elevation array to avoid sentinel-value issues when
    # water_level is near the maximum representable finite float.
    eligible_sources = src & ~elev_is_invalid & (elevation <= water_level)

    # Mark invalid elevations as above threshold so they are never traversed during BFS.
    # The sentinel value is a pragmatic choice; invalid cells are already excluded
    # from eligible_sources and the BFS neighbor check also guards against them.
    try:
        elev[elev_is_invalid] = water_level + 1.0
    except (OverflowError, TypeError, ValueError):
        pass

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
            if (
                0 <= nr < rows
                and 0 <= nc < cols
                and not flooded[nr, nc]
                and not elev_is_invalid[nr, nc]
                and elev[nr, nc] <= water_level
            ):
                flooded[nr, nc] = True
                queue.append((nr, nc))

    return flooded
