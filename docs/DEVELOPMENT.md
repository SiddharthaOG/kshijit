# Kshitij — Local Development, DEM Acquisition, and QGIS Connection

## Local Workflow

### 1. Start the stack

```bash
docker compose up -d
```

Verify the database is healthy:

```bash
docker compose ps
# EXPECTED: db should show "healthy"
```

### 2. Run the smoke test

```bash
docker compose up --abort-on-container-exit smoke-test
```

If the above fails because the smoke-test image needs rebuilding:

```bash
docker compose up --build --abort-on-container-exit smoke-test
```

### 3. Make code changes

Edit source files as needed. Changes to `requirements.txt` require a rebuild:

```bash
docker compose up --build -d
```

### 4. Stop the stack

```bash
docker compose down
```

(Volumes are preserved unless explicitly removed with `docker compose down -v`.)

## DEM Acquisition Workflow (M1.2)

### 1. Configure study area (optional)

Edit `src/kshitij_model/config.py` to modify study area tiles:

```python
study_tiles: list[tuple[int, int]] = [
    (16, 79),  # N16E079
    (16, 80),  # N16E080
    (16, 81),  # N16E081
]
```

### 2. Acquire DEM tiles

```bash
# From project root
python -m kshitij_model.dem_acquisition
```

Or programmatically:

```python
from kshitij_model.dem_acquisition import acquire_dem
from kshitij_model.config import get_config

config = get_config()
# Optionally override study tiles
manifest = acquire_dem(tiles=[(16, 79), (16, 80), (16, 81)])
print(f"Downloaded {len(manifest.tiles)} tiles, {manifest.total_size/1e6:.1f} MB total")
```

### 3. Verify acquisition

```bash
# Verify manifest checksums
python -c "from kshitij_model.dem_acquisition import DEMAcquisition; a = DEMAcquisition(); print('OK' if a.verify_manifest() else 'FAILED')"
```

### 4. Inspect downloaded tiles

```bash
# List downloaded tiles
ls -la data/raw/dem/

# Inspect tile metadata (requires rasterio)
python -c "
import rasterio
for tile in ['N16E079', 'N16E080', 'N16E081']:
    with rasterio.open(f'data/raw/dem/{tile}.tif') as src:
        print(f'{tile}: {src.shape}, {src.crs}, {src.bounds}')
"
```

### 5. Verify manifest checksums

```bash
python -c "from kshitij_model.dem_acquisition import DEMAcquisition; a = DEMAcquisition(); print('OK' if a.verify_manifest() else 'FAILED')"
```

### Output locations

- **Raw tiles:** `data/raw/dem/N16E079.tif`, `N16E080.tif`, `N16E081.tif`
- **Cache metadata:** `data/cache/N16E079.json`, `N16E080.json`, `N16E081.json`
- **Manifest:** `data/cache/manifest.json`

## Local Workflow (Docker)

### 1. Start the stack

```bash
docker compose up -d
```

Verify the database is healthy:

```bash
docker compose ps
# EXPECTED: db should show "healthy"
```

### 2. Run the smoke test

```bash
docker compose up --abort-on-container-exit smoke-test
```

If the above fails because the smoke-test image needs rebuilding:

```bash
docker compose up --build --abort-on-container-exit smoke-test
```

### 3. Make code changes

Edit source files as needed. Changes to `requirements.txt` require a rebuild:

```bash
docker compose up --build -d
```

### 4. Stop the stack

```bash
docker compose down
```

(Volumes are preserved unless explicitly removed with `docker compose down -v`.)

## Connecting QGIS to the Local PostGIS Database

QGIS can connect directly to the running PostGIS instance for visual inspection of geospatial data.

### Steps:

1. **Start the stack** (if not already running):
   ```bash
   docker compose up -d
   ```

2. **Find the Docker-host IP** (macOS/Windows may need `host.docker.internal` or the VM IP):
   - Docker Desktop → Settings → Resources → Ports → "Expose daemon on TCP..."
   - Or use `docker inspect kshitij-db` and look at `NetworkSettings.Networks`

3. **In QGIS**, click **Layer** → **Add Layer** → **Add PostGIS Layer**

4. **Connection parameters**:
   - **Host**: `localhost` (if using Docker Desktop's TCP endpoint) or `host.docker.internal`
   - **Port**: `5432`
   - **Database**: `kshitij_db`
   - **User**: `kshitij_dev`
   - **Password**: (the password set in your `.env` file)
   - **Enable PostGIS connections**: ✓ checked

5. **Connect** and explore:
   - The `public` schema will be available
   - You can add new tables/views from the postGIS connection
   - Useful for verifying that the smoke-test spatial query created usable geometry

### Tips:

- If `localhost` doesn't work, try `127.0.0.1` — some Docker setups bind differently.
- The password in `.env.example` is `dev_password_must_change`; change it before using anything other than throwaway dev.
- To disconnect, just close the PostGIS dialog; no cleanup is needed on the database side.

## Development Checklist

- [ ] `docker compose up -d` starts `db` in healthy state
- [ ] `docker compose up --abort-on-container-exit smoke-test` exits with code 0
- [ ] `.env` is gitignored and never committed
- [ ] QGIS can connect with the credentials from `.env`
- [ ] All smoke test checks pass (connection, PostgreSQL version, PostGIS version, spatial query)
- [ ] DEM tiles acquired: `python -m kshitij_model.dem_acquisition`
- [ ] Manifest verified: `python -c "from kshitij_model.dem_acquisition import DEMAcquisition; a = DEMAcquisition(); print('OK' if a.verify_manifest() else 'FAILED')"`

## Path Configuration

All data paths are configurable via `DEMConfig` in `src/kshitij_model/config.py`:

```python
@dataclass
class DEMConfig:
    cache_dir: str = "data/cache"
    raw_dir: str = "data/raw/dem"
    processed_dir: str = "data/processed"
    study_tiles: list[tuple[int, int]] = [(16, 79), (16, 80), (16, 81)]
```

Override paths via environment variables or by modifying the config before acquisition.