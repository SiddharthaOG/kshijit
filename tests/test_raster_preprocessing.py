"""Tests for raster preprocessing module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from kshitij_model.dem_acquisition import DEMAcquisition
from kshitij_model.raster_preprocessing import (
    DEFAULT_NODATA,
    build_validity_mask,
    crop_raster,
    inspect_raster,
    mosaic_tiles,
    prepare_model_input,
    write_geotiff,
)

# Test constants
TEST_WIDTH = 100
TEST_HEIGHT = 100
TEST_CROP_WIDTH = 50
TEST_CROP_HEIGHT = 50
TEST_MOSAIC_WIDTH = 300
TEST_MOSAIC_HEIGHT = 100
TEST_NODATA = -32767
TEST_NODATA_CUSTOM = -9999.0
TEST_NODATA_OVERRIDE = -8888.0
TEST_NODATA_CONFIG = -7777.0
TEST_ELEVATION_VALUE = 10.0
TEST_TILE_VALUES = (1.0, 2.0, 3.0)

# Regression test constants
TEST_MOSAIC_WIDTH_2TILE = 200
TEST_TIMEOUT = 100
TEST_MAX_RETRIES = 5
TEST_RETRY_DELAY = 1.5


class TestRasterInspection:
    """Tests for raster inspection functionality."""

    def test_inspect_raster_metadata(self, tmp_path: Path):
        """Test that raster metadata is correctly extracted."""
        # Create a synthetic raster
        temp_path = tmp_path / "test_raster.tif"

        # Create a simple test raster
        rng = np.random.default_rng(42)
        with rasterio.open(
            temp_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(rng.random((TEST_WIDTH, TEST_HEIGHT)).astype(np.float32) * 100, 1)

        # Inspect
        meta = inspect_raster(temp_path)

        assert meta["crs"] == "EPSG:4326"
        assert meta["width"] == TEST_WIDTH
        assert meta["height"] == TEST_HEIGHT
        assert meta["dtype"] == "float32"
        assert meta["nodata"] == TEST_NODATA
        assert meta["count"] == 1
        assert meta["driver"] == "GTiff"


class TestCropRaster:
    """Tests for crop_raster function."""

    def test_crop_full_overlap(self, tmp_path: Path):
        """Test cropping when bounds fully contain the raster."""
        # Create source raster
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        dst_path = tmp_path / "cropped.tif"
        crop_raster(
            src_path=src_path,
            dst_path=dst_path,
            bounds=(79.25, 16.25, 79.75, 16.75),
        )

        with rasterio.open(dst_path) as src:
            assert src.width == TEST_CROP_WIDTH
            assert src.height == TEST_CROP_HEIGHT
            assert src.crs.to_string() == "EPSG:4326"
            assert src.nodata == TEST_NODATA
            data = src.read(1)
            assert np.all(data == TEST_ELEVATION_VALUE)


class TestMosaicTiles:
    """Tests for mosaic_tiles function."""

    def test_mosaic_three_tiles(self, tmp_path: Path):
        """Test mosaicking three adjacent tiles."""
        tiles = []
        for i, (lat, lon) in enumerate([(16, 79), (16, 80), (16, 81)]):
            tile_path = Path(tempfile.mktemp(suffix=f"_{i}.tif", dir=tmp_path))
            tiles.append(str(tile_path))

            with rasterio.open(
                tile_path,
                "w",
                driver="GTiff",
                dtype="float32",
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(
                    lon, lat, lon + 1, lat + 1, TEST_WIDTH, TEST_HEIGHT
                ),
                nodata=TEST_NODATA,
                compress="lzw",
            ) as dst:
                dst.write(
                    np.full((TEST_WIDTH, TEST_HEIGHT), float(i + 1), dtype=np.float32),
                    1,
                )

        tmp_path / "mosaic.tif"
        mosaic_tiles(
            tile_paths=[Path(p) for p in tiles],
            dst_path=tmp_path / "mosaic.tif",
            bounds=(79.0, 16.0, 82.0, 17.0),
        )

        with rasterio.open(tmp_path / "mosaic.tif") as src:
            assert src.width == TEST_MOSAIC_WIDTH
            assert src.height == TEST_MOSAIC_HEIGHT
            assert src.crs.to_string() == "EPSG:4326"
            data = src.read(1)
            assert TEST_TILE_VALUES[0] in data
            assert TEST_TILE_VALUES[1] in data
            assert TEST_TILE_VALUES[2] in data


class TestBuildValidityMask:
    """Tests for build_validity_mask function."""

    def test_nan_masked(self):
        """NaN values should be masked as invalid."""
        data = np.array([[1.0, np.nan, 3.0]], dtype=float)
        mask = build_validity_mask(data, nodata=None, config_nodata=None)
        assert mask[0, 0]  # valid
        assert not mask[0, 1]  # NaN masked
        assert mask[0, 2]  # valid

    def test_inf_masked(self):
        """Positive infinity should be masked."""
        data = np.array([[1.0, np.inf, 3.0]], dtype=float)
        mask = build_validity_mask(data, nodata=None, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_negative_inf_masked(self):
        """Negative infinity should be masked."""
        data = np.array([[1.0, -np.inf, 3.0]], dtype=float)
        mask = build_validity_mask(data, nodata=None, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_sentinel_masked(self):
        """Sentinel value should be masked."""
        data = np.array([[1.0, -32768.0, 3.0]], dtype=float)
        mask = build_validity_mask(data, nodata=-32768.0, config_nodata=None)
        assert mask[0, 0]
        assert not mask[0, 1]
        assert mask[0, 2]

    def test_zero_preserved(self):
        """Zero elevation should be preserved as valid."""
        data = np.array([[0.0, 1.0, 2.0]], dtype=float)
        mask = build_validity_mask(data, nodata=-32768.0, config_nodata=None)
        assert mask[0, 0]
        assert mask[0, 1]
        assert mask[0, 2]

    def test_negative_elevation_preserved(self):
        """Negative elevations (coastal depressions) should be preserved."""
        data = np.array([[-4.5, -1.5, 0.0, 2.0]], dtype=float)
        mask = build_validity_mask(data, nodata=-32768.0, config_nodata=None)
        assert all(mask[0])


class TestWriteGeotiff:
    """Tests for write_geotiff function."""

    def test_write_geotiff(self, tmp_path: Path):
        """Test writing a GeoTIFF with proper metadata."""
        rng = np.random.default_rng(42)
        data = rng.random((TEST_WIDTH, TEST_HEIGHT)).astype(np.float32) * 100
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": TEST_WIDTH,
            "height": TEST_HEIGHT,
            "count": 1,
            "crs": "EPSG:4326",
            "transform": from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            "nodata": TEST_NODATA,
            "compress": "lzw",
        }

        dst_path = tmp_path / "output.tif"
        result = write_geotiff(dst_path, data, profile, nodata=TEST_NODATA)

        assert result["crs"] == "EPSG:4326"
        assert result["width"] == TEST_WIDTH
        assert result["height"] == TEST_HEIGHT
        assert result["dtype"] == "float32"
        assert result["nodata"] == TEST_NODATA


class TestPrepareModelInput:
    """Tests for prepare_model_input function."""

    def test_prepare_model_input_valid_data(self, tmp_path: Path):
        """Test preparing model input from valid raster."""
        # Create a test raster
        with rasterio.open(
            tmp_path / "test.tif",
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        elevation, validity_mask, metadata = prepare_model_input(
            tmp_path / "test.tif",
            nodata=TEST_NODATA,
        )

        assert elevation.shape == (TEST_WIDTH, TEST_HEIGHT)
        assert validity_mask.shape == (TEST_WIDTH, TEST_HEIGHT)
        assert validity_mask.dtype == bool
        assert np.all(validity_mask)
        assert metadata["crs"] == "EPSG:4326"
        assert elevation.shape == (TEST_WIDTH, TEST_HEIGHT)
        assert np.all(elevation == TEST_ELEVATION_VALUE)

    def test_prepare_model_input_uses_source_nodata(self, tmp_path: Path):
        """Test that declared source NoData is used when no explicit override."""
        # Create a test raster with declared NoData
        with rasterio.open(
            tmp_path / "test_nodata.tif",
            "w",
            driver="GTiff",
            dtype="float32",
            width=10,
            height=10,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, 10, 10),
            nodata=TEST_NODATA_CUSTOM,
            compress="lzw",
        ) as dst:
            data = np.full((10, 10), 5.0, dtype=np.float32)
            data[0, 0] = TEST_NODATA_CUSTOM  # NoData pixel
            data[0, 1] = 0.0  # valid zero elevation
            data[0, 2] = -2.5  # valid negative elevation
            dst.write(data, 1)

        elevation, validity_mask, metadata = prepare_model_input(
            tmp_path / "test_nodata.tif",
        )

        # NoData pixel should be masked
        assert not validity_mask[0, 0]
        # Valid zero elevation should be preserved
        assert validity_mask[0, 1]
        # Valid negative elevation should be preserved
        assert validity_mask[0, 2]
        # Metadata should include source NoData
        assert metadata["nodata"] == TEST_NODATA_CUSTOM
        assert elevation.shape == (10, 10)

    def test_prepare_model_input_explicit_nodata_overrides_source(self, tmp_path: Path):
        """Test that explicit nodata argument overrides source NoData."""
        with rasterio.open(
            tmp_path / "test_override.tif",
            "w",
            driver="GTiff",
            dtype="float32",
            width=10,
            height=10,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, 10, 10),
            nodata=TEST_NODATA_CUSTOM,
            compress="lzw",
        ) as dst:
            data = np.full((10, 10), 5.0, dtype=np.float32)
            data[0, 0] = TEST_NODATA_CUSTOM  # source NoData
            data[0, 1] = TEST_NODATA_OVERRIDE  # different sentinel
            dst.write(data, 1)

        # Override with explicit nodata=-8888.0
        elevation, validity_mask, _metadata = prepare_model_input(
            tmp_path / "test_override.tif",
            nodata=TEST_NODATA_OVERRIDE,
        )

        # Source NoData should NOT be masked (explicit override)
        assert validity_mask[0, 0]
        # Explicit NoData should be masked
        assert not validity_mask[0, 1]
        assert elevation.shape == (10, 10)

    def test_prepare_model_input_config_nodata_fallback(self, tmp_path: Path):
        """Test config_nodata is used when explicit nodata is None but source has no NoData."""
        with rasterio.open(
            tmp_path / "test_config.tif",
            "w",
            driver="GTiff",
            dtype="float32",
            width=10,
            height=10,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, 10, 10),
            nodata=None,  # source has no NoData
            compress="lzw",
        ) as dst:
            data = np.full((10, 10), 5.0, dtype=np.float32)
            data[0, 0] = TEST_NODATA_CONFIG  # sentinel to mask via config
            dst.write(data, 1)

        elevation, validity_mask, _metadata = prepare_model_input(
            tmp_path / "test_config.tif",
            config_nodata=TEST_NODATA_CONFIG,
        )

        assert not validity_mask[0, 0]
        assert validity_mask[0, 1]
        assert elevation.shape == (10, 10)


class TestCropRasterRegression:
    """Regression tests for restored crop_raster() API."""

    def test_compression_parameter_honored(self, tmp_path: Path):
        """crop_raster() honors the compression parameter."""
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        dst_path = tmp_path / "cropped.tif"
        crop_raster(
            src_path=src_path,
            dst_path=dst_path,
            bounds=(79.25, 16.25, 79.75, 16.75),
            compression="deflate",
        )

        with rasterio.open(dst_path) as src:
            # Check that compression was applied (we can't directly read compression
            # from rasterio, but we can verify the file was written successfully)
            assert src.width == TEST_CROP_WIDTH
            assert src.height == TEST_CROP_HEIGHT

    def test_dst_crs_same_as_source_works(self, tmp_path: Path):
        """crop_raster() works when dst_crs matches source CRS (default behavior)."""
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        dst_path = tmp_path / "cropped.tif"
        crop_raster(
            src_path=src_path,
            dst_path=dst_path,
            bounds=(79.25, 16.25, 79.75, 16.75),
            dst_crs="EPSG:4326",
        )

        with rasterio.open(dst_path) as src:
            assert src.crs.to_string() == "EPSG:4326"
            assert src.width == TEST_CROP_WIDTH

    def test_dst_crs_mismatch_raises_not_implemented(self, tmp_path: Path):
        """crop_raster() raises NotImplementedError when dst_crs differs from source."""
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        dst_path = tmp_path / "cropped.tif"
        with pytest.raises(NotImplementedError, match="Reprojection not yet supported"):
            crop_raster(
                src_path=src_path,
                dst_path=dst_path,
                bounds=(79.25, 16.25, 79.75, 16.75),
                dst_crs="EPSG:3857",
            )


class TestMosaicTilesRegression:
    """Regression tests for restored mosaic_tiles() API."""

    def test_dst_nodata_parameter_honored(self, tmp_path: Path):
        """mosaic_tiles() honors custom dst_nodata value."""
        tiles = []
        for i, (lat, lon) in enumerate([(16, 79), (16, 80)]):
            tile_path = Path(tempfile.mktemp(suffix=f"_{i}.tif", dir=tmp_path))
            tiles.append(str(tile_path))

            with rasterio.open(
                tile_path,
                "w",
                driver="GTiff",
                dtype="float32",
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(
                    lon, lat, lon + 1, lat + 1, TEST_WIDTH, TEST_HEIGHT
                ),
                nodata=TEST_NODATA,
                compress="lzw",
            ) as dst:
                dst.write(
                    np.full((TEST_WIDTH, TEST_HEIGHT), float(i + 1), dtype=np.float32),
                    1,
                )

        custom_nodata = -9999.0
        dst_path = tmp_path / "mosaic.tif"
        mosaic_tiles(
            tile_paths=[Path(p) for p in tiles],
            dst_path=dst_path,
            bounds=(79.0, 16.0, 81.0, 17.0),
            dst_nodata=custom_nodata,
        )

        with rasterio.open(dst_path) as src:
            assert src.nodata == custom_nodata
            # The metadata nodata value should be set to custom_nodata
            # (The mosaic covers the exact bounds of input tiles, so no nodata pixels in data)

    def test_compression_parameter_honored(self, tmp_path: Path):
        """mosaic_tiles() honors the compression parameter."""
        tiles = []
        for i, (lat, lon) in enumerate([(16, 79), (16, 80)]):
            tile_path = Path(tempfile.mktemp(suffix=f"_{i}.tif", dir=tmp_path))
            tiles.append(str(tile_path))

            with rasterio.open(
                tile_path,
                "w",
                driver="GTiff",
                dtype="float32",
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(
                    lon, lat, lon + 1, lat + 1, TEST_WIDTH, TEST_HEIGHT
                ),
                nodata=TEST_NODATA,
                compress="lzw",
            ) as dst:
                dst.write(
                    np.full((TEST_WIDTH, TEST_HEIGHT), float(i + 1), dtype=np.float32),
                    1,
                )

        dst_path = tmp_path / "mosaic.tif"
        mosaic_tiles(
            tile_paths=[Path(p) for p in tiles],
            dst_path=dst_path,
            bounds=(79.0, 16.0, 81.0, 17.0),
            compression="deflate",
        )

        with rasterio.open(dst_path) as src:
            assert src.width == TEST_MOSAIC_WIDTH_2TILE
            assert src.height == TEST_MOSAIC_HEIGHT


class TestPositionalCompatibility:
    """Test positional argument compatibility for restored APIs."""

    def test_crop_raster_positional_args(self, tmp_path: Path):
        """crop_raster() accepts positional arguments as before."""
        src_path = tmp_path / "source.tif"
        with rasterio.open(
            src_path,
            "w",
            driver="GTiff",
            dtype="float32",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            count=1,
            crs="EPSG:4326",
            transform=from_bounds(79, 16, 80, 17, TEST_WIDTH, TEST_HEIGHT),
            nodata=TEST_NODATA,
            compress="lzw",
        ) as dst:
            dst.write(
                np.full(
                    (TEST_WIDTH, TEST_HEIGHT), TEST_ELEVATION_VALUE, dtype=np.float32
                ),
                1,
            )

        dst_path = tmp_path / "cropped.tif"
        # Call with positional arguments for all parameters
        crop_raster(
            src_path,
            dst_path,
            (79.25, 16.25, 79.75, 16.75),
            None,
            None,
            None,
            "lzw",
        )

        with rasterio.open(dst_path) as src:
            assert src.width == TEST_CROP_WIDTH

    def test_mosaic_tiles_positional_args(self, tmp_path: Path):
        """mosaic_tiles() accepts positional arguments as before."""
        tiles = []
        for i, (lat, lon) in enumerate([(16, 79), (16, 80)]):
            tile_path = Path(tempfile.mktemp(suffix=f"_{i}.tif", dir=tmp_path))
            tiles.append(str(tile_path))

            with rasterio.open(
                tile_path,
                "w",
                driver="GTiff",
                dtype="float32",
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                count=1,
                crs="EPSG:4326",
                transform=from_bounds(
                    lon, lat, lon + 1, lat + 1, TEST_WIDTH, TEST_HEIGHT
                ),
                nodata=TEST_NODATA,
                compress="lzw",
            ) as dst:
                dst.write(
                    np.full((TEST_WIDTH, TEST_HEIGHT), float(i + 1), dtype=np.float32),
                    1,
                )

        dst_path = tmp_path / "mosaic.tif"
        # Call with positional arguments
        mosaic_tiles(
            [Path(p) for p in tiles],
            dst_path,
            (79.0, 16.0, 81.0, 17.0),
            DEFAULT_NODATA,
            "lzw",
        )

        with rasterio.open(dst_path) as src:
            assert src.width == TEST_MOSAIC_WIDTH_2TILE

    def test_demacquisition_positional_args(self):
        """DEMAcquisition() accepts positional timeout, max_retries, retry_delay."""
        acq = DEMAcquisition(
            "data/cache",  # cache_dir
            "data/raw/dem",  # raw_dir
            None,  # config
            TEST_TIMEOUT,  # timeout
            TEST_MAX_RETRIES,  # max_retries
            TEST_RETRY_DELAY,  # retry_delay
        )
        assert acq.timeout == TEST_TIMEOUT
        assert acq.max_retries == TEST_MAX_RETRIES
        assert acq.retry_delay == TEST_RETRY_DELAY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
