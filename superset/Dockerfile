FROM apache/superset:latest

# Switch to root om packages te installeren
USER root

# Installeer pip in de venv en dan de database drivers
# Python zoekt packages in /app/.venv/lib/python3.10/site-packages
RUN python -m ensurepip --default-pip && \
    pip install --target=/app/.venv/lib/python3.10/site-packages --no-cache-dir \
        trino==0.328.0 \
        sqlalchemy-trino==0.5.0 \
        psycopg2-binary==2.9.9

# Terug naar superset user voor security
USER superset
