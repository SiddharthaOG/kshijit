"""Tests for river mask generation module."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_bounds

from kshitij_model.river_mask import (
    MissingDependencyError,
    RiverGeometryError,
    RiverMaskEmptyError,
    RiverMaskError,
    RiverVectorError,
    create_river_mask_from_geojson_dict,
    rasterize_river_mask,
    write_river_mask_geotiff,
)


class TestCreateRiverMaskFromGeoJSONDict:
    """Tests for create_river_mask_from_geojson_dict using synthetic fixtures."""

    def test_line_string_river(self):
        """Test rasterizing a simple LineString river."""
        # Reference grid: 100x100, bounds (0,0) to (10,10), 0.1 deg resolution
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        width = 100
        height = 100

        # River runs horizontally through middle (y=5, i.e., row 50)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [1.0, 5.0],
                            [9.0, 5.0],
                        ],
                    },
                    "properties": {"name": "test_river"},
                }
            ],
        }

        mask = create_river_mask_from_geojson_dict(
            geojson, transform, width, height, "EPSG:4326", all_touched=True
        )

        assert mask.shape == (height, width)
        assert mask.dtype == bool
        # River at y=5 should be around row 50 (10.0 - 5.0 = 5.0, 5.0/0.1 = 50)
        assert mask[50, 10:90].any()  # Some cells in the middle should be True
        assert mask.sum() > 0

    def test_multi_line_string_river(self):
        """Test rasterizing a MultiLineString river."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        width = 100
        height = 100

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [
                            [[1.0, 5.0], [5.0, 5.0]],
                            [[5.0, 5.0], [9.0, 7.0]],
                        ],
                    },
                    "properties": {},
                }
            ],
        }

        mask = create_river_mask_from_geojson_dict(
            geojson, transform, width, height, "EPSG:4326", all_touched=True
        )

        assert mask.shape == (height, width)
        assert mask.sum() > 0

    def test_polygon_river(self):
        """Test rasterizing a Polygon river (wide river representation)."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        width = 100
        height = 100

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [4.0, 4.5],
                                [6.0, 4.5],
                                [6.0, 5.5],
                                [4.0, 5.5],
                                [4.0, 4.5],
                            ]
                        ],
                    },
                    "properties": {},
                }
            ],
        }

        mask = create_river_mask_from_geojson_dict(
            geojson, transform, width, height, "EPSG:4326", all_touched=True
        )

        assert mask.shape == (height, width)
        # Polygon covers rows ~45-55, cols ~40-60
        assert mask[45:55, 40:60].sum() > 0

    def test_all_touched_false(self):
        """Test all_touched=False only burns pixels with center in geometry."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        width = 100
        height = 100

        # Use a polygon that clearly demonstrates the difference
        # A thin diagonal line where all_touched=True covers more pixels
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 1.0], [9.0, 9.0]],
                    },
                    "properties": {},
                }
            ],
        }

        mask_all = create_river_mask_from_geojson_dict(
            geojson, transform, width, height, "EPSG:4326", all_touched=True
        )
        mask_center = create_river_mask_from_geojson_dict(
            geojson, transform, width, height, "EPSG:4326", all_touched=False
        )

        # all_touched=True should have more or equal pixels
        assert mask_all.sum() >= mask_center.sum()
        # Both should have some pixels
        assert mask_all.sum() > 0
        assert mask_center.sum() > 0

    def test_empty_feature_collection_raises(self):
        """Empty FeatureCollection should raise RiverGeometryError."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        geojson = {"type": "FeatureCollection", "features": []}

        with pytest.raises(RiverGeometryError, match="No river-like geometries"):
            create_river_mask_from_geojson_dict(geojson, transform, 100, 100)

    def test_non_river_geometry_raises(self):
        """Point geometry should be filtered out and raise."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [5.0, 5.0]},
                    "properties": {},
                }
            ],
        }

        with pytest.raises(RiverGeometryError, match="No river-like geometries"):
            create_river_mask_from_geojson_dict(geojson, transform, 100, 100)

    def test_river_outside_bounds_raises_empty(self):
        """River completely outside DEM bounds should raise RiverMaskEmptyError."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[20.0, 20.0], [30.0, 30.0]],
                    },
                    "properties": {},
                }
            ],
        }

        with pytest.raises(RiverMaskEmptyError, match="no True cells"):
            create_river_mask_from_geojson_dict(geojson, transform, 100, 100)

    def test_geometry_collection_extracts_valid(self):
        """GeometryCollection should extract valid sub-geometries."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [1.0, 1.0]},
                            {
                                "type": "LineString",
                                "coordinates": [[2.0, 5.0], [8.0, 5.0]],
                            },
                        ],
                    },
                    "properties": {},
                }
            ],
        }

        mask = create_river_mask_from_geojson_dict(
            geojson, transform, 100, 100, "EPSG:4326", all_touched=True
        )

        assert mask.sum() > 0


class TestWriteRiverMaskGeoTIFF:
    """Tests for write_river_mask_geotiff."""

    def test_write_river_mask(self, tmp_path: Path):
        """Test writing river mask as GeoTIFF."""
        mask = np.zeros((100, 100), dtype=bool)
        mask[50, 40:60] = True  # Horizontal line
        # Set some invalid areas (e.g., border) - these will be NoData
        # Note: write_river_mask_geotiff writes 1=river, 0=non-river, 255=NoData
        # We can't easily test NoData without a validity mask, so test the basic write

        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        output_path = tmp_path / "river_mask.tif"

        meta = write_river_mask_geotiff(
            mask=mask,
            dst_path=output_path,
            reference_transform=transform,
            reference_crs="EPSG:4326",
        )

        assert output_path.exists()
        assert meta["crs"] == "EPSG:4326"
        assert meta["width"] == 100
        assert meta["height"] == 100
        assert meta["nodata"] == 255
        assert meta["dtype"] == "uint8"

        # Verify content
        import rasterio

        with rasterio.open(output_path) as src:
            data = src.read(1)
            # River pixels should be 1
            assert data[50, 50] == 1
            # Non-river valid pixels should be 0
            assert data[50, 30] == 0
            # Non-river pixels elsewhere should be 0
            assert data[0, 0] == 0


class TestRasterizeRiverMaskFile:
    """Tests for rasterize_river_mask with actual vector files."""

    def test_geojson_file(self, tmp_path: Path):
        """Test reading river from GeoJSON file."""
        # Create a GeoJSON file
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {"name": "Test River"},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        mask = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=100,
            reference_height=100,
            reference_crs="EPSG:4326",
        )

        assert mask.shape == (100, 100)
        assert mask.dtype == bool
        assert mask.sum() > 0

    def test_nonexistent_file_raises(self):
        """Non-existent file should raise RiverVectorError."""
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        with pytest.raises(RiverVectorError, match="not found"):
            rasterize_river_mask(
                vector_path="nonexistent.geojson",
                reference_transform=transform,
                reference_width=100,
                reference_height=100,
            )

    def test_invalid_crs_transform(self, tmp_path: Path):
        """Test CRS transformation from different CRS."""
        # Create GeoJSON with a different CRS (we'll simulate by not specifying CRS)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        # This should work - fiona reads GeoJSON as EPSG:4326 by default
        transform = (0.1, 0.0, 0.0, 0.0, -0.1, 10.0)
        mask = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=100,
            reference_height=100,
            reference_crs="EPSG:4326",
        )

        assert mask.sum() > 0


class TestRiverMaskErrors:
    """Tests for river mask error types."""

    def test_missing_dependency_error(self):
        """Test MissingDependencyError inherits from RiverMaskError."""
        assert issubclass(MissingDependencyError, RiverMaskError)

    def test_error_hierarchy(self):
        """Test all error classes inherit from RiverMaskError."""
        assert issubclass(RiverVectorError, RiverMaskError)
        assert issubclass(RiverGeometryError, RiverMaskError)
        assert issubclass(RiverMaskEmptyError, RiverMaskError)
        assert issubclass(MissingDependencyError, RiverMaskError)


class TestRiverBuffering:
    """Tests for river buffering functionality."""

    def test_buffering_increases_rasterized_extent(self, tmp_path: Path):
        """Test that buffering increases the rasterized river extent.

        This test verifies that buffering expands the river mask spatially.
        We do not claim meter-level accuracy based on pixel counts alone,
        but we verify the directional effect (buffering expands extent).
        """
        # Create a test GeoJSON file with a simple river
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        transform = from_bounds(0, 0, 10, 10, 100, 100)
        width = 100
        height = 100

        # Test without buffer
        mask_no_buffer = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:4326",
            buffer_meters=0.0,
        )

        # Test with 100m buffer
        mask_with_buffer = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:4326",
            buffer_meters=100.0,
        )

        # Buffering should strictly increase the rasterized extent (not just >=)
        assert mask_with_buffer.sum() > mask_no_buffer.sum()
        # Both should have some pixels
        assert mask_no_buffer.sum() > 0
        assert mask_with_buffer.sum() > 0

    def test_buffering_requires_dependencies(self, tmp_path: Path):
        """Test that buffering raises MissingDependencyError when dependencies unavailable."""
        # This test is a placeholder - in the actual environment, dependencies are available
        # The actual error is raised when BUFFERING_AVAILABLE is False
        pass

    def test_negative_buffer_raises(self, tmp_path: Path):
        """Test that negative buffer distance raises RiverGeometryError."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        transform = from_bounds(0, 0, 10, 10, 100, 100)

        with pytest.raises(RiverGeometryError, match="buffer_meters must be non-negative"):
            rasterize_river_mask(
                vector_path=tmp_path / "river.geojson",
                reference_transform=(0.1, 0.0, 0.0, 0.0, -0.1, 10.0),
                reference_width=100,
                reference_height=100,
                reference_crs="EPSG:4326",
                buffer_meters=-10.0,
            )

    def test_nan_buffer_raises(self, tmp_path: Path):
        """Test that NaN buffer distance raises RiverGeometryError."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        transform = from_bounds(0, 0, 10, 10, 100, 100)

        with pytest.raises(RiverGeometryError, match="buffer_meters must be finite"):
            rasterize_river_mask(
                vector_path=tmp_path / "river.geojson",
                reference_transform=(0.1, 0.0, 0.0, 0.0, -0.1, 10.0),
                reference_width=100,
                reference_height=100,
                reference_crs="EPSG:4326",
                buffer_meters=float("nan"),
            )

    def test_inf_buffer_raises(self, tmp_path: Path):
        """Test that infinite buffer distance raises RiverGeometryError."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        with pytest.raises(RiverGeometryError, match="buffer_meters must be finite"):
            rasterize_river_mask(
                vector_path=tmp_path / "river.geojson",
                reference_transform=(0.1, 0.0, 0.0, 0.0, -0.1, 10.0),
                reference_width=100,
                reference_height=100,
                reference_crs="EPSG:4326",
                buffer_meters=float("inf"),
            )

    def test_buffering_expands_mask_spatially(self, tmp_path: Path):
        """Test that buffered mask includes cells outside the original unbuffered mask.

        This is a stronger test than just checking the pixel count. It verifies
        that the buffered mask actually expands spatially by checking that
        there are True cells in the buffered mask that were False in the
        unbuffered mask.
        """
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[1.0, 5.0], [9.0, 5.0]],
                    },
                    "properties": {},
                }
            ],
        }
        geojson_path = tmp_path / "river.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        transform = from_bounds(0, 0, 10, 10, 100, 100)
        width = 100
        height = 100

        mask_no_buffer = rasterize_river_mask(
            vector_path=tmp_path / "river.geojson",
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:4326",
            buffer_meters=0.0,
        )

        mask_with_buffer = rasterize_river_mask(
            vector_path=tmp_path / "river.geojson",
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:4326",
            buffer_meters=100.0,
        )

        # The buffered mask should have strictly more True cells
        assert mask_with_buffer.sum() > mask_no_buffer.sum()

        # AND there should be cells that are True in buffered but False in unbuffered
        # (i.e., the buffered mask strictly includes the original)
        expanded = mask_with_buffer & ~mask_no_buffer
        assert expanded.any(), "Buffered mask should include cells outside the original mask"

        # AND the original mask should be a subset of the buffered mask
        assert (mask_no_buffer & ~mask_with_buffer).sum() == 0, "Buffered mask should include all original river cells"

    def test_buffering_in_projected_crs(self, tmp_path: Path):
        """Test that buffering works correctly in a projected CRS (UTM).

        In a projected CRS, the buffer distance should be in the CRS's linear units
        (typically meters for UTM). This test verifies that buffering works correctly
        in a projected CRS and that the buffer distance is interpreted correctly.
        """
        import pyproj
        from pyproj import CRS

        # Create a UTM zone 44N CRS (EPSG:32644) - meters
        utm_crs = CRS.from_epsg(32644)
        
        # Create a simple river in UTM coordinates (already in projected CRS)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[500000.0, 0.0], [500010.0, 0.0]],
                    },
                    "properties": {},
                }
            ],
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:EPSG::32644"
                }
            }
        }
        geojson_path = tmp_path / "river_utm.geojson"
        with geojson_path.open("w") as f:
            json.dump(geojson, f)

        # Create a transform for a 10km x 10km area at 100m resolution (100x100 pixels)
        # This covers roughly 500km to 510km in x, 0km to 10km in y in UTM
        from rasterio.transform import Affine
        transform = Affine(100.0, 0.0, 500000.0, 0.0, -100.0, 10000.0)
        width = 100
        height = 100

        # Test without buffer
        mask_no_buffer = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:32644",
            buffer_meters=0.0,
        )

        # Test with 500m buffer (should be 5 pixels at 100m resolution)
        mask_with_buffer = rasterize_river_mask(
            vector_path=geojson_path,
            reference_transform=transform,
            reference_width=width,
            reference_height=height,
            reference_crs="EPSG:32644",
            buffer_meters=500.0,
        )

        # Buffering should increase the rasterized extent
        assert mask_with_buffer.sum() > mask_no_buffer.sum()

        # The buffer should expand by roughly 5 pixels on each side
        # (500m / 100m per pixel = 5 pixels)
        # We don't assert exact pixel count since rasterization is approximate,
        # but it should be significantly larger
        assert mask_with_buffer.sum() > mask_no_buffer.sum() * 2, "Buffer should significantly increase extent"

        # Verify the CRS is correctly handled (UTM uses meters)
        from pyproj import CRS
        utm_crs = CRS.from_epsg(32644)
        assert utm_crs.axis_info[0].unit_name == "metre"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
