"""Tests for DEM acquisition module."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kshitij_model.config import DEMConfig, get_config
from kshitij_model.dem_acquisition import (
    AcquisitionManifest,
    DEMAcquisition,
    DEMTileInfo,
    acquire_dem,
)


class TestDEMConfig:
    """Tests for DEMConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = get_config()
        assert list(config.study_tiles) == [(16, 79), (16, 80), (16, 81)]
        assert config.dem_bucket == "copernicus-dem-30m"
        assert config.dem_region == "us-east-1"
        assert config.vertical_datum == "EGM2008"
        assert config.nodata_value == -32768.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = DEMConfig(
            study_tiles=[(15, 80), (15, 81)],
            nodata_value=-9999.0,
        )
        assert config.study_tiles == [(15, 80), (15, 81)]
        assert config.nodata_value == -9999.0

    def test_empty_study_tiles_raises(self):
        """Empty study_tiles should raise ValueError."""
        with pytest.raises(ValueError, match="study_tiles cannot be empty"):
            DEMConfig(study_tiles=[])

    def test_get_config(self):
        """Test get_config function."""
        config = get_config()
        assert isinstance(config, DEMConfig)
        assert list(config.study_tiles) == [(16, 79), (16, 80), (16, 81)]

    def test_config_validation(self):
        """Test config validation."""
        with pytest.raises(ValueError, match="study_tiles cannot be empty"):
            DEMConfig(study_tiles=[])


class TestDEMTileInfo:
    """Tests for DEMTileInfo dataclass."""

    def test_tile_info_creation(self):
        """Test creating DEMTileInfo."""
        tile = DEMTileInfo(
            tile_id="N16E080",
            source_url="s3://copernicus-dem-30m/...",
            local_path="/path/to/N16E080.tif",
            file_size=47527962,
            sha256="abc123",
            retrieved_at="2024-01-01T00:00:00Z",
            tile_lat=16,
            tile_lon=80,
        )
        assert tile.tile_id == "N16E080"
        assert tile.tile_lat == 16
        assert tile.tile_lon == 80


class TestAcquisitionManifest:
    """Tests for AcquisitionManifest serialization."""

    def test_manifest_creation(self):
        """Test creating AcquisitionManifest."""
        tile = DEMTileInfo(
            tile_id="N16E080",
            source_url="s3://...",
            local_path="/path.tif",
            file_size=100,
            sha256="abc",
            retrieved_at="2024-01-01T00:00:00Z",
            tile_lat=16,
            tile_lon=80,
        )
        manifest = AcquisitionManifest(
            dataset="Test",
            version="1.0",
            retrieval_time="2024-01-01T00:00:00Z",
            tiles=[tile],
            total_size=100,
            licence="CC BY 4.0",
            source_catalog="s3://bucket",
        )
        assert manifest.total_size == 100
        assert len(manifest.tiles) == 1

    def test_manifest_to_dict(self):
        """Test manifest serialization."""
        tile = DEMTileInfo(
            tile_id="N16E080",
            source_url="s3://...",
            local_path="/path.tif",
            file_size=100,
            sha256="abc",
            retrieved_at="2024-01-01T00:00:00Z",
            tile_lat=16,
            tile_lon=80,
        )
        manifest = AcquisitionManifest(
            dataset="Test",
            version="1.0",
            retrieval_time="2024-01-01T00:00:00Z",
            tiles=[tile],
            total_size=100,
            licence="CC BY 4.0",
            source_catalog="s3://bucket",
        )
        d = manifest.to_dict()
        assert d["dataset"] == "Test"
        assert len(d["tiles"]) == 1
        assert d["tiles"][0]["tile_id"] == "N16E080"

    def test_manifest_serialization(self):
        """Test manifest round-trip."""
        tile = DEMTileInfo(
            tile_id="N16E080",
            source_url="s3://...",
            local_path="/path.tif",
            file_size=100,
            sha256="abc",
            retrieved_at="2024-01-01T00:00:00Z",
            tile_lat=16,
            tile_lon=80,
        )
        manifest = AcquisitionManifest(
            dataset="Test",
            version="1.0",
            retrieval_time="2024-01-01T00:00:00Z",
            tiles=[tile],
            total_size=100,
            licence="CC BY 4.0",
            source_catalog="s3://bucket",
        )

        # Test serialization
        d = manifest.to_dict()
        assert d["dataset"] == "Test"
        assert d["tiles"][0]["tile_id"] == "N16E080"

        # Test round-trip - need to reconstruct DEMTileInfo objects
        tiles = [DEMTileInfo(**t) for t in d["tiles"]]
        manifest2 = AcquisitionManifest(
            dataset=d["dataset"],
            version=d["version"],
            retrieval_time=d["retrieval_time"],
            tiles=tiles,
            total_size=d["total_size"],
            licence=d["licence"],
            source_catalog=d["source_catalog"],
        )
        assert manifest2.dataset == "Test"
        assert manifest2.tiles[0].tile_id == "N16E080"


class TestDEMAcquisition:
    """Tests for DEMAcquisition class."""

    def test_tile_id_generation(self):
        """Test tile ID generation."""
        acq = DEMAcquisition()
        assert acq._tile_id(16, 79) == "N16E079"
        assert acq._tile_id(16, 80) == "N16E080"
        assert acq._tile_id(15, 81) == "N15E081"

    def test_s3_key_generation(self):
        """Test S3 key generation."""
        acq = DEMAcquisition()
        key = acq._s3_key(16, 80)
        # Key format: Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif
        assert "Copernicus_DSM_COG_10_N16_00_E080_00_DEM" in key
        assert "DEM.tif" in key

    def test_dem_path(self):
        """Test DEM path generation."""
        acq = DEMAcquisition(raw_dir="data/raw/dem")
        path = acq._dem_path(16, 80)
        assert path.name == "N16E080.tif"

    def test_cache_path(self):
        """Test cache path generation."""
        acq = DEMAcquisition(cache_dir="data/cache")
        path = acq._cache_path(16, 80)
        assert path.name == "N16E080.json"

    def test_manifest_path(self):
        """Test manifest path."""
        acq = DEMAcquisition(cache_dir="data/cache")
        path = acq._manifest_path()
        assert path.name == "manifest.json"

    def test_study_area_bounds(self):
        """Test study area bounds."""
        acq = DEMAcquisition()
        bounds = acq.get_study_area_bounds()
        assert bounds == (79.0, 16.0, 82.0, 17.0)

    def test_compute_sha256(self):
        """Test SHA-256 computation."""
        acq = DEMAcquisition()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            sha256 = acq._compute_sha256(temp_path)
            expected = hashlib.sha256(b"test content").hexdigest()
            assert sha256 == expected
        finally:
            temp_path.unlink()

    def test_compute_sha256_large_file(self):
        """Test SHA-256 on larger file (streaming)."""
        acq = DEMAcquisition()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100000)
            temp_path = Path(f.name)

        try:
            sha256 = acq._compute_sha256(temp_path)
            # Just verify it returns a valid hex string
            assert len(sha256) == 64
            int(sha256, 16)  # Should not raise
        finally:
            temp_path.unlink()

    @patch("kshitij_model.dem_acquisition.boto3.client")
    def test_verify_tile_exists(self, mock_boto):
        """Test tile existence check."""
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        acq = DEMAcquisition()

        # Tile exists
        mock_s3.head_object.return_value = {}
        assert acq._verify_tile_exists(16, 80) is True
        mock_s3.head_object.assert_called_once()

        # Tile not found (404)
        from botocore.exceptions import ClientError

        error = {"Error": {"Code": "404"}}
        mock_s3.head_object.side_effect = ClientError(error, "HeadObject")
        assert acq._verify_tile_exists(16, 80) is False

    @patch("kshitij_model.dem_acquisition.boto3.client")
    def test_verify_tile_exists_other_error(self, mock_boto):
        """Test other errors are raised."""
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        acq = DEMAcquisition()
        from botocore.exceptions import ClientError

        error = {"Error": {"Code": "500"}}
        mock_s3.head_object.side_effect = ClientError(error, "HeadObject")

        with pytest.raises(ClientError):
            acq._verify_tile_exists(16, 80)


class TestDEMAcquisitionIntegration:
    """Integration tests with mocked S3."""

    def test_acquire_study_area_cached(self, tmp_path):
        """Test acquiring with cached tiles."""
        with patch("kshitij_model.dem_acquisition.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3

            # Mock head_object for tile existence
            mock_s3.head_object.return_value = {"ContentLength": 100}

            # Mock download_file
            def mock_download(Bucket, Key, Filename, Config=None):
                Path(Filename).write_bytes(b"x" * 100)

            mock_s3.download_file.side_effect = mock_download

            cache_dir = tmp_path / "cache"
            raw_dir = tmp_path / "raw" / "dem"
            cache_dir.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)

            # Pre-create cached files
            tile_id = "N16E080"
            dest = raw_dir / f"{tile_id}.tif"
            dest.write_bytes(b"x" * 100)

            cache_meta = cache_dir / "N16E080.json"
            cache_meta.parent.mkdir(parents=True, exist_ok=True)
            cache_meta.write_text(
                json.dumps(
                    {
                        "tile_id": tile_id,
                        "source_url": "s3://...",
                        "local_path": str(dest),
                        "file_size": 100,
                        "sha256": hashlib.sha256(b"x" * 100).hexdigest(),
                        "retrieved_at": "2024-01-01T00:00:00Z",
                        "tile_lat": 16,
                        "tile_lon": 80,
                    }
                )
            )

            acq = DEMAcquisition(cache_dir=cache_dir, raw_dir=raw_dir)
            acq.s3 = mock_s3

            manifest = acq.acquire_study_area([(16, 80)])

            assert len(manifest.tiles) == 1
            assert manifest.tiles[0].tile_id == "N16E080"
            assert manifest.total_size == 100

    @patch("kshitij_model.dem_acquisition.boto3.client")
    def test_acquire_study_area_download(self, mock_boto, tmp_path):
        """Test downloading new tiles."""
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        # Mock head_object for existence and size
        mock_s3.head_object.return_value = {"ContentLength": 100}

        # Mock download_file
        def mock_download(Bucket, Key, Filename, Config=None):
            Path(Filename).write_bytes(b"x" * 100)

        mock_s3.download_file.side_effect = mock_download

        acq = DEMAcquisition(
            cache_dir=tmp_path / "cache", raw_dir=tmp_path / "raw" / "dem"
        )
        acq.s3 = mock_s3

        manifest = acq.acquire_study_area([(16, 80)])

        assert len(manifest.tiles) == 1
        assert manifest.tiles[0].tile_id == "N16E080"
        assert manifest.total_size == 100
        assert manifest.tiles[0].sha256 == hashlib.sha256(b"x" * 100).hexdigest()


class TestAcquireDemFunction:
    """Tests for acquire_dem convenience function."""

    @patch("kshitij_model.dem_acquisition.DEMAcquisition")
    def test_acquire_dem_function(self, mock_acq_class):
        """Test acquire_dem convenience function."""
        mock_acq = MagicMock()
        mock_acq_class.return_value = mock_acq
        mock_manifest = MagicMock()
        mock_acq.acquire_study_area.return_value = mock_manifest

        result = acquire_dem(tiles=[(16, 80)])

        mock_acq_class.assert_called_once()
        mock_acq.acquire_study_area.assert_called_once_with([(16, 80)])
        assert result == mock_manifest


class TestAcquireDemIntegration:
    """Integration tests (require network)."""

    @pytest.mark.integration
    def test_real_tile_download(self):
        """Test downloading a real tile (requires network)."""
        pytest.skip("Requires network access")

    @pytest.mark.integration
    def test_manifest_verification(self):
        """Test manifest verification with real data."""
        pytest.skip("Requires downloaded data")


# Register pytest marks
pytestmark = pytest.mark.integration
