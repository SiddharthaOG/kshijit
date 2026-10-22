"""
Kshitij Milestone M0 — Database smoke test.

Verifies:
1. Database connection succeeds.
2. PostgreSQL version is readable.
3. PostGIS is installed and version is queryable.
4. A basic PostGIS spatial query (ST_AsText(ST_Point(0,0))) succeeds.

Exits with nonzero code if any check fails.
"""

import os
import sys
import time

import psycopg2
import psycopg2.extensions

# ---------------------------------------------------------------------------
# Configuration — read from environment (matching .env.example)
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "kshitij_db")
DB_USER = os.getenv("POSTGRES_USER", "kshitij_dev")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dev_password_must_change")

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_connection(max_retries: int = 12, delay: float = 5.0) -> psycopg2.extensions.connection:
    """Attempt to open a connection, retrying until the DB is ready.

    Args:
        max_retries: Maximum number of connection attempts.
        delay: Seconds to wait between retries.

    Returns:
        An open psycopg2 connection.

    Raises:
        SystemExit: If all retries are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
            # Verify the connection is healthy
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(delay)
            else:
                print(f"❌ Failed to connect to database after {max_retries} attempts")
                raise SystemExit(1)
    raise SystemExit(1)  # pragma: no cover


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_connection(conn: psycopg2.extensions.connection) -> bool:
    """Check that the database connection succeeds."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        print(f"✅ Connection: OK (result={result})")
        return True
    except Exception as exc:  # broad; we want to report it
        print(f"❌ Connection check failed: {exc}")
        return False


def check_postgresql_version(conn: psycopg2.extensions.connection) -> bool:
    """Check that PostgreSQL responds with its version."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        print(f"✅ PostgreSQL version: {version}")
        return True
    except Exception as exc:
        print(f"❌ PostgreSQL version check failed: {exc}")
        return False


def check_postgis_version(conn: psycopg2.extensions.connection) -> bool:
    """Check that PostGIS is installed and its version can be queried."""
    try:
        cursor = conn.cursor()
        # PostGIS exposes its version via the PostGIS extension view
        cursor.execute("SELECT PostGIS_Version()")
        version = cursor.fetchone()[0]
        cursor.close()
        print(f"✅ PostGIS version: {version}")
        return True
    except Exception as exc:
        print(f"❌ PostGIS version check failed: {exc}")
        return False


def check_spatial_query(conn: psycopg2.extensions.connection) -> bool:
    """Check that a basic PostGIS spatial query succeeds.

    Runs ST_AsText(ST_Point(0,0)) which should return 'POINT(0 0)'.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ST_AsText(ST_Point(0, 0))")
        result = cursor.fetchone()[0]
        cursor.close()
        print(f"✅ Spatial query result: {result}")
        # Validate the expected output
        if "POINT" not in result:
            print(f"⚠️  Spatial query returned unexpected geometry: {result}")
            return False
        return True
    except Exception as exc:
        print(f"❌ Spatial query failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run all smoke checks and return an exit code."""
    conn = get_connection()
    try:
        all_passed = True

        checks = [
            ("Database connection", lambda: check_connection(conn)),
            ("PostgreSQL version", lambda: check_postgresql_version(conn)),
            ("PostGIS version", lambda: check_postgis_version(conn)),
            ("PostGIS spatial query", lambda: check_spatial_query(conn)),
        ]

        for label, check_fn in checks:
            if not check_fn():
                all_passed = False

        if all_passed:
            print("\n🟢 All checks passed.")
            return 0
        else:
            print("\n🔴 Some checks failed.")
            return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())