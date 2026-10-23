"""Configuration for DEM acquisition and processing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DEMConfig:
    """Configuration for DEM acquisition and processing."""

    # Study area tiles (lat, lon) for core Vijayawada area
    study_tiles: list[tuple[int, int]] = (
        (16, 79),  # N16E079
        (16, 80),  # N16E080
        (16, 81),  # N16E081
    )

    # Extended tiles (optional)
    extended_tiles: list[tuple[int, int]] = (
        (15, 79),
        (15, 80),
        (15, 81),
        (17, 79),
        (17, 80),
        (17, 81),
    )

    # Copernicus DEM GLO-30 configuration
    dem_bucket: str = "copernicus-dem-30m"
    dem_region: str = "us-east-1"
    tile_prefix: str = "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
    dem_filename: str = "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif"

    # Dataset metadata
    dataset_name: str = "Copernicus DEM GLO-30 Public"
    dataset_version: str = "2024"
    licence: str = "CC BY 4.0 (Copernicus Free & Open Data Policy)"
    source_catalog: str = "AWS Open Data Registry: s3://copernicus-dem-30m/"

    # Download settings
    download_timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 5.0

    # Storage paths
    cache_dir: str = "data/cache"
    raw_dir: str = "data/raw/dem"
    processed_dir: str = "data/processed"

    # Study area bounds (min_lon, min_lat, max_lon, max_lat) in WGS84
    study_area_bounds: tuple[float, float, float, float] = (79.0, 16.0, 82.0, 17.0)

    # CRS information
    source_crs: str = "EPSG:4326"  # WGS84
    vertical_datum: str = "EGM2008"  # EGM2008 geoid

    # NoData handling
    nodata_value: float = -32768.0  # Common NoData value for Copernicus DEM

    def __post_init__(self):
        """Validate configuration."""
        if not self.study_tiles:
            raise ValueError("study_tiles cannot be empty")


def get_config() -> DEMConfig:
    """Get default DEM configuration."""
    return DEMConfig()
