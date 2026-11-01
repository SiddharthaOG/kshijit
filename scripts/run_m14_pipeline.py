#!/usr/bin/env python
"""M1.4 Flood Extent Pipeline — Command-line interface.

Runs the complete DEM-to-flood-extent workflow using a supplied river vector.

Usage:
    python scripts/run_m14_pipeline.py \
        --river-vector data/river.gpkg \
        --water-level 15.0 \
        --output data/processed/flood_extent.tif \
        --aoi-bounds 80.5 16.3 81.2 16.7 \
        --river-buffer 30

Environment:
    Requires fiona for vector reading (install with: pip install fiona)
    Uses cached DEM tiles in data/raw/dem/ if available.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kshitij_model.pipeline import PipelineConfig, PipelineError, run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M1.4 Flood Extent Pipeline: DEM to flood extent using threshold connectivity",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required arguments
    parser.add_argument(
        "--river-vector",
        type=Path,
        required=True,
        help="Path to river vector file (GeoJSON, GeoPackage, Shapefile)",
    )
    parser.add_argument(
        "--water-level",
        type=float,
        required=True,
        help="Water level threshold in meters (EGM2008 vertical datum)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/flood_extent.tif"),
        help="Output flood extent GeoTIFF path",
    )

    # Optional DEM/AOI arguments
    parser.add_argument(
        "--aoi-bounds",
        type=float,
        nargs=4,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="Area of interest bounds in WGS84 (min_lon min_lat max_lon max_lat)",
    )
    parser.add_argument(
        "--dem-tiles",
        type=int,
        nargs="+",
        metavar=("LAT LON"),
        help="DEM tiles as lat lon pairs (e.g., 16 79 16 80 16 81)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache"),
        help="DEM cache directory",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/dem"),
        help="Raw DEM directory",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed"),
        help="Processed data output directory",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-download of DEM tiles (ignore cache)",
    )

    # River mask arguments
    parser.add_argument(
        "--river-buffer",
        type=float,
        default=0.0,
        help="Buffer distance in meters to apply to river geometries",
    )
    parser.add_argument(
        "--river-all-touched",
        action="store_true",
        default=True,
        help="Rasterize all pixels touched by river geometry (default: True)",
    )
    parser.add_argument(
        "--river-center-only",
        action="store_false",
        dest="river_all_touched",
        help="Rasterize only pixels whose center is within river geometry",
    )
    parser.add_argument(
        "--write-river-mask",
        action="store_true",
        help="Write river mask GeoTIFF for inspection",
    )
    parser.add_argument(
        "--river-mask-output",
        type=Path,
        default=Path("data/processed/river_mask.tif"),
        help="River mask output path (if --write-river-mask)",
    )

    # Model arguments
    parser.add_argument(
        "--nodata",
        type=float,
        default=-32767.0,
        help="NoData sentinel value for DEM",
    )
    parser.add_argument(
        "--compression",
        type=str,
        default="lzw",
        choices=["lzw", "deflate", "none"],
        help="Output GeoTIFF compression",
    )

    # Logging
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress info logging",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Validate river vector exists
    if not args.river_vector.exists():
        logger.error("River vector file not found: %s", args.river_vector)
        return 1

    # Parse DEM tiles if provided
    dem_tiles = None
    if args.dem_tiles:
        if len(args.dem_tiles) % 2 != 0:
            logger.error("--dem-tiles requires lat lon pairs (even number of integers)")
            return 1
        dem_tiles = [(args.dem_tiles[i], args.dem_tiles[i + 1])
                     for i in range(0, len(args.dem_tiles), 2)]

    # Build pipeline config
    config = PipelineConfig(
        dem_tiles=dem_tiles,
        cache_dir=args.cache_dir,
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        aoi_bounds=tuple(args.aoi_bounds) if args.aoi_bounds else None,
        river_vector_path=args.river_vector,
        river_buffer_meters=args.river_buffer,
        river_all_touched=args.river_all_touched,
        water_level=args.water_level,
        nodata_value=args.nodata,
        output_path=args.output,
        write_river_mask=args.write_river_mask,
        river_mask_output_path=args.river_mask_output if args.write_river_mask else None,
        use_cached_dem=not args.no_cache,
        compression=args.compression,
    )

    # Run pipeline
    try:
        logger.info("Starting M1.4 pipeline")
        logger.info("River vector: %s", args.river_vector)
        logger.info("Water level: %.2f m", args.water_level)
        logger.info("Output: %s", args.output)

        result = run_pipeline(config)

        logger.info("Pipeline completed successfully")
        logger.info("Flood extent: %s", result.flood_extent_path)
        logger.info("Flooded cells: %d / %d valid (%.1f%%)",
                    result.flooded_cell_count, result.valid_cell_count,
                    100 * result.flooded_cell_count / result.valid_cell_count if result.valid_cell_count else 0)
        logger.info("Output metadata: %s", result.flood_extent_meta)

        return 0

    except PipelineError as e:
        logger.error("Pipeline failed: %s", e)
        return 1
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())