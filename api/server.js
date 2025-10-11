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