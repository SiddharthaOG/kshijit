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
    elevation = np.array(
        [[10, 10, 10], [10, 1, 10], [10, 10, 10]], dtype=float
    )
    source = np.array(
        [[False, False, False], [False, True, False], [False, False, False]],
        dtype=bool,
    )
    result = compute_flood_extent(elevation, source, water_level=0.5)
    # water_level=0.5 < elevation=1, so no cells should be flooded
    assert result is not None
    assert result.sum() == 0


def test_above_threshold_blocks_connectivity():
    """An above-threshold cell blocks connectivity."""
    elevation = np.array(
        [[2, 2, 2], [2, 5, 2], [2, 2, 2]], dtype=float
    )
    source = np.array(
        [[True, False, False], [False, False, False], [False, False, False]],
        dtype=bool,
    )
    result = compute_flood_extent(elevation, source, water_level=3)
    # Source at (0,0) has elevation=2 <= 3, so it is eligible and flooded
    assert result[0, 0]
    # No other cells should be flooded since center (elevation=5) blocks
    assert result.sum() == 1


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
    assert result is not None
    assert result.sum() == 0


def test_multiple_eligible_sources():
    """Multiple eligible source cells work correctly."""
    elevation = np.array(
        [[1, 1, 1], [1, 5, 1], [1, 1, 1]], dtype=float
    )
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


def test_invalid_dimensions_raise():
    """Non-2D arrays raise TypeError."""
    with pytest.raises(TypeError, match("elevation must be a NumPy array")):
        compute_flood_extent(np.array([1, 2, 3]), np.array([[True, False]]), water_level=1)

    with pytest.raises(TypeError, match("source_mask must be a NumPy array")):
        compute_flood_extent(np.array([[1, 2], [3, 4]]), np.array([True, False]), water_level=1)


def test_mismatched_shapes_raise():
    """Arrays with different shapes raise ValueError."""
    with pytest.raises(ValueError, match("must have the same shape")):
        elevation = np.array([[1, 2], [3, 4]], dtype=float)
        source = np.array([[True, False, False]], dtype=bool)
        compute_flood_extent(elevation, source, water_level=1)


def test_empty_grid_raises():
    """Empty arrays raise ValueError."""
    with pytest.raises(ValueError, match("non-empty")):
        compute_flood_extent(np.array([]).reshape(0, 0), np.array([[False]]), water_level=1)

    with pytest.raises(ValueError, match("non-empty")):
        compute_flood_extent(np.array([[1, 2]]), np.array([]).reshape(0, 0), water_level=1)


def test_non_finite_water_level_raises():
    """Non-finite water_level raises ValueError."""
    with pytest.raises(ValueError, match("must be a finite number")):
        compute_flood_extent(np.array([[1.0]]), np.array([[True]]), water_level=float("nan"))

    with pytest.raises(ValueError, match("must be a finite number")):
        compute_flood_extent(np.array([[1.0]]), np.array([[True]]), water_level=float("inf"))


def test_input_arrays_unchanged():
    """Input arrays must not be modified by the function."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    source = np.array([[True, False], [False, True]], dtype=bool)
    original_elev = elevation.copy()
    original_src = source.copy()

    compute_flood_extent(elevation, source, water_level=5.0)

    assert np.array_equal(elevation, original_elev), "elevation array was modified!"
    assert np.array_equal(source, original_src), "source_mask array was modified!"