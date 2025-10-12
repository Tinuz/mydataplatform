# Weather API Documentation

## Overview

The Weather API provides access to weather observations and station information from the data platform. The API is exposed through Kong API Gateway with rate limiting and API key authentication.

## Base URL

```
http://localhost:8000/api/v1/weather
```

## Authentication

All weather endpoints require an API key. Include the key in your request using one of these headers:

- `X-API-Key: your-api-key`
- `apikey: your-api-key`

### Available API Keys

| Consumer | API Key | Purpose |
|----------|---------|---------|
| weather-client | `demo-weather-api-key-2025` | Demo/testing |
| internal-dagster | `dagster-internal-key-secure` | Internal pipeline use |

### Example

```bash
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/observations/latest
```

## Rate Limiting

The Weather API has the following rate limits per IP address:

- **100 requests per minute**
- **5,000 requests per hour**

When you exceed the rate limit, you'll receive a `429 Too Many Requests` response.

## Endpoints

### 1. Get Latest Weather Observations

Get the most recent weather observation for each station.

**Endpoint:** `GET /api/v1/weather/observations/latest`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| station | string | Optional. Filter by station name (fuzzy match, case-insensitive) |

**Example Request:**

```bash
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations/latest"
```

**Example Response:**

```json
{
  "count": 7,
  "items": [
    {
      "station_name": "Amsterdam",
      "timestamp": "2025-10-12T12:45:00.000Z",
      "temperature": 15.7,
      "humidity": 79,
      "wind_speed": 9.4,
      "feels_like_temp": 13.61,
      "pressure": 1030.9,
      "data_quality": "validated"
    }
  ]
}
```

**Filter by station:**

```bash
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations/latest?station=Amsterdam"
```

### 2. Get Weather Observations

Get historical weather observations with filtering and pagination.

**Endpoint:** `GET /api/v1/weather/observations`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| station | string | Optional. Filter by station name (fuzzy match) |
| start_date | string | Optional. Start date/time (ISO 8601 format) |
| end_date | string | Optional. End date/time (ISO 8601 format) |
| limit | integer | Optional. Number of records to return (1-1000, default: 100) |
| offset | integer | Optional. Pagination offset (default: 0) |

**Example Requests:**

```bash
# Get recent observations for Amsterdam
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?station=Amsterdam&limit=10"

# Get observations for a date range
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?start_date=2025-10-12&end_date=2025-10-13"

# Pagination
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?limit=50&offset=50"
```

**Example Response:**

```json
{
  "count": 3,
  "items": [
    {
      "station_name": "Amsterdam",
      "timestamp": "2025-10-12T12:45:00.000Z",
      "temperature": 15.7,
      "humidity": 79,
      "wind_speed": 9.4,
      "precipitation": 0,
      "rain": 0,
      "wind_direction": 339,
      "pressure": 1030.9,
      "feels_like_temp": 13.61,
      "data_quality": "validated",
      "ingestion_time": "2025-10-12T10:50:05.878Z",
      "processed_at": "2025-10-12T10:51:05.763Z"
    }
  ]
}
```

### 3. Get Weather Stations

Get information about all weather stations with metrics.

**Endpoint:** `GET /api/v1/weather/stations`

**Query Parameters:** None

**Example Request:**

```bash
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/stations"
```

**Example Response:**

```json
{
  "count": 7,
  "items": [
    {
      "station_name": "Amsterdam",
      "latitude": 52.3676,
      "longitude": 4.9041,
      "total_observations": 2,
      "last_observation": "2025-10-12T12:45:00.000Z",
      "avg_temperature": 15.7,
      "min_temperature": 15.7,
      "max_temperature": 15.7
    }
  ]
}
```

## Response Format

All endpoints return JSON with the following structure:

```json
{
  "count": <number>,
  "items": [<array of objects>]
}
```

## Error Responses

### 401 Unauthorized

Missing or invalid API key.

```json
{
  "message": "No API key found in request",
  "request_id": "caef4d007ac40f763c9e5268308dba3a"
}
```

### 429 Too Many Requests

Rate limit exceeded.

```json
{
  "message": "API rate limit exceeded",
  "request_id": "..."
}
```

### 500 Internal Server Error

Query or server error.

```json
{
  "error": "query_failed"
}
```

## Data Quality

The `data_quality` field in weather observations indicates the validation status:

- `validated`: Data passed all quality checks
- `flagged`: Data has potential issues
- `raw`: Data not yet validated

## Usage Examples

### Python

```python
import requests

API_KEY = "demo-weather-api-key-2025"
BASE_URL = "http://localhost:8000/api/v1/weather"

headers = {"X-API-Key": API_KEY}

# Get latest weather
response = requests.get(f"{BASE_URL}/observations/latest", headers=headers)
weather = response.json()

for item in weather["items"]:
    print(f"{item['station_name']}: {item['temperature']}°C")
```

### JavaScript

```javascript
const API_KEY = "demo-weather-api-key-2025";
const BASE_URL = "http://localhost:8000/api/v1/weather";

async function getLatestWeather() {
  const response = await fetch(`${BASE_URL}/observations/latest`, {
    headers: {
      "X-API-Key": API_KEY
    }
  });
  
  const data = await response.json();
  return data.items;
}
```

### curl

```bash
# Get all stations
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/stations | jq '.'

# Get weather for specific station
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?station=Amsterdam&limit=5" \
  | jq '.items[] | {station: .station_name, temp: .temperature}'
```

## OpenAPI Specification

The full OpenAPI specification is available at:

```
http://localhost:8000/openapi.yaml
```

Interactive Swagger UI documentation:

```
http://localhost:8000/docs
```

## Support

For issues or questions:
- Check the [Superset dashboards](http://localhost:8088) for data visualization
- Review [Amundsen catalog](http://localhost:5005) for data lineage
- Check [Marquez](http://localhost:3003) for pipeline lineage

## Architecture

```
Client → Kong Gateway → API Service → PostgreSQL
         (Auth + Rate Limiting)
```

The Weather API is part of a larger data platform that includes:
- **Dagster**: Data pipeline orchestration
- **Marquez**: Lineage tracking (OpenLineage)
- **Amundsen**: Data catalog and discovery
- **Superset**: Data visualization and dashboards
- **Kong**: API gateway with authentication and rate limiting
