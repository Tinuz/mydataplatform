# Dagster + Great Expectations runtime
FROM python:3.11-slim

WORKDIR /opt/dagster/app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
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

# Default command (webserver) - point to weather_pipeline module
CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "weather_pipeline"]
