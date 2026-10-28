"""Tests for M1.4 pipeline orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from kshitij_model.pipeline import (
    PipelineConfig,
    PipelineConfigError,
    PipelineError,
    run_pipeline,
)
from kshitij_model.raster_preprocessing import write_flood_extent
from kshitij_model.river_mask import RiverMaskEmptyError


class TestPipelineConfig:
    """Tests for PipelineConfig validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = PipelineConfig(
            river_vector_path="data/river.geojson",
            water_level=15.0,
        )
        assert config.water_level == 15.0
        assert config.river_vector_path == "data/river.geojson"

    def test_invalid_water_level_none(self):
        """None water_level should raise."""
        with pytest.raises(PipelineConfigError, match="water_level is required"):
            PipelineConfig(river_vector_path="river.geojson", water_level=None)

    def test_invalid_water_level_nan(self):
        """NaN water_level should raise."""
        with pytest.raises(PipelineConfigError, match="finite"):
            PipelineConfig(river_vector_path="river.geojson", water_level=float("nan"))

    def test_invalid_water_level_inf(self):
        """Inf water_level should raise."""
        with pytest.raises(PipelineConfigError, match="finite"):
            PipelineConfig(river_vector_path="river.geojson", water_level=float("inf"))

    def test_missing_river_vector_raises(self):
        """Missing river_vector_path should raise."""
        with pytest.raises(PipelineConfigError, match="river_vector_path is required"):
            PipelineConfig(water_level=15.0, river_vector_path=None)

    def test_invalid_aoi_bounds(self):
        """Invalid AOI bounds should raise."""
        with pytest.raises(PipelineConfigError, match="aoi_bounds must be"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(1.0, 2.0, 3.0),  # Only 3 values
            )

    def test_invalid_aoi_bounds_min_max_ordering(self):
        """AOI bounds with min >= max should raise."""
        with pytest.raises(PipelineConfigError, match="min_lon must be less than max_lon"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(10.0, 2.0, 5.0, 3.0),  # min_lon > max_lon
            )
        with pytest.raises(PipelineConfigError, match="min_lat must be less than max_lat"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(5.0, 10.0, 10.0, 5.0),  # min_lat > max_lat
            )

    def test_invalid_aoi_bounds_out_of_range(self):
        """AOI bounds outside geographic bounds should raise."""
        with pytest.raises(PipelineConfigError, match="longitude must be in"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(-200.0, 10.0, 10.0, 20.0),  # min_lon < -180
            )
        with pytest.raises(PipelineConfigError, match="latitude must be in"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(10.0, -100.0, 20.0, 20.0),  # min_lat < -90
            )

    def test_invalid_aoi_bounds_non_finite(self):
        """Non-finite AOI bounds should raise."""
        with pytest.raises(PipelineConfigError, match="finite"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                aoi_bounds=(float("nan"), 10.0, 20.0, 30.0),
            )

    def test_negative_buffer_raises(self):
        """Negative buffer distance should raise."""
        with pytest.raises(PipelineConfigError, match="river_buffer_meters must be non-negative"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                river_buffer_meters=-10.0,
            )

    def test_nan_buffer_raises(self):
        """NaN buffer distance should raise."""
        with pytest.raises(PipelineConfigError, match="finite"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                river_buffer_meters=float("nan"),
            )

    def test_inf_buffer_raises(self):
        """Infinite buffer distance should raise."""
        with pytest.raises(PipelineConfigError, match="finite"):
            PipelineConfig(
                river_vector_path="river.geojson",
                water_level=15.0,
                river_buffer_meters=float("inf"),
            )


def _create_dummy_dem(
    path: Path, width: int, height: int, transform, crs: str = "EPSG:4326"
):
    """Create a dummy DEM file for testing."""
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
        "nodata": -32767,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((height, width), 10.0, dtype=np.float32), 1)


class TestWriteFloodExtent:
    """Tests for write_flood_extent function."""

    def test_write_flood_extent_three_states(self, tmp_path: Path):
        """Test writing flood extent with three states: flooded, dry, NoData."""
        flooded = np.zeros((100, 100), dtype=bool)
        flooded[50:60, 50:60] = True  # 10x10 flooded block

        validity_mask = np.ones((100, 100), dtype=bool)
        validity_mask[0:10, 0:10] = False  # Top-left corner invalid

        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(0, 0, 10, 10, 100, 100),
            "width": 100,
            "height": 100,
            "bounds": (0, 0, 10, 10),
            "dtype": "float32",
            "nodata": -32767,
        }

        output_path = tmp_path / "flood_extent.tif"
        meta = write_flood_extent(
            dst_path=output_path,
            flooded=flooded,
            validity_mask=validity_mask,
            dem_metadata=dem_metadata,
            nodata=255,
        )

        assert output_path.exists()
        assert meta["crs"] == "EPSG:4326"
        assert meta["width"] == 100
        assert meta["height"] == 100
        assert meta["dtype"] == "uint8"
        assert meta["nodata"] == 255

        # Verify content by reopening
        with rasterio.open(output_path) as src:
            data = src.read(1)

            # Flooded valid cells = 1
            assert data[55, 55] == 1

            # Dry valid cells = 0
            assert data[55, 30] == 0

            # Invalid cells = 255 (NoData)
            assert data[5, 5] == 255

    def test_write_flood_extent_shape_mismatch_raises(self, tmp_path: Path):
        """Shape mismatch should raise ValueError."""
        flooded = np.zeros((50, 50), dtype=bool)
        validity_mask = np.ones((100, 100), dtype=bool)
        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(0, 0, 10, 10, 100, 100),
            "width": 100,
            "height": 100,
        }

        with pytest.raises(ValueError, match="shape.*does not match"):
            write_flood_extent(
                dst_path=tmp_path / "out.tif",
                flooded=flooded,
                validity_mask=validity_mask,
                dem_metadata=dem_metadata,
            )

    def test_write_flood_extent_all_flooded(self, tmp_path: Path):
        """Test when all valid cells are flooded."""
        flooded = np.ones((10, 10), dtype=bool)
        validity_mask = np.ones((10, 10), dtype=bool)
        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(0, 0, 1, 1, 10, 10),
            "width": 10,
            "height": 10,
        }

        output_path = tmp_path / "flood_all.tif"
        write_flood_extent(output_path, flooded, validity_mask, dem_metadata)

        with rasterio.open(output_path) as src:
            data = src.read(1)
            assert np.all(data[validity_mask] == 1)

    def test_write_flood_extent_none_flooded(self, tmp_path: Path):
        """Test when no cells are flooded."""
        flooded = np.zeros((10, 10), dtype=bool)
        validity_mask = np.ones((10, 10), dtype=bool)
        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(0, 0, 1, 1, 10, 10),
            "width": 10,
            "height": 10,
        }

        output_path = tmp_path / "flood_none.tif"
        write_flood_extent(output_path, flooded, validity_mask, dem_metadata)

        with rasterio.open(output_path) as src:
            data = src.read(1)
            assert np.all(data[validity_mask] == 0)


class TestPipelineIntegration:
    """Integration tests for the full pipeline (mocked external calls)."""

    def create_synthetic_river_geojson(self, tmp_path: Path) -> Path:
        """Create a synthetic river GeoJSON."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [79.5, 16.5],
                            [80.5, 16.5],
                            [81.5, 16.5],
                        ],
                    },
                    "properties": {"name": "Krishna River"},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)
        return geojson_path

    @patch("kshitij_model.pipeline.acquire_dem")
    @patch("kshitij_model.pipeline.mosaic_tiles")
    @patch("kshitij_model.pipeline.crop_raster")
    @patch("kshitij_model.pipeline.prepare_model_input")
    @patch("kshitij_model.pipeline.rasterize_river_mask")
    @patch("kshitij_model.pipeline.write_flood_extent")
    @patch("kshitij_model.pipeline.write_river_mask_geotiff")
    def test_pipeline_orchestration(
        self,
        mock_write_river_mask,
        mock_write_flood_extent,
        mock_rasterize_river,
        mock_prepare_input,
        mock_crop,
        mock_mosaic,
        mock_acquire,
        tmp_path: Path,
    ):
        """Test pipeline orchestration with mocked external functions."""
        # Setup mocks
        mock_acquire.return_value = MagicMock(
            tiles=[
                MagicMock(local_path=str(tmp_path / "N16E079.tif")),
                MagicMock(local_path=str(tmp_path / "N16E080.tif")),
                MagicMock(local_path=str(tmp_path / "N16E081.tif")),
            ]
        )
        mock_mosaic.return_value = {
            "crs": "EPSG:4326",
            "width": 300,
            "height": 100,
            "transform": list(from_bounds(79, 16, 82, 17, 300, 100)),
            "bounds": [79, 16, 82, 17],
            "dtype": "float32",
            "nodata": -32767,
        }

        # Mock crop_raster to create actual file
        def mock_crop_func(
            src_path,
            dst_path,
            bounds,
            nodata=None,
            dst_crs=None,
            dst_nodata=None,
            compression="lzw",
        ):
            transform = from_bounds(80, 16, 82, 17, 200, 100)
            _create_dummy_dem(Path(dst_path), 200, 100, transform)
            return {
                "crs": "EPSG:4326",
                "width": 200,
                "height": 100,
                "transform": list(transform),
                "bounds": [80, 16, 82, 17],
                "dtype": "float32",
                "nodata": -32767,
            }

        mock_crop.side_effect = mock_crop_func

        # Mock prepare_model_input
        elevation = np.full((100, 200), 10.0, dtype=np.float32)
        validity_mask = np.ones((100, 200), dtype=bool)
        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(80, 16, 82, 17, 200, 100),
            "width": 200,
            "height": 100,
            "bounds": (80, 16, 82, 17),
            "dtype": "float32",
            "nodata": -32767,
        }
        mock_prepare_input.return_value = (elevation, validity_mask, dem_metadata)

        # Mock river mask
        river_mask = np.zeros((100, 200), dtype=bool)
        river_mask[50, 50:150] = True  # River across middle
        mock_rasterize_river.return_value = river_mask

        # Mock write_flood_extent
        flooded = np.zeros((100, 200), dtype=bool)
        flooded[50, 50:150] = True  # Flooded along river
        mock_write_flood_extent.return_value = {
            "crs": "EPSG:4326",
            "width": 200,
            "height": 100,
            "transform": list(from_bounds(80, 16, 82, 17, 200, 100)),
            "bounds": [80, 16, 82, 17],
            "dtype": "uint8",
            "nodata": 255,
        }
        mock_write_river_mask.return_value = {}

        # Create river vector file
        river_path = self.create_synthetic_river_geojson(tmp_path)

        # Run pipeline
        config = PipelineConfig(
            dem_tiles=[(16, 79), (16, 80), (16, 81)],
            cache_dir=tmp_path / "cache",
            raw_dir=tmp_path / "raw",
            processed_dir=tmp_path / "processed",
            aoi_bounds=(80.0, 16.0, 82.0, 17.0),
            river_vector_path=river_path,
            water_level=15.0,
            nodata_value=-32767.0,
            output_path=tmp_path / "flood_extent.tif",
            write_river_mask=True,
            river_mask_output_path=tmp_path / "river_mask.tif",
            use_cached_dem=False,
        )

        result = run_pipeline(config)

        # Verify result
        assert result.flood_extent_path == Path(config.output_path)
        # With all cells valid and elevation <= water_level, all valid cells flood
        assert result.flooded_cell_count == 20000
        assert result.valid_cell_count == 20000
        assert result.elevation_shape == (100, 200)

        # Verify mocks called
        mock_acquire.assert_called_once()
        mock_mosaic.assert_called_once()
        mock_crop.assert_called_once()
        mock_prepare_input.assert_called_once()
        mock_rasterize_river.assert_called_once()
        mock_write_flood_extent.assert_called_once()
        mock_write_river_mask.assert_called_once()

    @patch("kshitij_model.pipeline.prepare_model_input")
    @patch("kshitij_model.pipeline.rasterize_river_mask")
    def test_pipeline_river_mask_empty_raises(
        self,
        mock_rasterize_river,
        mock_prepare_input,
        tmp_path: Path,
    ):
        """Test pipeline raises when river mask is empty."""
        # Create dummy DEM tiles in the temp directory (simulating cached tiles)
        tile_dir = tmp_path / "raw"
        tile_dir.mkdir(parents=True, exist_ok=True)
        for lat, lon in [(16, 79)]:
            tile_id = f"N{lat:02d}E{lon:03d}"
            _create_dummy_dem(
                tile_dir / f"{tile_id}.tif",
                100,
                100,
                from_bounds(lon, lat, lon + 1, lat + 1, 100, 100),
            )

        # Use real mosaic_tiles and crop_raster with the dummy tiles
        elevation = np.full((100, 100), 10.0, dtype=np.float32)
        validity_mask = np.ones((100, 100), dtype=bool)
        dem_metadata = {
            "crs": "EPSG:4326",
            "transform": from_bounds(79, 16, 80, 17, 100, 100),
            "width": 100,
            "height": 100,
        }
        mock_prepare_input.return_value = (elevation, validity_mask, dem_metadata)

        # River mask empty
        mock_rasterize_river.side_effect = RiverMaskEmptyError("No river cells")

        river_path = self.create_synthetic_river_geojson(tmp_path)

        config = PipelineConfig(
            dem_tiles=[(16, 79)],
            cache_dir=tmp_path / "cache",
            raw_dir=tile_dir,
            processed_dir=tmp_path / "processed",
            river_vector_path=river_path,
            water_level=15.0,
            output_path=tmp_path / "flood_extent.tif",
            use_cached_dem=True,
        )

        with pytest.raises(PipelineError, match="River mask generation failed"):
            run_pipeline(config)


class TestPipelineWithRealDEM:
    """Integration test using real cached DEM data (if available)."""

    @pytest.mark.integration
    def test_pipeline_with_cached_dem(self, tmp_path: Path):
        """Test pipeline with actual cached DEM tiles.
        This test is skipped if DEM data is not available.
        """
        raw_dir = Path("data/raw/dem")
        required_tiles = ["N16E079.tif", "N16E080.tif", "N16E081.tif"]

        if not all((raw_dir / t).exists() for t in required_tiles):
            pytest.skip("Cached DEM tiles not available")

        # Create a simple river GeoJSON for the Vijayawada area
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [80.5, 16.5],
                            [80.6, 16.5],
                            [80.7, 16.5],
                            [80.8, 16.5],
                            [80.9, 16.5],
                            [81.0, 16.5],
                            [81.1, 16.5],
                        ],
                    },
                    "properties": {"name": "Krishna River"},
                }
            ],
        }
        river_path = tmp_path / "river.geojson"
        with river_path.open("w") as f:
            json.dump(geojson, f)

        config = PipelineConfig(
            dem_tiles=[(16, 79), (16, 80), (16, 81)],
            cache_dir="data/cache",
            raw_dir="data/raw/dem",
            processed_dir=tmp_path / "processed",
            aoi_bounds=(80.5, 16.3, 81.2, 16.7),
            river_vector_path=river_path,
            water_level=25.0,
            nodata_value=-32767.0,
            output_path=tmp_path / "flood_extent.tif",
            use_cached_dem=True,
        )

        result = run_pipeline(config)

        assert result.flood_extent_path.exists()
        assert result.flooded_cell_count >= 0
        assert result.valid_cell_count > 0
        assert result.elevation_shape is not None


class TestDEMCacheHandling:
    """Tests for DEM cache handling in the pipeline."""

    @patch("kshitij_model.pipeline.acquire_dem")
    def test_dem_cache_handling_mixed_cached_and_missing(self, mock_acquire_dem, tmp_path: Path):
        """Test that DEM cache handling works correctly with a mix of cached and missing tiles.
        This test verifies that only missing tiles are downloaded, not all tiles.
        """
        # Create a dummy DEM tile for the first tile (simulating cached)
        tile_dir = tmp_path / "raw"
        tile_dir.mkdir(parents=True, exist_ok=True)
        for lat, lon in [(16, 79)]:
            tile_id = f"N{lat:02d}E{lon:03d}"
            _create_dummy_dem(
                tile_dir / f"{tile_id}.tif",
                100, 100,
                from_bounds(lon, lat, lon + 1, lat + 1, 100, 100)
            )

        # Create river vector
        river_path = tmp_path / "river.geojson"
        with river_path.open("w") as f:
            json.dump({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[79.5, 16.5], [80.5, 16.5]]},
                    "properties": {"name": "Test River"}
                }]
            }, f)

        # Mock acquire_dem to verify it's only called for missing tiles
        mock_manifest = MagicMock()
        mock_manifest.tiles = [
            MagicMock(local_path=str(tile_dir / "N16E080.tif")),
            MagicMock(local_path=str(tile_dir / "N16E081.tif")),
        ]
        mock_acquire_dem.return_value = mock_manifest

        config = PipelineConfig(
            dem_tiles=[(16, 79), (16, 80), (16, 81)],
            cache_dir=tmp_path / "cache",
            raw_dir=str(tile_dir),
            processed_dir=tmp_path / "processed",
            river_vector_path=tmp_path / "river.geojson",
            water_level=15.0,
            output_path=tmp_path / "flood_extent.tif",
            use_cached_dem=True,
        )

        # We don't run the full pipeline since we're mocking acquire_dem
        # Just test the _ensure_dem_tiles function
        from kshitij_model.pipeline import _ensure_dem_tiles, get_config
        dem_config = get_config()
        dem_config.study_tiles = [(16, 79), (16, 80), (16, 81)]

        tile_paths = _ensure_dem_tiles(config, dem_config)

        # Verify all three tiles are present
        assert len(tile_paths) == 3
        # Verify the order matches the requested tiles
        for i, (lat, lon) in enumerate([(16, 79), (16, 80), (16, 81)]):
            tile_id = f"N{lat:02d}E{lon:03d}"
            assert tile_id in str(tile_paths[i])

        # Verify acquire_dem was called only for missing tiles (2 tiles: 16,80 and 16,81)
        mock_acquire_dem.assert_called_once()
        call_args = mock_acquire_dem.call_args[1]['tiles']
        assert len(call_args) == 2
        assert (16, 80) in call_args
        assert (16, 81) in call_args
        assert (16, 79) not in call_args  # This one was cached

    @patch("kshitij_model.pipeline.acquire_dem")
    def test_dem_cache_disabled_acquires_all_tiles(self, mock_acquire_dem, tmp_path: Path):
        """Test that use_cached_dem=False acquires all requested tiles even if they exist.
        This test verifies that when use_cached_dem=False, all requested tiles are acquired.
        """
        # Create dummy DEM tiles for all tiles (simulating cached)
        tile_dir = tmp_path / "raw"
        tile_dir.mkdir(parents=True, exist_ok=True)
        for lat, lon in [(16, 79), (16, 80), (16, 81)]:
            tile_id = f"N{lat:02d}E{lon:03d}"
            _create_dummy_dem(
                tile_dir / f"{tile_id}.tif",
                100, 100,
                from_bounds(lon, lat, lon + 1, lat + 1, 100, 100)
            )

        # Create river vector
        river_path = tmp_path / "river.geojson"
        with river_path.open("w") as f:
            json.dump({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[79.5, 16.5], [80.5, 16.5]]},
                    "properties": {"name": "Test River"}
                }]
            }, f)

        # Mock acquire_dem to verify it's called with all tiles
        mock_manifest = MagicMock()
        mock_manifest.tiles = [
            MagicMock(local_path=str(tile_dir / "N16E079.tif")),
            MagicMock(local_path=str(tile_dir / "N16E080.tif")),
            MagicMock(local_path=str(tile_dir / "N16E081.tif")),
        ]
        mock_acquire_dem.return_value = mock_manifest

        config = PipelineConfig(
            dem_tiles=[(16, 79), (16, 80), (16, 81)],
            cache_dir=tmp_path / "cache",
            raw_dir=str(tile_dir),
            processed_dir=tmp_path / "processed",
            river_vector_path=tmp_path / "river.geojson",
            water_level=15.0,
            output_path=tmp_path / "flood_extent.tif",
            use_cached_dem=False,
        )

        from kshitij_model.pipeline import _ensure_dem_tiles, get_config
        dem_config = get_config()
        dem_config.study_tiles = [(16, 79), (16, 80), (16, 81)]

        tile_paths = _ensure_dem_tiles(config, dem_config)

        # Verify all three tiles are present
        assert len(tile_paths) == 3
        # Verify the order matches the requested tiles
        for i, (lat, lon) in enumerate([(16, 79), (16, 80), (16, 81)]):
            tile_id = f"N{lat:02d}E{lon:03d}"
            assert tile_id in str(tile_paths[i])

        # Verify acquire_dem was called for ALL tiles (not just missing ones)
        mock_acquire_dem.assert_called_once()
        call_args = mock_acquire_dem.call_args[1]['tiles']
        assert len(call_args) == 3
        assert (16, 79) in call_args
        assert (16, 80) in call_args
        assert (16, 81) in call_args
