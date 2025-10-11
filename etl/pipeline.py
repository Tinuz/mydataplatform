import os, io, json
import requests
import boto3
import psycopg2
import uuid, time
from urllib.parse import quote

# ---------- ENV ----------
FILE_URL       = os.environ["FILE_URL"]
RAW_FILENAME   = os.environ.get("RAW_FILENAME") or os.path.basename(FILE_URL)

MARQUEZ_URL       = os.environ.get("MARQUEZ_URL")
MARQUEZ_NAMESPACE = os.environ.get("MARQUEZ_NAMESPACE", "demo")
MARQUEZ_SOURCE_MINIO = os.environ.get("MARQUEZ_SOURCE_MINIO", "minio-lake")
MARQUEZ_SOURCE_PG    = os.environ.get("MARQUEZ_SOURCE_PG", "postgres-warehouse")
MARQUEZ_JOB_NAME     = os.environ.get("MARQUEZ_JOB_NAME", "cell_towers_etl_v1")

MINIO_ENDPOINT   = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
MINIO_BUCKET     = os.environ["MINIO_BUCKET"]
RAW_PREFIX       = os.environ.get("MINIO_RAW_PREFIX", "raw/")
CLEAN_PREFIX     = os.environ.get("MINIO_CLEAN_PREFIX", "clean/")  # gereserveerd

PGHOST=os.environ["PGHOST"]; PGPORT=os.environ["PGPORT"]; PGDATABASE=os.environ["PGDATABASE"]
PGUSER=os.environ["PGUSER"]; PGPASSWORD=os.environ["PGPASSWORD"]

SUPERSET_URL  = os.environ["SUPERSET_URL"].rstrip("/")
SS_USER       = os.environ["SUPERSET_USER"]
SS_PASSWORD   = os.environ["SUPERSET_PASSWORD"]

SCHEMA        = os.environ.get("SCHEMA_NAME","cell_towers")
STAGING_TABLE = os.environ.get("STAGING_TABLE","stg_204")
CLEAN_TABLE   = os.environ.get("CLEAN_TABLE","clean_204")

RAW_KEY   = f"{RAW_PREFIX}{RAW_FILENAME}"

def pg_conn():
    return psycopg2.connect(
        host=PGHOST, port=PGPORT, dbname=PGDATABASE,
        user=PGUSER, password=PGPASSWORD
    )

def ensure_minio_bucket(s3):
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets",[])]
    if MINIO_BUCKET not in existing:
        s3.create_bucket(Bucket=MINIO_BUCKET)

def superset_session():
    import requests
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": SUPERSET_URL,   # bv. http://superset:8088
    })

    # 1) LOGIN → JWT access_token
    r = s.post(f"{SUPERSET_URL}/api/v1/security/login", json={
        "username": SS_USER,
        "password": SS_PASSWORD,
        "provider": "db",
        "refresh": True
    })
    r.raise_for_status()
    access = r.json().get("access_token") or r.json().get("result", {}).get("access_token")
    if not access:
        raise RuntimeError(f"Superset login gaf geen access_token: {r.text}")

    s.headers["Authorization"] = f"Bearer {access}"

    # 2) CSRF ophalen MET Bearer
    r = s.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    r.raise_for_status()
    token = r.json()["result"]
    s.headers["X-CSRFToken"] = token

    return s

def superset_me_user_id(session):
    # let op: géén trailing slash
    r = session.get(f"{SUPERSET_URL}/api/v1/me")
    r.raise_for_status()
    me = r.json()
    return me.get("id") or (me.get("result", {}) or {}).get("id")

def superset_test_connection(session, uri: str):
    # Superset verwacht {"uri": "..."} voor de test
    r = session.post(f"{SUPERSET_URL}/api/v1/database/test_connection", json={"uri": uri})
    # test_connection geeft 200 terug met {"message": "OK"} of {"errors": ...}
    if r.status_code != 200:
        raise RuntimeError(f"Superset test_connection HTTP {r.status_code}: {r.text}")
    data = r.json()
    # Sommige versies geven {"message":"OK"}, andere {"result": true}
    ok = (data.get("message") == "OK") or (data.get("result") is True)
    if not ok:
        raise RuntimeError(f"Superset test_connection fail: {r.text}")
    return True

def superset_ensure_database(session):
    # 0) Bestaat er al 1 DB? dan gebruik die
    r = session.get(f"{SUPERSET_URL}/api/v1/database/")
    r.raise_for_status()
    dbs = r.json().get("result", [])
    if dbs:
        return dbs[0]["id"]

    # 1) Bouw de URI op basis van je env
    sqlalchemy_uri = f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

    # 2) Test de connectie — dit geeft meteen nuttige foutmelding als driver/URI niet klopt
    superset_test_connection(session, sqlalchemy_uri)

    # 3) Create payload – met extra velden die validatie tevreden houden
    payload = {
        "database_name": "Postgres",
        "sqlalchemy_uri": sqlalchemy_uri,
        "expose_in_sqllab": True,
        "allow_csv_upload": True,
        "allow_run_async": False,
        "allow_ctas": False,
        "allow_cvas": False,
        "impersonate_user": False,
        "server_cert": "",
        "extra": "{}",                   # leeg JSON als string
        "masked_encrypted_extra": ""     # leeg
    }

    r = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if r.status_code in (200, 201):
        return r.json()["id"]

    # 4) Als 422 of anders: toon exacte fout van Superset; probeer evt. fallback-vorm
    body = r.text
    # fallback payload variant (sommige builds verwachten een nested database object bij updates, zelden voor create)
    payload_alt = {
        **payload,
        # niets nested nodig voor create; we loggen en geven duidelijk terug
    }
    try:
        r2 = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload_alt)
        if r2.status_code in (200, 201):
            return r2.json()["id"]
        body = f"{body} | alt: {r2.status_code} {r2.text}"
    except Exception as _:
        pass
    raise RuntimeError(f"Superset database create faalde: {r.status_code} {body}")

def register_dataset_in_superset(session):
    me_id = superset_me_user_id(session)
    database_id = superset_ensure_database(session)

    params = {"q": json.dumps({"filters": [
        {"col": "table_name", "opr": "eq", "value": CLEAN_TABLE},
        {"col": "schema",     "opr": "eq", "value": SCHEMA}
    ]})}
    r = session.get(f"{SUPERSET_URL}/api/v1/dataset/", params=params)
    r.raise_for_status()
    if r.json().get("count", 0) > 0:
        print(f"Superset: dataset {SCHEMA}.{CLEAN_TABLE} bestaat al.")
        return

    payload = {
        "database": database_id,
        "schema": SCHEMA,
        "table_name": CLEAN_TABLE,
        "owners": [me_id] if me_id else []
    }
    r = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if r.status_code in (200, 201):
        print(f"Superset: dataset {SCHEMA}.{CLEAN_TABLE} geregistreerd.")
        return

    # Fallback (sommige builds/permissions)
    payload_v2 = {
        "database": {"id": database_id},
        "schema": SCHEMA,
        "table_name": CLEAN_TABLE,
        "owners": [me_id] if me_id else []
    }
    r2 = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload_v2)
    if r2.status_code in (200, 201):
        print(f"Superset: dataset {SCHEMA}.{CLEAN_TABLE} geregistreerd (v2).")
        return

    raise RuntimeError(f"Superset dataset-registratie faalde: {r.status_code} {r.text}")

def mz_request(method, path, payload=None, tries=5, wait=1.5):
    url = f"{MARQUEZ_URL.rstrip('/')}/api/v1{path}"
    last = None
    for i in range(tries):
        try:
            r = requests.request(method, url, json=payload, timeout=15)
            if r.status_code in (200, 201, 202, 204, 409):
                return r
            # 404 kort na start? even opnieuw proberen
            if r.status_code in (404, 503) and i < tries - 1:
                time.sleep(wait)
                continue
            raise RuntimeError(f"Marquez error {r.status_code}: {r.text}")
        except requests.RequestException as e:
            last = e
            if i < tries - 1:
                time.sleep(wait)
                continue
            raise RuntimeError(f"Marquez request failed: {e}") from e

def marquez_register(raw_object_key: str, schema: str, cleaned_table: str):
    """
    Registreer lineage in Marquez:
      - Input dataset  : MinIO object (STREAM)
      - Output dataset : Postgres tabel (DB_TABLE)
      - Job            : MARQUEZ_JOB_NAME
    """
    if not MARQUEZ_URL:
        print("Marquez niet geconfigureerd; skip lineage.")
        return

    ns = MARQUEZ_NAMESPACE

    # 0) Upsert namespace & sources (PUT-by-name)
    mz_request("PUT", f"/namespaces/{quote(ns)}", {
        "ownerName": "etl",
        "description": "Demo namespace"
    })
    
    mz_request("PUT", f"/sources/{quote(MARQUEZ_SOURCE_MINIO)}", {
        "type": "S3",
        "connectionUrl": "s3://lake",
        "description": "MinIO data lake"
    })
    mz_request("PUT", f"/sources/{quote(MARQUEZ_SOURCE_PG)}", {
        "type": "POSTGRESQL",
        "connectionUrl": "postgres://superset@postgres:5432/superset",
        "description": "Warehouse"
    })

    # 1) Logische namen bepalen (en URL-encoden in pad)
    input_name  = f"lake/{raw_object_key}"        # bv. lake/raw/celltowers/204.csv
    output_name = f"{schema}.{cleaned_table}"     # bv. cell_towers.clean_204

    schema_loc = FILE_URL

    # 2) Als dat onverhoopt geen http(s) is, val terug op MinIO HTTP endpoint
    if not (isinstance(schema_loc, str) and schema_loc.startswith(("http://", "https://"))):
        # MINIO_ENDPOINT is bv. "http://minio:9000"
        schema_loc = f"{MINIO_ENDPOINT.rstrip('/')}/{MINIO_BUCKET}/{raw_object_key}"

    print(f"[Marquez] schemaLocation used: {schema_loc}")

    # RAW in MinIO → STREAM (verplicht: schemaLocation als http(s))
    raw_fields = [
        {"name": "radio", "type": "STRING", "description": "Radio technology (GSM, UMTS, LTE, 5G)"},
        {"name": "mcc", "type": "INTEGER", "description": "Mobile Country Code"},
        {"name": "net", "type": "INTEGER", "description": "Network operator code"},
        {"name": "area", "type": "INTEGER", "description": "Location Area Code"},
        {"name": "cell", "type": "BIGINT", "description": "Cell Tower ID"},
        {"name": "unit", "type": "INTEGER", "description": "Unit identifier"},
        {"name": "lon", "type": "DOUBLE", "description": "Longitude coordinate [PII, GeoData]"},
        {"name": "lat", "type": "DOUBLE", "description": "Latitude coordinate [PII, GeoData]"},
        {"name": "range", "type": "BIGINT", "description": "Cell tower coverage range (meters)"},
        {"name": "samples", "type": "BIGINT", "description": "Number of measurement samples"},
        {"name": "changeable", "type": "INTEGER", "description": "Whether location is changeable"},
        {"name": "created", "type": "BIGINT", "description": "Creation timestamp (Unix epoch)"},
        {"name": "updated", "type": "BIGINT", "description": "Last update timestamp (Unix epoch)"},
        {"name": "averageSignal", "type": "INTEGER", "description": "Average signal strength"}
    ]
    
    mz_request("PUT", f"/namespaces/{quote(ns)}/datasets/{quote(input_name, safe='')}", {
        "name": input_name,
        "type": "DB_TABLE",  # Use DB_TABLE to avoid schemaLocation requirement
        "physicalName": f"s3://{input_name}",       
        "sourceName": MARQUEZ_SOURCE_MINIO,
        "description": "Raw cell tower data from public GCS dataset, stored in MinIO data lake (source: https://storage.googleapis.com/cell_tower_data/204.csv)",
        "fields": raw_fields,
        "tags": ["raw", "cell-towers", "telecom", "public-dataset"]
    })

    clean_fields = [
        {"name": "radio", "type": "STRING", "description": "Radio technology (GSM, UMTS, LTE, 5G) - validated"},
        {"name": "mcc", "type": "INTEGER", "description": "Mobile Country Code - validated range"},
        {"name": "net", "type": "INTEGER", "description": "Network operator code"},
        {"name": "area", "type": "INTEGER", "description": "Location Area Code"},
        {"name": "cell", "type": "BIGINT", "description": "Cell Tower ID - deduplicated"},
        {"name": "unit", "type": "INTEGER", "description": "Unit identifier"},
        {"name": "lon", "type": "DOUBLE", "description": "Longitude coordinate - validated [-180, 180] [PII, GeoData, Quality-Checked]"},
        {"name": "lat", "type": "DOUBLE", "description": "Latitude coordinate - validated [-90, 90] [PII, GeoData, Quality-Checked]"},
        {"name": "range", "type": "BIGINT", "description": "Cell tower coverage range (meters)"},
        {"name": "samples", "type": "BIGINT", "description": "Number of measurement samples - quality indicator"},
        {"name": "changeable", "type": "INTEGER", "description": "Whether location is changeable"},
        {"name": "created", "type": "BIGINT", "description": "Creation timestamp (Unix epoch)"},
        {"name": "updated", "type": "BIGINT", "description": "Last update timestamp (Unix epoch)"},
        {"name": "averageSignal", "type": "INTEGER", "description": "Average signal strength (dBm)"}
    ]

    mz_request("PUT", f"/namespaces/{quote(ns)}/datasets/{quote(output_name, safe='')}", {
        "name": output_name,
        "type": "DB_TABLE",                       # CLEAN als DB_TABLE
        "physicalName": output_name,
        "sourceName": MARQUEZ_SOURCE_PG,
        "description": "Cleaned and validated cell tower data ready for analytics. Quality checks applied: coordinates validated, duplicates removed, indexed for performance.",
        "fields": clean_fields,
        "tags": ["clean", "analytics-ready", "indexed", "cell-towers", "quality-checked"]
    })

    # 3) Job + run registreren
    job = MARQUEZ_JOB_NAME
    mz_request("PUT", f"/namespaces/{quote(ns)}/jobs/{quote(job, safe='')}", {
        "name": job,
        "type": "BATCH",   # ← essentieel: BATCH of STREAM
        "inputs":  [{"namespace": ns, "name": input_name}],
        "outputs": [{"namespace": ns, "name": output_name}],
        "context": {
            "engine": "python-etl",
            "version": "1.0",
            "owner": "Data Engineering Team",
            "sla": "daily",
            "confidentiality": "public"
        },
        "location": "https://github.com/your-org/data-platform/blob/main/etl/pipeline.py",
        "description": """
Cell Towers ETL Pipeline v1

**Purpose**: Ingests public cell tower location data and prepares it for analytics

**Data Flow**:
1. Download CSV from Google Cloud Storage public dataset
2. Store raw data in MinIO data lake (S3-compatible)
3. Load to PostgreSQL staging table
4. Apply data quality transformations:
   - Validate coordinate ranges (lat: -90 to 90, lon: -180 to 180)
   - Remove duplicates based on cell tower ID
   - Validate radio types
5. Create indexed clean table for fast queries

**Quality Checks**:
- ✓ No NULL values in key columns (lat, lon, cell)
- ✓ Coordinate validation
- ✓ Duplicate detection
- ✓ Index creation for performance

**Output**: Analytics-ready dataset with 47K+ cell tower locations
**Owner**: Data Engineering Team
**SLA**: Daily refresh
**Data Classification**: Public
        """.strip()
    })

    run_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    mz_request("POST", f"/namespaces/{quote(ns)}/jobs/{quote(job, safe='')}/runs", {
        "id": run_id,
        "nominalStartTime": now
    })

    mz_request("POST", f"/jobs/runs/{run_id}/complete", {})
    print("Marquez lineage geregistreerd. UI: http://localhost:3000")

# ---------- 1) Download public CSV ----------
print(f"Downloaden: {FILE_URL}")
resp = requests.get(FILE_URL, stream=True, timeout=120)
resp.raise_for_status()
raw_bytes = resp.content
print(f"Ophalen gereed ({len(raw_bytes)} bytes).")

# ---------- 2) Upload naar MinIO (raw) ----------
print(f"Uploaden naar MinIO s3://{MINIO_BUCKET}/{RAW_KEY} ...")
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
)
ensure_minio_bucket(s3)
s3.put_object(Bucket=MINIO_BUCKET, Key=RAW_KEY, Body=raw_bytes, ContentType="text/csv")
print("Upload gereed.")

# ---------- 3) Laden naar Postgres (staging) ----------
print("Laden naar Postgres (staging) ...")
conn = pg_conn(); conn.autocommit = True
cur = conn.cursor()
cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")

# staging schema (pas kolommen naar jouw CSV indien nodig)
cur.execute(f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.{STAGING_TABLE} (
  radio TEXT,
  mcc INT,
  net INT,
  area INT,
  cell BIGINT,
  unit INT,
  lon DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  range BIGINT,
  samples BIGINT,
  changeable INT,
  created BIGINT,
  updated BIGINT,
  averageSignal INT
);
TRUNCATE TABLE {SCHEMA}.{STAGING_TABLE};
""")

buf = io.StringIO(raw_bytes.decode("utf-8"))
cur.copy_expert(f"COPY {SCHEMA}.{STAGING_TABLE} FROM STDIN WITH CSV HEADER", buf)
print("Staging geladen.")

# ---------- 4) Clean/transform ----------
print("Opschonen/transform naar clean-tabel ...")
with open("/app/sql/cleanup.sql", "r", encoding="utf-8") as f:
    tmpl = f.read()
sql = tmpl.format(schema=SCHEMA, staging=STAGING_TABLE, cleaned=CLEAN_TABLE)
cur.execute(sql)
print("Clean-tabel aangemaakt.")

# optioneel: post-load optimalisaties
post_load = "/app/sql/post_load.sql"
if os.path.exists(post_load):
    with open(post_load, "r", encoding="utf-8") as f:
        tmpl2 = f.read()
    sql2 = tmpl2.format(schema=SCHEMA, cleaned=CLEAN_TABLE)
    cur.execute(sql2)
    print("Indexen/ANALYZE uitgevoerd.")

cur.close(); conn.close()

# ---------- 5) Registratie in Superset ----------
try:
    s = superset_session()
    register_dataset_in_superset(s)
except Exception as e:
    print(f"Superset-registratie overgeslagen/fout: {e}")

# ---------- 6) Marquez registratie (optioneel) ----------
try:
    marquez_register(RAW_KEY, SCHEMA, CLEAN_TABLE)
except Exception as e:
    print(f"Marquez-registratie overgeslagen/fout: {e}")

print("ETL pipeline voltooid.")