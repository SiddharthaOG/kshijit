# Kshitij — Local Development and QGIS Connection

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