import express from "express";
import helmet from "helmet";
import cors from "cors";
import pkg from "pg";

import swaggerUi from "swagger-ui-express";
import YAML from "yamljs";
import path from "path";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const { Pool } = pkg;

const {
    PGHOST = "postgres",
    PGPORT = "5432",
    PGDATABASE = "superset",
    PGUSER = "superset",
    PGPASSWORD = "superset",
    API_PORT = "3000"
} = process.env;

const pool = new Pool({
    host: PGHOST, port: Number(PGPORT),
    database: PGDATABASE, user: PGUSER, password: PGPASSWORD,
    max: 10, idleTimeoutMillis: 30_000
});

const app = express();
app.use(helmet());
app.use(cors()); // Kong doet ook CORS, maar fijn voor local tests.
app.use(express.json());

// Health
app.get("/healthz", (_, res) => res.json({ ok: true }));

// GET /towers?limit=100&offset=0&radio=LTE&mcc=204&bbox=minLon,minLat,maxLon,maxLat
app.get("/towers", async (req, res) => {
    const { limit = "100", offset = "0", radio, mcc, bbox } = req.query;

    const lim = Math.min(Math.max(parseInt(limit, 10) || 100, 1), 1000);
    const off = Math.max(parseInt(offset, 10) || 0, 0);

    const where = [];
    const params = [];
    let i = 1;

    if (radio) { where.push(`radio = $${i++}`); params.push(String(radio)); }
    if (mcc) { where.push(`mcc = $${i++}`); params.push(Number(mcc)); }

    // bbox filter: lon/lat between corners
    if (bbox) {
        const parts = String(bbox).split(",").map(Number);
        if (parts.length === 4 && parts.every(v => Number.isFinite(v))) {
            const [minLon, minLat, maxLon, maxLat] = parts;
            where.push(`lon BETWEEN $${i} AND $${i + 1}`); params.push(minLon, maxLon); i += 2;
            where.push(`lat BETWEEN $${i} AND $${i + 1}`); params.push(minLat, maxLat); i += 2;
        }
    }

    const sql = `
  SELECT
    radio, mcc, net, area, cell, unit, lon, lat,
    range_m AS "range", samples, changeable, created_ts AS created,
    updated_ts AS updated,
    average_signal AS "averageSignal"
  FROM cell_towers.clean_204
  ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
  ORDER BY samples DESC
  LIMIT $${i} OFFSET $${i + 1}
`;
    params.push(lim, off);

    try {
        const { rows } = await pool.query(sql, params);
        res.json({ count: rows.length, items: rows });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "query_failed" });
    }
});

// GET /towers/:cell (cell id is BIGINT)
app.get("/towers/:cell", async (req, res) => {
    const cell = BigInt(req.params.cell); // validate
const sql = `
  SELECT
    radio, mcc, net, area, cell, unit, lon, lat,
    range_m AS "range", samples, changeable, created_ts AS created,
    updated_ts AS updated,
    average_signal AS "averageSignal"
  FROM cell_towers.clean_204
  WHERE cell = $1
`;
    try {
        const { rows } = await pool.query(sql, [cell.toString()]);
        if (!rows.length) return res.status(404).json({ error: "not_found" });
        res.json(rows[0]);
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "query_failed" });
    }
});

// GET /api/v1/weather/observations?station=Amsterdam&start_date=2025-01-01&end_date=2025-01-31&limit=100
app.get("/api/v1/weather/observations", async (req, res) => {
    const { station, start_date, end_date, limit = "100", offset = "0" } = req.query;

    const lim = Math.min(Math.max(parseInt(limit, 10) || 100, 1), 1000);
    const off = Math.max(parseInt(offset, 10) || 0, 0);

    const where = [];
    const params = [];
    let i = 1;

    if (station) {
        where.push(`station_name ILIKE $${i++}`);
        params.push(`%${String(station)}%`);
    }
    if (start_date) {
        where.push(`timestamp >= $${i++}`);
        params.push(String(start_date));
    }
    if (end_date) {
        where.push(`timestamp <= $${i++}`);
        params.push(String(end_date));
    }

    const sql = `
  SELECT
    station_name, timestamp, temperature, humidity, wind_speed,
    precipitation, rain, wind_direction, pressure, feels_like_temp,
    data_quality, ingestion_time, processed_at
  FROM weather.observations
  ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
  ORDER BY timestamp DESC
  LIMIT $${i} OFFSET $${i + 1}
`;
    params.push(lim, off);

    try {
        const { rows } = await pool.query(sql, params);
        res.json({ count: rows.length, items: rows });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "query_failed" });
    }
});

// GET /api/v1/weather/observations/latest - Get latest observation per station
app.get("/api/v1/weather/observations/latest", async (req, res) => {
    const { station } = req.query;

    const where = station ? `WHERE station_name ILIKE $1` : "";
    const params = station ? [`%${String(station)}%`] : [];

    const sql = `
  SELECT
    station_name, timestamp, temperature, humidity, wind_speed,
    feels_like_temp, pressure, data_quality
  FROM weather.latest_weather
  ${where}
  ORDER BY station_name
`;

    try {
        const { rows } = await pool.query(sql, params);
        res.json({ count: rows.length, items: rows });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "query_failed" });
    }
});

// GET /api/v1/weather/stations - Get all weather stations
app.get("/api/v1/weather/stations", async (req, res) => {
    const sql = `
  SELECT
    station_name, latitude, longitude, total_observations,
    last_observation, avg_temperature, min_temperature, max_temperature
  FROM weather.station_metrics
  ORDER BY station_name
`;

    try {
        const { rows } = await pool.query(sql);
        res.json({ count: rows.length, items: rows });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "query_failed" });
    }
});

// Serve OpenAPI & Swagger UI
const openapiPath = path.join(__dirname, "openapi.yaml");
const openapiDoc = YAML.load(openapiPath);

// (Optioneel) overschrijf server-URLs dynamisch voor lokale dev:
openapiDoc.servers = [
    { url: "http://localhost:8000/api", description: "Via Kong" },
    { url: "http://localhost:3100", description: "Direct" }
];

app.get("/openapi.yaml", (_, res) => res.sendFile(openapiPath));
app.use("/docs", swaggerUi.serve, swaggerUi.setup(openapiDoc));


app.listen(Number(API_PORT), "0.0.0.0", () => {
    console.log(`cell-towers api listening on :${API_PORT}`);
});