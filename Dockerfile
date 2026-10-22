# Dockerfile for Kshitij M0 smoke test runner
# Builds a minimal Python image with psycopg2 for DB connectivity testing.
# Used by the smoke_test.py script to verify database readiness.

FROM python:3.12-slim

WORKDIR /app

# Install minimal dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy smoke test script
COPY scripts/smoke_test.py .

# Entrypoint runs the smoke test and exits with appropriate code
ENTRYPOINT ["python", "smoke_test.py"]