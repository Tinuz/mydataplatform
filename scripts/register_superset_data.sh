#!/bin/bash
# Script om PostgreSQL database en dataset te registreren in Superset

SUPERSET_URL="http://localhost:8088"
USERNAME="admin"
PASSWORD="admin"

echo "🔐 Logging in to Superset..."

# 1. Login en krijg access token
LOGIN_RESPONSE=$(curl -s -X POST "${SUPERSET_URL}/api/v1/security/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"provider\":\"db\",\"refresh\":true}")

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Login failed!"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Logged in successfully"

# 2. Get CSRF token
CSRF_RESPONSE=$(curl -s -X GET "${SUPERSET_URL}/api/v1/security/csrf_token/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json")

CSRF_TOKEN=$(echo "$CSRF_RESPONSE" | grep -o '"result":"[^"]*' | cut -d'"' -f4)

if [ -z "$CSRF_TOKEN" ]; then
  echo "❌ Failed to get CSRF token!"
  echo "$CSRF_RESPONSE"
  exit 1
fi

echo "✅ Got CSRF token"

# 3. Check bestaande databases
echo ""
echo "📊 Checking for existing PostgreSQL database..."
DB_LIST=$(curl -s -X GET "${SUPERSET_URL}/api/v1/database/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json")

# Check of "Postgres" al bestaat (simpele grep check)
if echo "$DB_LIST" | grep -q '"database_name":"Postgres"'; then
  echo "✅ PostgreSQL database already exists"
  DB_ID=$(echo "$DB_LIST" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
else
  # 4. Maak PostgreSQL database aan
  echo "📝 Creating PostgreSQL database connection..."
  
  DB_RESPONSE=$(curl -s -X POST "${SUPERSET_URL}/api/v1/database/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-CSRFToken: ${CSRF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
      "database_name": "Postgres",
      "sqlalchemy_uri": "postgresql+psycopg2://superset:superset@postgres:5432/superset",
      "expose_in_sqllab": true,
      "allow_csv_upload": true,
      "allow_run_async": false,
      "allow_ctas": false,
      "allow_cvas": false,
      "impersonate_user": false,
      "extra": "{}"
    }')
  
  if echo "$DB_RESPONSE" | grep -q '"id"'; then
    DB_ID=$(echo "$DB_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    echo "✅ PostgreSQL database created (ID: ${DB_ID})"
  else
    echo "❌ Failed to create database!"
    echo "$DB_RESPONSE"
    exit 1
  fi
fi

# 5. Get user ID
ME_RESPONSE=$(curl -s -X GET "${SUPERSET_URL}/api/v1/me/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json")

USER_ID=$(echo "$ME_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

# 6. Check bestaande datasets
echo ""
echo "📋 Checking for cell_towers.clean_204 dataset..."

FILTER='{"filters":[{"col":"table_name","opr":"eq","value":"clean_204"},{"col":"schema","opr":"eq","value":"cell_towers"}]}'
DATASET_LIST=$(curl -s -X GET "${SUPERSET_URL}/api/v1/dataset/?q=$(echo "$FILTER" | jq -sRr @uri)" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json")

if echo "$DATASET_LIST" | grep -q '"count":[1-9]'; then
  echo "✅ Dataset cell_towers.clean_204 already exists"
  DATASET_ID=$(echo "$DATASET_LIST" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
else
  # 7. Maak dataset aan
  echo "📝 Creating cell_towers.clean_204 dataset..."
  
  DATASET_RESPONSE=$(curl -s -X POST "${SUPERSET_URL}/api/v1/dataset/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-CSRFToken: ${CSRF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
      \"database\": ${DB_ID},
      \"schema\": \"cell_towers\",
      \"table_name\": \"clean_204\",
      \"owners\": [${USER_ID}]
    }")
  
  if echo "$DATASET_RESPONSE" | grep -q '"id"'; then
    DATASET_ID=$(echo "$DATASET_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    echo "✅ Dataset created (ID: ${DATASET_ID})"
  else
    echo "❌ Failed to create dataset!"
    echo "$DATASET_RESPONSE"
    exit 1
  fi
fi

echo ""
echo "============================================================"
echo "🎉 SUCCESS!"
echo "============================================================"
echo ""
echo "✅ PostgreSQL database: ID ${DB_ID}"
echo "✅ Dataset cell_towers.clean_204: ID ${DATASET_ID}"
echo ""
echo "🌐 Open Superset: ${SUPERSET_URL}"
echo "📊 Go to: Data → Datasets → cell_towers.clean_204"
echo "🎨 Click 'Create Chart' to start visualizing!"
echo ""
echo "💡 Example query in SQL Lab:"
echo "   SELECT radio, COUNT(*) FROM cell_towers.clean_204 GROUP BY radio;"
echo ""
echo "📈 Suggested visualizations:"
echo "   - Big Number: COUNT(*) total towers"
echo "   - Pie Chart: Distribution by radio type"
echo "   - Scatter Plot: Geographic map (lat, lon)"
echo "   - Bar Chart: Top countries by MCC"
