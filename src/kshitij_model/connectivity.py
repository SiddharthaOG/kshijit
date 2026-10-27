"""Synthetic-terrain flood-connectivity model.

Provides ``compute_flood_extent`` — a threshold-connectivity flood model that
identifies cells flooded given a water-level threshold and a river-source mask,
using 4-neighbor (cardinal) connectivity.
"""

from __future__ import annotations

import contextlib
from numbers import Real

import numpy as np

# Constants for validation
EXPECTED_NDIM = 2
INT64_MIN = -(2**63)
UINT64_MAX = 2**64 - 1

# 4-neighbor connectivity offsets
NEIGHBOR_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))


class ConnectivityError(Exception):
    """Base exception for connectivity module errors."""

    message: str = "Connectivity error"


class InvalidWaterLevelError(ConnectivityError, ValueError, TypeError):
    """Raised when water_level validation fails."""

    message = "Invalid water level"

    @classmethod
    def not_bool(cls) -> InvalidWaterLevelError:
        return cls("water_level must be a real number, not bool.")

    @classmethod
    def not_real(cls, type_name: str) -> InvalidWaterLevelError:
        return cls(
            f"water_level must be a real number (int or float), got {type_name}."
        )

    @classmethod
    def too_large(cls) -> InvalidWaterLevelError:
        return cls("water_level is too large to convert to float.")

    @classmethod
    def not_finite(cls) -> InvalidWaterLevelError:
        return cls("water_level must be a finite number (not NaN or inf).")


class InvalidNoDataError(ConnectivityError, ValueError, TypeError):
    """Raised when nodata validation fails."""

    message = "Invalid nodata value"

    @classmethod
    def not_bool(cls) -> InvalidNoDataError:
        return cls("nodata must be a real number (int or float) or None, not bool.")

    @classmethod
    def not_real(cls, type_name: str) -> InvalidNoDataError:
        return cls(
            f"nodata must be a real number (int or float) or None, got {type_name}."
        )

    @classmethod
    def too_large(cls) -> InvalidNoDataError:
        return cls("nodata integer value is too large to be represented.")


class InvalidElevationError(ConnectivityError, TypeError, ValueError):
    """Raised when elevation array validation fails."""

    message = "Invalid elevation array"

    @classmethod
    def not_array(cls) -> InvalidElevationError:
        return cls("elevation must be a NumPy array.")

    @classmethod
    def wrong_dim(cls, ndim: int) -> InvalidElevationError:
        return cls(f"elevation must be 2-D, got {ndim}-D array.")

    @classmethod
    def empty(cls) -> InvalidElevationError:
        return cls("elevation must be a non-empty array.")

    @classmethod
    def unsupported_dtype(cls, dtype: np.dtype) -> InvalidElevationError:
        return cls(
            f"elevation must have a supported numeric dtype (integer or real float), "
            f"got {dtype}."
        )


class InvalidSourceMaskError(ConnectivityError, TypeError, ValueError):
    """Raised when source_mask array validation fails."""

    message = "Invalid source mask"

    @classmethod
    def not_array(cls) -> InvalidSourceMaskError:
        return cls("source_mask must be a NumPy array.")

    @classmethod
    def wrong_dim(cls, ndim: int) -> InvalidSourceMaskError:
        return cls(f"source_mask must be 2-D, got {ndim}-D array.")

    @classmethod
    def empty(cls) -> InvalidSourceMaskError:
        return cls("source_mask must be a non-empty array.")

    @classmethod
    def not_boolean(cls) -> InvalidSourceMaskError:
        return cls("source_mask must be Boolean.")


class ShapeMismatchError(ConnectivityError, ValueError):
    """Raised when elevation and source_mask shapes differ."""

    message = "Shape mismatch"

    @classmethod
    def mismatch(
        cls, elev_shape: tuple[int, int], src_shape: tuple[int, int]
    ) -> ShapeMismatchError:
        return cls(
            f"elevation and source_mask must have the same shape: "
            f"{elev_shape} vs {src_shape}."
        )


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
        raise InvalidWaterLevelError.not_bool() from None
    # Must be a real number (int, float, np.integer, np.floating)
    if not isinstance(water_level, Real):
        raise InvalidWaterLevelError.not_real(type(water_level).__name__) from None
    # Convert to Python float for consistency
    try:
        wl = float(water_level)
    except OverflowError as err:
        raise InvalidWaterLevelError.too_large() from err
    if not np.isfinite(wl):
        raise InvalidWaterLevelError.not_finite() from None
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
        raise InvalidNoDataError.not_bool() from None
    if not isinstance(nodata, Real):
        raise InvalidNoDataError.not_real(type(nodata).__name__) from None
    if isinstance(nodata, (int, np.integer)) and (
        nodata < INT64_MIN or nodata > UINT64_MAX
    ):
        raise InvalidNoDataError.too_large() from None
    return nodata


def _identify_nodata_cells(elev: np.ndarray, nodata: Real | None) -> np.ndarray:
    """Identify cells in elev that are exactly equal to nodata sentinel.

    Guarantees exact mathematical equality without precision loss or false
    matches from mixed-dtype conversions.
    """
    if nodata is None:
        return np.zeros(elev.shape, dtype=bool)

    # Float NaN and infinity sentinels: already captured by np.isnan(elev) | np.isinf(elev)
    if isinstance(nodata, (float, np.floating)) and (
        np.isnan(nodata) or np.isinf(nodata)
    ):
        return np.zeros(elev.shape, dtype=bool)

    # Case 1: elev is floating-point (float32, float64, etc.)
    if elev.dtype.kind == "f":
        return _compare_float_elev_with_nodata(elev, nodata)

    # Case 2: elev is an integer array (int8..int64, uint8..uint64)
    if elev.dtype.kind in ("i", "u"):
        return _compare_int_elev_with_nodata(elev, nodata)

    return elev == nodata


def _compare_float_elev_with_nodata(elev: np.ndarray, nodata: Real) -> np.ndarray:
    """Compare floating-point elevation with nodata sentinel."""
    if isinstance(nodata, (int, np.integer)):
        # Check if integer sentinel can be represented in elev.dtype without precision loss.
        nodata_float = elev.dtype.type(nodata)
        if float(nodata_float) != nodata:
            # nodata cannot be represented in elev.dtype without rounding;
            # therefore no cell in elev can equal nodata in exact value.
            return np.zeros(elev.shape, dtype=bool)
        return elev == nodata_float
    return elev == nodata


def _compare_int_elev_with_nodata(elev: np.ndarray, nodata: Real) -> np.ndarray:
    """Compare integer elevation with nodata sentinel."""
    if isinstance(nodata, (float, np.floating)):
        # A float can only equal an integer cell if the float is an exact integer
        if not float(nodata).is_integer():
            return np.zeros(elev.shape, dtype=bool)
        nodata_int = int(nodata)
    else:
        nodata_int = int(nodata)

    # Check if nodata_int falls within the representable range of elev.dtype
    iinfo = np.iinfo(elev.dtype)
    if nodata_int < iinfo.min or nodata_int > iinfo.max:
        return np.zeros(elev.shape, dtype=bool)

    return elev == elev.dtype.type(nodata_int)


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
    _validate_elevation(elevation)

    # ---- validate source_mask -------------------------------------------------
    _validate_source_mask(source_mask, elevation.shape)

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
        elev_is_invalid |= _identify_nodata_cells(elev, nodata)

    # ---- identify eligible source cells: finite non-sentinel AND at or below threshold
    # Use the original elevation array to avoid sentinel-value issues when
    # water_level is near the maximum representable finite float.
    eligible_sources = src & ~elev_is_invalid & (elevation <= water_level)

    # Mark invalid elevations as above threshold so they are never traversed during BFS.
    # The sentinel value is a pragmatic choice; invalid cells are already excluded
    # from eligible_sources and the BFS neighbor check also guards against them.
    with contextlib.suppress(OverflowError, TypeError, ValueError):
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
        for dr, dc in NEIGHBOR_OFFSETS:
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


def _validate_elevation(elevation: np.ndarray) -> None:
    """Validate elevation array."""
    if not isinstance(elevation, np.ndarray):
        raise InvalidElevationError.not_array() from None
    if elevation.ndim != EXPECTED_NDIM:
        raise InvalidElevationError.wrong_dim(elevation.ndim) from None
    if elevation.size == 0:
        raise InvalidElevationError.empty() from None
    if not _is_supported_numeric_dtype(elevation.dtype):
        raise InvalidElevationError.unsupported_dtype(elevation.dtype) from None


def _validate_source_mask(
    source_mask: np.ndarray, elevation_shape: tuple[int, int]
) -> None:
    """Validate source_mask array."""
    if not isinstance(source_mask, np.ndarray):
        raise InvalidSourceMaskError.not_array() from None
    if source_mask.ndim != EXPECTED_NDIM:
        raise InvalidSourceMaskError.wrong_dim(source_mask.ndim) from None
    if source_mask.size == 0:
        raise InvalidSourceMaskError.empty() from None
    if source_mask.dtype != np.bool_:
        raise InvalidSourceMaskError.not_boolean() from None
    if elevation_shape != source_mask.shape:
        raise ShapeMismatchError.mismatch(elevation_shape, source_mask.shape) from None
