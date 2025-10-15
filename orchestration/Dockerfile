# Dagster + Great Expectations runtime
FROM python:3.11-slim

WORKDIR /opt/dagster/app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Dagster project
COPY . .

# Expose Dagster webserver port
EXPOSE 3000

# Set environment
ENV DAGSTER_HOME=/opt/dagster/app/dagster_home
ENV PYTHONPATH=/opt/dagster/app

# Create dagster home directory
RUN mkdir -p $DAGSTER_HOME

# Create startup script that runs both daemon and webserver
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Starting Dagster daemon..."\n\
dagster-daemon run &\n\
\n\
echo "Starting Dagster webserver..."\n\
dagster-webserver -h 0.0.0.0 -p 3000 -w /opt/dagster/app/workspace.yaml\n\
' > /opt/dagster/start.sh && chmod +x /opt/dagster/start.sh

# Use startup script
CMD ["/opt/dagster/start.sh"]
