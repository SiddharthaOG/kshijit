"""Tests for raster preprocessing module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from kshitij_model.config import DEMConfig, get_config
from kshitij_model.raster_preprocessing import (
    RasterPreprocessingError,
    build_validity_mask,
    crop_raster,
    inspect_raster,
    mosaic_tiles,
    prepare_model_input,
    write_geotiff,
)


class TestRasterInspection:
    """Tests for raster inspection functionality."""

    def test_inspect_raster_metadata(self, tmp_path: Path):
        """Test that raster metadata is correctly extracted."""
        # Create a synthetic raster
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Create a simple test raster
            with rasterio.open(
                temp_path, "w",
                driver="GTiff",
                dtype="float32",
                width=100,
                height=100,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(79, 16, 80, 17, 100, 100),
                nodata=-32767,
                compress="lzw",
            ) as dst:
                dst.write(np.random.rand(100, 100).astype(np.float32) * 100, 1)

            # Inspect
            meta = inspect_raster(temp_path)

            assert meta["crs"] == "EPSG:4326"
            assert meta["width"] == 100
            assert meta["height"] == 100
            assert meta["dtype"] == "float32"
            assert meta["nodata"] == -32767
            assert meta["count"] == 1
            assert meta["driver"] == "GTiff"
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestCropRaster:
    """Tests for crop_raster function."""

    def test_crop_full_overlap(self, tmp_path: Path):
        """Test cropping when bounds fully contain the raster."""
        # Create source raster
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path, "w",
            driver="GTiff",
            dtype="float32",
            width=100,
            height=100,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, 100, 100),
            nodata=-32767,
            compress="lzw",
        ) as dst:
            dst.write(np.full((100, 100), 10.0, dtype=np.float32), 1)

        dst_path = tmp_path / "cropped.tif"
        crop_raster(
            src_path=src_path,
            dst_path=dst_path,
            bounds=(79.25, 16.25, 79.75, 16.75),
        )

        with rasterio.open(dst_path) as src:
            assert src.width == 50
            assert src.height == 50
            assert src.crs.to_string() == "EPSG:4326"
            assert src.nodata == -32767
            data = src.read(1)
            assert np.all(data == 10.0)


class TestMosaicTiles:
    """Tests for mosaic_tiles function."""

    def test_mosaic_three_tiles(self, tmp_path: Path):
        """Test mosaicking three adjacent tiles."""
        tiles = []
        for i, (lat, lon) in enumerate([(16, 79), (16, 80), (16, 81)]):
            tile_path = Path(tempfile.mktemp(suffix=f"_{i}.tif", dir=tmp_path))
            tiles.append(str(tile_path))

            with rasterio.open(tile_path, "w",
                driver="GTiff",
                dtype="float32",
                width=100,
                height=100,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(lon, lat, lon + 1, lat + 1, 100, 100),
                nodata=-32767,
                compress="lzw",
            ) as dst:
                dst.write(np.full((100, 100), float(i + 1), dtype=np.float32), 1)

        dst_path = tmp_path / "mosaic.tif"
        result = mosaic_tiles(
            tile_paths=[Path(p) for p in tiles],
            dst_path=tmp_path / "mosaic.tif",
            bounds=(79.0, 16.0, 82.0, 17.0),
        )

        with rasterio.open(tmp_path / "mosaic.tif") as src:
            assert src.width == 300
            assert src.height == 100
            assert src.crs.to_string() == "EPSG:4326"
            data = src.read(1)
            assert 1.0 in src.read(1)
            assert 2.0 in src.read(1)
            assert 3.0 in src.read(1)


class TestBuildValidityMask:
    """Tests for build_validity_mask function."""

    def test_nan_masked(self):
        """NaN values should be masked as invalid."""
        data = np.array([[1.0, np.nan, 3.0]], dtype=float)
        mask = build_validity_mask(np.array([[1.0, np.nan, 3.0]]), nodata=None, config_nodata=None)
        assert mask[0, 0]  # valid
        assert not mask[0, 1]  # NaN masked
        assert mask[0, 2]  # valid

    def test_inf_masked(self):
        """Positive infinity should be masked."""
        data = np.array([[1.0, np.inf, 3.0]], dtype=float)
        mask = build_validity_mask(np.array([[1.0, np.inf, 3.0]]), nodata=None, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_negative_inf_masked(self):
        """Negative infinity should be masked."""
        data = np.array([[1.0, -np.inf, 3.0]], dtype=float)
        mask = build_validity_mask(np.array([[1.0, -np.inf, 3.0]]), nodata=None, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_sentinel_masked(self):
        """Sentinel value should be masked."""
        data = np.array([[1.0, -32768.0, 3.0]], dtype=float)
        mask = build_validity_mask(np.array([[1.0, -32768.0, 3.0]]), nodata=-32768.0, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_zero_preserved(self):
        """Zero elevation should be preserved as valid."""
        data = np.array([[0.0, 1.0, 2.0]], dtype=float)
        mask = build_validity_mask(np.array([[0.0, 1.0, 2.0]]), nodata=-32768.0, config_nodata=None)
        assert mask[0, 0]
        assert mask[0, 1]
        assert mask[0, 2]

    def test_negative_elevation_preserved(self):
        """Negative elevations (coastal depressions) should be preserved."""
        data = np.array([[-4.5, -1.5, 0.0, 2.0]], dtype=float)
        mask = build_validity_mask(np.array([[-4.5, -1.5, 0.0, 2.0]]), nodata=-32768.0, config_nodata=None)
        assert all(mask[0])


class TestWriteGeotiff:
    """Tests for write_geotiff function."""

    def test_write_geotiff(self, tmp_path: Path):
        """Test writing a GeoTIFF with proper metadata."""
        data = np.random.rand(100, 100).astype(np.float32) * 100
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": 100,
            "height": 100,
            "count": 1,
            "crs": "EPSG:4326",
            "transform": from_bounds(79, 16, 80, 17, 100, 100),
            "nodata": -32767,
            "compress": "lzw",
        }

        dst_path = tmp_path / "output.tif"
        result = write_geotiff(dst_path, data, profile, nodata=-32767)

        assert result["crs"] == "EPSG:4326"
        assert result["width"] == 100
        assert result["height"] == 100
        assert result["dtype"] == "float32"
        assert result["nodata"] == -32767


class TestPrepareModelInput:
    """Tests for prepare_model_input function."""

    def test_prepare_model_input_valid_data(self, tmp_path: Path):
        """Test preparing model input from valid raster."""
        # Create a test raster
        with rasterio.open(
            tmp_path / "test.tif", "w",
            driver="GTiff",
            dtype="float32",
            width=100,
            height=100,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, 100, 100),
            nodata=-32767,
            compress="lzw",
        ) as dst:
            dst.write(np.full((100, 100), 10.0, dtype=np.float32), 1)

        elevation, validity_mask, metadata = prepare_model_input(
            tmp_path / "test.tif",
            nodata=-32767.0,
        )

        assert elevation.shape == (100, 100)
        assert validity_mask.shape == (100, 100)
        assert validity_mask.dtype == bool
        assert np.all(validity_mask)
        assert metadata["crs"] == "EPSG:4326"
        assert elevation.shape == (100, 100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])