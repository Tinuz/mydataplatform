FROM apache/superset:latest

# Switch to root om packages te installeren
USER root

# Eerst pip installeren in de venv, dan de database drivers
# We moeten expliciet --upgrade gebruiken om pip in de venv te krijgen
RUN curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
    /app/.venv/bin/python /tmp/get-pip.py && \
    rm /tmp/get-pip.py && \
    /app/.venv/bin/pip install --no-cache-dir \
        psycopg2-binary==2.9.9 \
        duckdb==1.1.3 \
        duckdb-engine==0.13.2

# Terug naar superset user voor security
USER superset
