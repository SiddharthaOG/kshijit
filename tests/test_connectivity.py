"""Deterministic tests for ``kshitij_model.connectivity.compute_flood_extent``.

Uses ``pytest.raises`` for expected-exception tests and direct Boolean
assertions (no ``is True`` / ``is False`` on NumPy scalars).
"""

import numpy as np
import pytest

from kshitij_model.connectivity import compute_flood_extent


def test_simple_connected_corridor():
    """A simple connected corridor of below-threshold cells is flooded."""
    elevation = np.array(
        [
            [5, 5, 5, 5, 5],
            [5, 3, 3, 3, 5],
            [5, 3, 1, 3, 5],
            [5, 3, 3, 3, 5],
            [5, 5, 5, 5, 5],
        ],
        dtype=float,
    )
    source = np.array(
        [
            [False, False, False, False, False],
            [False, True, False, False, False],
            [False, False, False, False, False],
            [False, False, False, False, False],
            [False, False, False, False, False],
        ],
        dtype=bool,
    )
    result = compute_flood_extent(elevation, source, water_level=3)
    # Center cell (elevation=1) should be flooded
    assert result[2, 2]
    # Source cell should be flooded
    assert result[1, 1]
    # Top row should not be flooded (elevation=5 > threshold=3)
    assert not result[0, :].any()


def test_isolated_low_depression():
    """An isolated low-elevation depression is excluded if no eligible source."""
    elevation = np.array([[10, 10, 10], [10, 1, 10], [10, 10, 10]], dtype=float)
    source = np.array(
        [[False, False, False], [False, True, False], [False, False, False]],
        dtype=bool,
    )
    result = compute_flood_extent(elevation, source, water_level=0.5)
    # water_level=0.5 < elevation=1, so no cells should be flooded
    assert result.sum() == 0
    assert result.shape == (3, 3)
    assert result.dtype == bool


def test_above_threshold_blocks_connectivity():
    """An above-threshold cell blocks connectivity in a corridor."""
    # Corridor: source at left, target at right, barrier in middle
    # Source (0,0) elev=1 -> (0,1) elev=2 -> BARRIER (0,2) elev=5 -> target (0,3) elev=2
    elevation = np.array([[1, 2, 5, 2]], dtype=float)
    source = np.array([[True, False, False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    # Source cell should be flooded (elev=1 <= 3)
    assert result[0, 0]
    # Cell (0,1) should be flooded (elev=2 <= 3, connected to source)
    assert result[0, 1]
    # Barrier cell (0,2) should NOT be flooded (elev=5 > 3)
    assert not result[0, 2]
    # Target cell (0,3) should NOT be flooded (blocked by barrier)
    assert not result[0, 3]


def test_diagonal_only_no_connectivity():
    """Diagonally positioned low cell is NOT connected under 4-neighbor rules.

    Elevation ``[[1, 5], [5, 1]]`` with source at (0,0) and water_level=1:
    - Source cell (0,0) elevation=1 <= threshold, so it is flooded.
    - Cell (1,1) elevation=1 is diagonally adjacent but not connected via
      4-neighbor (up/down/left/right) path because the orthogonal cells
      (0,1) and (1,0) have elevation=5 > threshold, blocking passage.
    - Therefore (1,1) must remain unflooded.
    """
    elevation = np.array([[1, 5], [5, 1]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=1)
    # Source cell should be flooded
    assert result[0, 0]
    # Diagonally positioned cell must NOT be flooded (blocked by above-threshold orthogonals)
    assert not result[1, 1]


def test_source_above_threshold_returns_empty():
    """A source cell above the threshold produces an all-false mask."""
    elevation = np.array([[5, 2], [2, 2]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    # Source at (0,0) has elevation=5 > 3, so not eligible
    assert result.sum() == 0
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_multiple_eligible_sources():
    """Multiple eligible source cells work correctly."""
    elevation = np.array([[1, 1, 1], [1, 5, 1], [1, 1, 1]], dtype=float)
    source = np.array(
        [[True, False, False], [False, False, False], [False, False, True]],
        dtype=bool,
    )
    result = compute_flood_extent(elevation, source, water_level=1)
    # Perimeter cells have elevation=1 <= 1 and should be connected
    assert result[0, 0]
    assert result[0, 1]
    assert result[0, 2]
    assert result[1, 0]
    assert result[1, 2]
    assert result[2, 0]
    assert result[2, 1]
    assert result[2, 2]
    # Center should NOT be flooded (elevation=5 > 1)
    assert not result[1, 1]


def test_nan_blocks_connectivity():
    """NaN elevation cells block connectivity."""
    elevation = np.array([[1, np.nan, 1]], dtype=float)
    source = np.array([[True, False, True]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=2)
    # Left and right sources should be flooded
    assert result[0, 0]
    assert result[0, 2]
    # The NaN cell itself should not be flooded
    assert not result[0, 1]


def test_inf_blocks_connectivity():
    """Positive infinity elevation cells block connectivity."""
    elevation = np.array([[1, np.inf, 1]], dtype=float)
    source = np.array([[True, False, True]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=2)
    # Left and right sources should be flooded
    assert result[0, 0]
    assert result[0, 2]
    # The inf cell itself should not be flooded
    assert not result[0, 1]


def test_negative_inf_blocks_connectivity():
    """Negative infinity elevation cells block connectivity."""
    elevation = np.array([[1, -np.inf, 1]], dtype=float)
    source = np.array([[True, False, True]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=2)
    # Left and right sources should be flooded
    assert result[0, 0]
    assert result[0, 2]
    # The -inf cell itself should not be flooded
    assert not result[0, 1]


def test_inf_source_cell_with_max_water_level():
    """An infinite elevation source cell is never flooded, even at max water level.

    Uses np.finfo(float).max as water_level to test the edge case where
    water_level + 1.0 does not produce a larger finite value.
    """
    elevation = np.array([[np.inf]], dtype=float)
    source = np.array([[True]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=np.finfo(float).max)
    # The infinite-elevation source cell must NOT be flooded
    assert result.shape == (1, 1)
    assert not result[0, 0]


def test_invalid_source_mask_dtype_raises():
    """Non-Boolean source_mask raises TypeError."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    # Integer array instead of Boolean
    source = np.array([[1, 0], [0, 1]], dtype=int)
    with pytest.raises(TypeError, match="source_mask must be Boolean"):
        compute_flood_extent(elevation, source, water_level=5.0)


def test_invalid_dimensions_raise():
    """Non-2D arrays raise TypeError."""
    with pytest.raises(TypeError):
        compute_flood_extent(
            np.array([1, 2, 3]), np.array([[True, False]]), water_level=1
        )

    with pytest.raises(TypeError):
        compute_flood_extent(
            np.array([[1, 2], [3, 4]]), np.array([True, False]), water_level=1
        )


def test_mismatched_shapes_raise():
    """Arrays with different shapes raise ValueError."""
    elevation = np.array([[1, 2], [3, 4]], dtype=float)
    source = np.array([[True, False, False]], dtype=bool)
    with pytest.raises(ValueError, match="same shape"):
        compute_flood_extent(elevation, source, water_level=1)


def test_empty_grid_raises():
    """Empty arrays raise ValueError."""
    with pytest.raises(ValueError, match="non-empty"):
        compute_flood_extent(
            np.array([]).reshape(0, 0), np.array([[False]]), water_level=1
        )

    with pytest.raises(ValueError, match="non-empty"):
        compute_flood_extent(
            np.array([[1, 2]]), np.array([]).reshape(0, 0), water_level=1
        )


def test_non_finite_water_level_raises():
    """Non-finite water_level raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        compute_flood_extent(
            np.array([[1.0]]), np.array([[True]]), water_level=float("nan")
        )

    with pytest.raises(ValueError, match="finite"):
        compute_flood_extent(
            np.array([[1.0]]), np.array([[True]]), water_level=float("inf")
        )


def test_input_arrays_unchanged():
    """Input arrays must not be modified by the function."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, True]], dtype=bool)
    original_elev = elevation.copy()
    original_src = source.copy()

    compute_flood_extent(elevation, source, water_level=5.0)

    assert np.array_equal(elevation, original_elev), "elevation array was modified!"
    assert np.array_equal(source, original_src), "source_mask array was modified!"


# =============================================================================
# Part A hardening: elevation dtype validation
# =============================================================================


def test_elevation_bool_dtype_raises():
    """Boolean elevation dtype raises TypeError."""
    elevation = np.array([[True, False], [False, True]], dtype=bool)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(
        TypeError, match="elevation must have a supported numeric dtype"
    ):
        compute_flood_extent(elevation, source, water_level=1.0)


def test_elevation_complex_dtype_raises():
    """Complex elevation dtype raises TypeError."""
    elevation = np.array([[1 + 2j, 2 + 3j], [3 + 4j, 4 + 5j]], dtype=complex)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(
        TypeError, match="elevation must have a supported numeric dtype"
    ):
        compute_flood_extent(elevation, source, water_level=5.0)


def test_elevation_object_dtype_raises():
    """Object elevation dtype raises TypeError."""
    elevation = np.array([[1, 2], [3, 4]], dtype=object)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(
        TypeError, match="elevation must have a supported numeric dtype"
    ):
        compute_flood_extent(elevation, source, water_level=5.0)


def test_elevation_string_dtype_raises():
    """String elevation dtype raises TypeError."""
    elevation = np.array([["1", "2"], ["3", "4"]], dtype=str)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(
        TypeError, match="elevation must have a supported numeric dtype"
    ):
        compute_flood_extent(elevation, source, water_level=5.0)


def test_elevation_int8_accepted():
    """Signed integer elevation dtype (int8) is accepted."""
    elevation = np.array([[1, 2], [3, 4]], dtype=np.int8)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_int32_accepted():
    """Signed integer elevation dtype (int32) is accepted."""
    elevation = np.array([[1, 2], [3, 4]], dtype=np.int32)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_uint16_accepted():
    """Unsigned integer elevation dtype (uint16) is accepted."""
    elevation = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_float32_accepted():
    """Float32 elevation dtype is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3.0)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_float64_accepted():
    """Float64 elevation dtype is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3.0)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_longdouble_accepted():
    """Longdouble (extended precision) elevation dtype is accepted where available."""
    if hasattr(np, "longdouble"):
        elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.longdouble)
        source = np.array([[True, False], [False, False]], dtype=bool)
        result = compute_flood_extent(elevation, source, water_level=3.0)
        assert result.shape == (2, 2)
        assert result.dtype == bool


# =============================================================================
# Part A hardening: water_level validation
# =============================================================================


def test_water_level_bool_raises():
    """Boolean water_level raises TypeError."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(TypeError, match="water_level must be a real number, not bool"):
        compute_flood_extent(elevation, source, water_level=True)


def test_water_level_complex_raises():
    """Complex water_level raises TypeError."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(TypeError, match="water_level must be a real number"):
        compute_flood_extent(elevation, source, water_level=1 + 2j)


def test_water_level_string_raises():
    """String water_level raises TypeError."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(TypeError, match="water_level must be a real number"):
        compute_flood_extent(elevation, source, water_level="3.0")


def test_water_level_none_raises():
    """None water_level raises TypeError."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(TypeError, match="water_level must be a real number"):
        compute_flood_extent(elevation, source, water_level=None)


def test_water_level_numpy_int32_accepted():
    """NumPy int32 water_level is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=np.int32(3))
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_water_level_numpy_float64_accepted():
    """NumPy float64 water_level is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=np.float64(3.0))
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_water_level_python_int_accepted():
    """Python int water_level is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_water_level_python_float_accepted():
    """Python float water_level is accepted."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3.0)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_water_level_numpy_longdouble_accepted():
    """NumPy longdouble water_level is accepted where available."""
    if hasattr(np, "longdouble"):
        elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
        source = np.array([[True, False], [False, False]], dtype=bool)
        result = compute_flood_extent(elevation, source, water_level=np.longdouble(3.0))
        assert result.shape == (2, 2)
        assert result.dtype == bool


def test_water_level_overflow_raises():
    """Extremely large Python int water_level raises ValueError (not OverflowError)."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    with pytest.raises(ValueError, match="too large to convert to float"):
        compute_flood_extent(elevation, source, water_level=10**400)


# =============================================================================
# Valid integer and floating-point elevation inputs
# =============================================================================


def test_elevation_int16_accepted():
    """Signed integer elevation dtype (int16) is accepted."""
    elevation = np.array([[1, 2], [3, 4]], dtype=np.int16)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


def test_elevation_uint8_accepted():
    """Unsigned integer elevation dtype (uint8) is accepted."""
    elevation = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=3)
    assert result.shape == (2, 2)
    assert result.dtype == bool


# =============================================================================
# Property / invariant tests
# =============================================================================


def test_monotonicity_water_level():
    """Increasing water level must not decrease flooded area (monotonicity)."""
    elevation = np.array(
        [
            [5, 4, 3, 2, 1],
            [5, 4, 3, 2, 1],
            [5, 4, 3, 2, 1],
            [5, 4, 3, 2, 1],
            [5, 4, 3, 2, 1],
        ],
        dtype=float,
    )
    source = np.array(
        [[False, False, True, False, False]] * 5,
        dtype=bool,
    )
    # Test multiple increasing water levels
    levels = [1.0, 2.0, 3.0, 4.0, 5.0]
    flooded_areas = []
    for level in levels:
        result = compute_flood_extent(elevation, source, water_level=level)
        flooded_areas.append(result.sum())
    # Flooded area must be monotonically non-decreasing
    for i in range(1, len(flooded_areas)):
        assert flooded_areas[i] >= flooded_areas[i - 1], (
            f"Flooded area decreased from level {levels[i - 1]} to {levels[i]}"
        )


def test_flooded_cell_validity():
    """Every flooded cell must have finite elevation <= water_level."""
    elevation = np.array(
        [
            [1, 2, np.nan, 4, 5],
            [1, np.inf, 3, 4, 5],
            [1, 2, 3, -np.inf, 5],
            [1, 2, 3, 4, 5],
        ],
        dtype=float,
    )
    source = np.array(
        [[True, False, False, False, False]] * 4,
        dtype=bool,
    )
    water_level = 3.0
    result = compute_flood_extent(elevation, source, water_level=water_level)
    # Every flooded cell must have finite elevation <= water_level
    flooded_indices = np.where(result)
    for r, c in zip(*flooded_indices, strict=False):
        assert np.isfinite(elevation[r, c]), (
            f"Flooded cell ({r},{c}) has non-finite elevation"
        )
        assert elevation[r, c] <= water_level + 1e-10, (
            f"Flooded cell ({r},{c}) elevation {elevation[r, c]} > water_level {water_level}"
        )


def test_input_immutability_property():
    """Input arrays must never be modified, even with edge cases."""
    elevation = np.array([[1.0, np.nan, 3.0], [4.0, 5.0, 6.0]], dtype=float)
    source = np.array([[True, False, False], [False, True, False]], dtype=bool)
    original_elev = elevation.copy()
    original_src = source.copy()

    compute_flood_extent(elevation, source, water_level=5.0)

    # Use equal_nan=True to handle NaN comparison
    assert np.array_equal(elevation, original_elev, equal_nan=True), (
        "elevation array was modified!"
    )
    assert np.array_equal(source, original_src), "source_mask array was modified!"
    # Also verify NaN positions preserved
    assert np.isnan(elevation[0, 1]), "NaN position was modified"


def test_water_level_precision_contract():
    """Water level is converted to Python float (IEEE 754 double precision).

    This test documents the conversion behavior: np.longdouble and other
    extended-precision types are converted to Python float (IEEE 754 double),
    which may lose precision. The contract guarantees finite conversion
    but does not preserve extended precision.
    """
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)

    # np.longdouble water_level is accepted but converted to Python float
    if hasattr(np, "longdouble"):
        ld_val = np.longdouble("3.1234567890123456789")
        result = compute_flood_extent(
            np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float),
            np.array([[True, False], [False, False]], dtype=bool),
            water_level=ld_val,
        )
        assert result.shape == (2, 2)
        assert result.dtype == bool

    # Verify that Python float is the internal representation
    wl = 3.14159265358979323846264338327950288419716939937510
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)
    result = compute_flood_extent(elevation, source, water_level=wl)
    assert result.shape == (2, 2)


# ===========================================================================
# NoData sentinel regression tests
# ===========================================================================


def test_nodata_sentinel_blocks_connectivity():
    """An explicit NoData sentinel blocks flood connectivity.

    When nodata is supplied, cells equal to the sentinel are treated as
    invalid terrain even if their numeric value is <= water_level.
    """
    elevation = np.array([[1.0, -32768.0, 2.0]], dtype=float)
    source = np.array([[True, False, False]], dtype=bool)
    water_level = 5.0

    # Without nodata specified, -32768.0 <= 5.0 so the corridor conducts flood
    unhardened = compute_flood_extent(elevation, source, water_level=water_level)
    assert unhardened[0, 0]
    assert unhardened[0, 1]
    assert unhardened[0, 2]

    # With nodata=-32768.0, sentinel cell is invalid and blocks passage
    hardened = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=-32768.0
    )
    assert hardened[0, 0]  # source is flooded
    assert not hardened[0, 1]  # sentinel cell must NOT be flooded
    assert not hardened[0, 2]  # target cell blocked by sentinel


def test_nodata_sentinel_source_ineligible():
    """A source cell with NoData elevation is ineligible and produces empty flood."""
    elevation = np.array([[-32768.0, 2.0]], dtype=float)
    source = np.array([[True, False]], dtype=bool)
    water_level = 5.0

    result = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=-32768.0
    )
    assert result.shape == (1, 2)
    assert result.dtype == bool
    assert result.sum() == 0


def test_nodata_exact_equality_no_tolerance():
    """NoData matching is exact; no default np.isclose tolerances are applied."""
    sentinel = -100.0
    # -100.0001 is close to -100.0 (relative diff 1e-6), which default np.isclose would match
    elevation = np.array([[1.0, -100.0001, -100.0, 2.0]], dtype=float)
    source = np.array([[True, False, False, False]], dtype=bool)
    water_level = 5.0

    result = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=sentinel
    )
    assert result[0, 0]  # source flooded
    assert result[0, 1]  # -100.0001 != -100.0: valid terrain, flooded
    assert not result[0, 2]  # -100.0 == sentinel: invalid, not flooded
    assert not result[0, 3]  # blocked by cell 2


def test_valid_negative_elevations_preserved_and_flooded():
    """Real negative elevations (e.g. coastal depressions) are preserved and floodable."""
    # N16E080 and N16E081 have valid elevations down to -1.5m and -4.5m
    elevation = np.array([[-4.5, -1.5, 0.0, 2.0, 10.0]], dtype=float)
    source = np.array([[True, False, False, False, False]], dtype=bool)
    water_level = 3.0

    result = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=-32767.0
    )
    # Valid elevations <= 3.0 are flooded
    assert result[0, 0]  # -4.5m flooded
    assert result[0, 1]  # -1.5m flooded
    assert result[0, 2]  # 0.0m flooded
    assert result[0, 3]  # 2.0m flooded
    # Elevation 10.0m > 3.0m is not flooded
    assert not result[0, 4]


def test_nodata_nan_sentinel_safe_handling():
    """Passing np.nan or float('nan') as nodata is safely handled."""
    elevation = np.array([[1.0, np.nan, 2.0]], dtype=float)
    source = np.array([[True, False, False]], dtype=bool)
    water_level = 5.0

    # With nodata=np.nan
    result_nan = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=np.nan
    )
    assert result_nan[0, 0]
    assert not result_nan[0, 1]
    assert not result_nan[0, 2]

    # With nodata=float('nan')
    result_float_nan = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=float("nan")
    )
    assert result_float_nan[0, 0]
    assert not result_float_nan[0, 1]
    assert not result_float_nan[0, 2]


def test_nodata_inf_sentinels_safe_handling():
    """Passing infinity as nodata is safely handled."""
    elevation_pos = np.array([[1.0, np.inf, 2.0]], dtype=float)
    source = np.array([[True, False, False]], dtype=bool)
    result_pos = compute_flood_extent(
        elevation_pos, source, water_level=5.0, nodata=np.inf
    )
    assert result_pos[0, 0]
    assert not result_pos[0, 1]
    assert not result_pos[0, 2]

    elevation_neg = np.array([[1.0, -np.inf, 2.0]], dtype=float)
    result_neg = compute_flood_extent(
        elevation_neg, source, water_level=5.0, nodata=-np.inf
    )
    assert result_neg[0, 0]
    assert not result_neg[0, 1]
    assert not result_neg[0, 2]


def test_nodata_backward_compatibility():
    """Callers omitting nodata retain exact default behavior."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, False]], dtype=bool)

    # 3-arg call
    res1 = compute_flood_extent(elevation, source, 2.5)
    # 4-arg explicit None call
    res2 = compute_flood_extent(elevation, source, 2.5, nodata=None)
    assert np.array_equal(res1, res2)
    assert res1[0, 0]
    assert res1[0, 1]
    assert not res1[1, 0]
    assert not res1[1, 1]


def test_nodata_validation_type_errors():
    """Non-numeric non-None nodata types raise TypeError."""
    elevation = np.array([[1.0, 2.0]], dtype=float)
    source = np.array([[True, False]], dtype=bool)

    # Boolean is explicitly rejected
    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=True)

    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=False)

    # String is rejected
    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata="None")

    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata="invalid")

    # Sequence is rejected
    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=[-32768])

    # Complex is rejected
    with pytest.raises(TypeError, match="nodata must be a real number"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=1 + 2j)


def test_nodata_input_immutability():
    """Input elevation array with sentinel is not mutated."""
    elevation = np.array([[1.0, -32768.0, 3.0]], dtype=float)
    source = np.array([[True, False, False]], dtype=bool)
    elev_copy = elevation.copy()
    src_copy = source.copy()

    compute_flood_extent(elevation, source, water_level=5.0, nodata=-32768.0)

    assert np.array_equal(elevation, elev_copy)
    assert np.array_equal(source, src_copy)


def test_nodata_oversized_integer_raises():
    """Oversized Python integers exceeding 64-bit bounds raise ValueError."""
    elevation = np.array([[1.0, 2.0]], dtype=float)
    source = np.array([[True, False]], dtype=bool)

    # 10**100 raises ValueError (not TypeError from NumPy ufunc)
    with pytest.raises(ValueError, match="too large to be represented"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=10**100)

    # Negative oversized integer raises ValueError
    with pytest.raises(ValueError, match="too large to be represented"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=-(10**100))

    # Boundary beyond uint64 (2**64) raises
    with pytest.raises(ValueError, match="too large to be represented"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=2**64)

    # Boundary below int64 (-2**63 - 1) raises
    with pytest.raises(ValueError, match="too large to be represented"):
        compute_flood_extent(elevation, source, water_level=5.0, nodata=-(2**63) - 1)


def test_nodata_64bit_integer_bounds_accepted():
    """Integers at valid 64-bit boundaries are accepted without error."""
    elevation = np.array([[1.0, 2.0]], dtype=float)
    source = np.array([[True, False]], dtype=bool)

    # Max int64
    res_max_i64 = compute_flood_extent(
        elevation, source, water_level=5.0, nodata=2**63 - 1
    )
    assert res_max_i64.shape == (1, 2)

    # Min int64
    res_min_i64 = compute_flood_extent(
        elevation, source, water_level=5.0, nodata=-(2**63)
    )
    assert res_min_i64.shape == (1, 2)

    # Max uint64
    res_max_u64 = compute_flood_extent(
        elevation, source, water_level=5.0, nodata=2**64 - 1
    )
    assert res_max_u64.shape == (1, 2)


def test_nodata_float32_precision_boundary_no_false_match():
    """Large integer sentinel does not falsely match float32 cell due to precision loss."""
    # float32 has 24 bits of mantissa; 2**24 = 16777216 is exact, 16777217 rounds to 16777216
    elevation = np.array([[16777216.0, 16777216.0]], dtype=np.float32)
    source = np.array([[True, False]], dtype=bool)
    water_level = 20000000.0

    # nodata=16777217 cannot be represented in float32 without rounding;
    # it must NOT match elevation cell 16777216.0
    res_inexact = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=16777217
    )
    assert res_inexact[0, 0]  # source is valid and flooded
    assert res_inexact[0, 1]  # neighbor is valid and flooded

    # nodata=16777216 is exact in float32; it MUST match and block
    res_exact = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=16777216
    )
    assert not res_exact[0, 0]
    assert not res_exact[0, 1]


def test_nodata_float64_precision_boundary_no_false_match():
    """Large integer sentinel does not falsely match float64 cell due to precision loss."""
    # float64 has 53 bits of mantissa; 2**53 = 9007199254740992 is exact, 2**53 + 1 rounds
    elevation = np.array([[float(2**53), float(2**53)]], dtype=np.float64)
    source = np.array([[True, False]], dtype=bool)
    water_level = 1e16

    # nodata = 2**53 + 1 cannot be represented in float64; must NOT match 2**53.0
    res_inexact = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=2**53 + 1
    )
    assert res_inexact[0, 0]
    assert res_inexact[0, 1]

    # nodata = 2**53 is exact in float64; MUST match and block
    res_exact = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=2**53
    )
    assert not res_exact[0, 0]
    assert not res_exact[0, 1]


def test_nodata_int64_array_with_float_precision_boundary():
    """Float sentinel does not falsely match adjacent int64 cells across corridor."""
    # Corridor with cell 1 = 2**53 + 1. float(2**53) rounds to 2**53.0
    elevation = np.array([[100, 2**53 + 1, 100]], dtype=np.int64)
    source = np.array([[True, False, False]], dtype=bool)
    water_level = 1e16

    # nodata = float(2**53) must NOT match cell 1 (2**53 + 1); corridor remains open
    res = compute_flood_extent(
        elevation, source, water_level=water_level, nodata=float(2**53)
    )
    assert res[0, 0]  # source flooded
    assert res[0, 1]  # cell 1 flooded
    assert res[0, 2]  # cell 2 reached and flooded

    # If cell 1 is exactly 2**53, it MUST match float(2**53) and block corridor
    elevation_blocked = np.array([[100, 2**53, 100]], dtype=np.int64)
    res_blocked = compute_flood_extent(
        elevation_blocked, source, water_level=water_level, nodata=float(2**53)
    )
    assert res_blocked[0, 0]
    assert not res_blocked[0, 1]
    assert not res_blocked[0, 2]


def test_nodata_unsigned_int_with_negative_sentinel():
    """Negative integer sentinel does not match unsigned integer elevation cells."""
    elevation = np.array([[10, 20]], dtype=np.uint8)
    source = np.array([[True, False]], dtype=bool)
    water_level = 50

    res = compute_flood_extent(elevation, source, water_level=water_level, nodata=-1)
    assert res[0, 0]
    assert res[0, 1]


def test_nodata_int_array_with_fractional_float():
    """Fractional float sentinel does not match integer elevation cells."""
    elevation = np.array([[1, 2]], dtype=np.int32)
    source = np.array([[True, False]], dtype=bool)
    water_level = 5

    res = compute_flood_extent(elevation, source, water_level=water_level, nodata=1.5)
    assert res[0, 0]
    assert res[0, 1]
