"""Copernicus DEM GLO-30 acquisition module.

Provides functionality to discover, download, verify, and cache
Copernicus DEM GLO-30 tiles from the AWS Open Data Registry.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import DEMConfig


@dataclass
class DEMTileInfo:
    """Metadata for a single DEM tile."""

    tile_id: str
    source_url: str
    local_path: str
    file_size: int
    sha256: str
    retrieved_at: str
    tile_lat: int
    tile_lon: int


@dataclass
class AcquisitionManifest:
    """Manifest recording all acquisition metadata."""

    dataset: str
    version: str
    retrieval_time: str
    tiles: list[DEMTileInfo]
    total_size: int
    licence: str
    source_catalog: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "dataset": self.dataset,
            "version": self.version,
            "retrieval_time": self.retrieval_time,
            "tiles": [asdict(t) for t in self.tiles],
            "total_size": self.total_size,
            "licence": self.licence,
            "source_catalog": self.source_catalog,
        }


class DEMAcquisitionError(Exception):
    """Raised when DEM acquisition fails."""

    @classmethod
    def size_mismatch(
        cls, tile_id: str, expected_size: int, actual_size: int
    ) -> DEMAcquisitionError:
        return cls(
            f"Size mismatch for {tile_id}: expected {expected_size}, got {actual_size}"
        )

    @classmethod
    def tile_not_found(cls, tile_id: str) -> DEMAcquisitionError:
        return cls(f"Tile not found: {tile_id}")

    @classmethod
    def download_failed(
        cls, tile_id: str, max_retries: int, err: Exception
    ) -> DEMAcquisitionError:
        exc = cls(f"Failed to download {tile_id} after {max_retries} attempts: {err}")
        exc.__cause__ = err
        return exc

    @classmethod
    def exhausted_retries(cls, tile_id: str) -> DEMAcquisitionError:
        return cls(f"Exhausted retries for {tile_id}")

    @classmethod
    def tile_not_available(cls, tile_id: str) -> DEMAcquisitionError:
        return cls(f"Tile not available: {tile_id}")


class DEMAcquisition:
    """Handles discovery, download, and verification of Copernicus DEM GLO-30 tiles."""

    # Copernicus DEM GLO-30 Public on AWS
    BUCKET = "copernicus-dem-30m"
    REGION = "us-east-1"
    TILE_PREFIX = "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
    DEM_FILENAME = "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif"

    # Study area: core tiles for Vijayawada (Krishna River corridor)
    STUDY_TILES: ClassVar[list[tuple[int, int]]] = [
        (16, 79),  # N16E079
        (16, 80),  # N16E080
        (16, 81),  # N16E081
    ]

    def __init__(
        self,
        cache_dir: str | Path = "data/cache",
        raw_dir: str | Path = "data/raw/dem",
        config: DEMConfig | None = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.raw_dir = Path(raw_dir)
        self.config = config or DEMConfig()

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # S3 client with anonymous access
        self.s3 = boto3.client(
            "s3",
            config=Config(signature_version=UNSIGNED),
            region_name=self.REGION,
        )

    def _tile_id(self, lat: int, lon: int) -> str:
        """Generate tile ID from coordinates."""
        return f"N{lat:02d}E{lon:03d}"

    def _dem_path(self, lat: int, lon: int) -> Path:
        """Get local path for a DEM tile."""
        tile_id = self._tile_id(lat, lon)
        return self.raw_dir / f"{tile_id}.tif"

    def _cache_path(self, lat: int, lon: int) -> Path:
        """Get cache path for a tile."""
        tile_id = self._tile_id(lat, lon)
        return self.cache_dir / f"{tile_id}.json"

    def _manifest_path(self) -> Path:
        """Get manifest file path."""
        return self.cache_dir / "manifest.json"

    def _s3_key(self, lat: int, lon: int) -> str:
        """Generate S3 key for the DEM file."""
        prefix = self.TILE_PREFIX.format(lat=lat, lon=lon)
        filename = self.DEM_FILENAME.format(lat=lat, lon=lon)
        return prefix + filename

    def _verify_tile_exists(self, lat: int, lon: int) -> bool:
        """Check if tile exists in S3 without downloading."""
        key = self._s3_key(lat, lon)
        try:
            self.s3.head_object(Bucket=self.BUCKET, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
        else:
            return True

    def _compute_sha256(self, filepath: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _download_with_retries(self, lat: int, lon: int, dest: Path) -> dict:
        """Download a tile with retries and timeout."""
        key = self._s3_key(lat, lon)
        tile_id = self._tile_id(lat, lon)

        for attempt in range(1, self.config.max_retries + 1):
            try:
                # Get object size first
                head = self.s3.head_object(Bucket=self.BUCKET, Key=key)
                expected_size = head["ContentLength"]

                # Download with progress tracking
                self.s3.download_file(
                    Bucket=self.BUCKET,
                    Key=key,
                    Filename=str(dest),
                    Config=boto3.s3.transfer.TransferConfig(
                        max_concurrency=4,
                        multipart_chunksize=8 * 1024 * 1024,
                    ),
                )

                # Verify file size
                actual_size = dest.stat().st_size
                if actual_size != expected_size:
                    raise DEMAcquisitionError.size_mismatch(
                        tile_id, expected_size, actual_size
                    )

                # Compute checksum
                sha256 = self._compute_sha256(dest)

                return {
                    "tile_id": tile_id,
                    "source_url": f"s3://{self.BUCKET}/{key}",
                    "local_path": str(dest),
                    "file_size": actual_size,
                    "sha256": sha256,
                    "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "tile_lat": lat,
                    "tile_lon": lon,
                }

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "404":
                    raise DEMAcquisitionError.tile_not_found(tile_id) from e
                if attempt == self.config.max_retries:
                    raise DEMAcquisitionError.download_failed(
                        tile_id, self.config.max_retries, e
                    ) from e
                time.sleep(self.config.retry_delay * attempt)
            except OSError as e:
                if attempt == self.config.max_retries:
                    raise DEMAcquisitionError.download_failed(
                        tile_id, self.config.max_retries, e
                    ) from e
                time.sleep(self.config.retry_delay * attempt)

        raise DEMAcquisitionError.exhausted_retries(tile_id)

    def acquire_study_area(
        self, tiles: list[tuple[int, int]] | None = None
    ) -> AcquisitionManifest:
        """Acquire all tiles for the study area."""
        tiles = tiles or self.STUDY_TILES
        tiles_info = []
        total_size = 0

        for lat, lon in tiles:
            tile_id = self._tile_id(lat, lon)
            dest = self._dem_path(lat, lon)
            cache_meta = self._cache_path(lat, lon)

            # Check if already cached and valid
            if dest.exists() and cache_meta.exists():
                with cache_meta.open() as f:
                    cached = json.load(f)
                if dest.exists() and dest.stat().st_size == cached["file_size"]:
                    # Verify checksum
                    sha256 = self._compute_sha256(dest)
                    if sha256 == cached["sha256"]:
                        tiles_info.append(DEMTileInfo(**cached))
                        total_size += cached["file_size"]
                        continue

            # Check if tile exists
            if not self._verify_tile_exists(lat, lon):
                raise DEMAcquisitionError.tile_not_available(tile_id)

            # Download
            tile_info = self._download_with_retries(lat, lon, dest)

            # Cache metadata
            cache_meta.parent.mkdir(parents=True, exist_ok=True)
            with cache_meta.open("w") as f:
                json.dump(tile_info, f, indent=2)

            tiles_info.append(DEMTileInfo(**tile_info))
            total_size += tile_info["file_size"]

        # Create manifest
        manifest = AcquisitionManifest(
            dataset="Copernicus DEM GLO-30 Public",
            version="2024",
            retrieval_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            tiles=tiles_info,
            total_size=total_size,
            licence="CC BY 4.0 (Copernicus Free & Open Data Policy)",
            source_catalog="AWS Open Data Registry: s3://copernicus-dem-30m/",
        )

        # Save manifest
        manifest_path = self._manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return manifest

    def verify_manifest(self, manifest_path: Path | None = None) -> bool:
        """Verify all files in manifest match checksums."""
        manifest_path = manifest_path or self._manifest_path()
        if not manifest_path.exists():
            return False

        with manifest_path.open() as f:
            manifest = json.load(f)

        for tile_data in manifest["tiles"]:
            path = Path(tile_data["local_path"])
            if not path.exists():
                return False

            sha256 = self._compute_sha256(Path(tile_data["local_path"]))
            if sha256 != tile_data["sha256"]:
                return False

        return True

    def get_study_area_bounds(self) -> tuple[float, float, float, float]:
        """Get geographic bounds of study area in WGS84 (min_lon, min_lat, max_lon, max_lat)."""
        # Tiles are 1x1 degree, N16E079 covers 79-80E, 16-17N
        # Core tiles: N16E079, N16E080, N16E081
        return (79.0, 16.0, 82.0, 17.0)


# Convenience function for quick acquisition
def acquire_dem(
    tiles: list[tuple[int, int]] | None = None,
    cache_dir: str | Path = "data/cache",
    raw_dir: str | Path = "data/raw/dem",
) -> AcquisitionManifest:
    """Acquire DEM tiles for study area."""
    acquisition = DEMAcquisition(cache_dir=cache_dir, raw_dir=raw_dir)
    return acquisition.acquire_study_area(tiles)
