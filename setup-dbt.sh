#!/bin/bash
# Setup script for dbt integration in Docker
# Run this script AFTER docker-compose up to initialize dbt

set -e

echo "🚀 dbt + Dagster Integration Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if Dagster container is running
if ! docker ps | grep -q dp_dagster; then
    echo -e "${YELLOW}⚠️  Dagster container is not running.${NC}"
    echo "Starting containers with docker-compose..."
    docker-compose --profile standard up -d
    echo "Waiting for containers to be healthy..."
    sleep 10
fi

echo -e "${GREEN}✓${NC} Docker containers are running"
echo ""

# Step 1: Install dbt dependencies
echo "📦 Step 1: Installing dbt packages..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt deps"
echo -e "${GREEN}✓${NC} dbt packages installed"
echo ""

# Step 2: Test database connection
echo "🔌 Step 2: Testing database connection..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt debug"
echo -e "${GREEN}✓${NC} Database connection successful"
echo ""

# Step 3: Create canonical schema if not exists
echo "🗄️  Step 3: Creating canonical schema..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt run-operation create_canonical_schema"
echo -e "${GREEN}✓${NC} Canonical schema ready"
echo ""

# Step 4: Parse dbt project and generate manifest
echo "📋 Step 4: Parsing dbt project..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt parse"
echo -e "${GREEN}✓${NC} Manifest generated at target/manifest.json"
echo ""

# Step 5: Compile all models (dry-run)
echo "🔨 Step 5: Compiling dbt models..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt compile"
echo -e "${GREEN}✓${NC} All models compiled successfully"
echo ""

# Step 6: Run dbt tests (will mostly fail since no data yet)
echo "🧪 Step 6: Running dbt tests (baseline)..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt test --select source:* || true"
echo -e "${YELLOW}⚠️  Source tests may fail if no data uploaded yet${NC}"
echo ""

# Step 7: Generate documentation
echo "📚 Step 7: Generating dbt documentation..."
docker exec dp_dagster bash -c "cd /opt/dagster/dbt_investigations && dbt docs generate"
echo -e "${GREEN}✓${NC} Documentation generated"
echo ""

# Step 8: Restart Dagster daemon to load new assets
echo "🔄 Step 8: Reloading Dagster assets..."
docker restart dp_dagster
echo "Waiting for Dagster to restart..."
sleep 5
echo -e "${GREEN}✓${NC} Dagster restarted with dbt assets"
echo ""

echo "=================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "📍 Next Steps:"
echo "   1. Open Dagster UI: http://localhost:3000"
echo "   2. Navigate to Assets → investigations"
echo "   3. You should see new dbt assets:"
echo "      • dbt_staging_models"
echo "      • dbt_canonical_models"
echo "      • dbt_test_canonical"
echo "      • dbt_docs_generate"
echo ""
echo "🧪 To test the full pipeline:"
echo "   1. Upload SNS Bank test file via Investigation UI"
echo "   2. Watch Dagster run the pipeline:"
echo "      file_upload_sensor → process_bank_transactions → dbt_staging_models → dbt_canonical_models"
echo ""
echo "📊 To view dbt documentation:"
echo "   docker exec dp_dagster bash -c 'cd /opt/dagster/dbt_investigations && dbt docs serve --port 8081'"
echo "   Then open: http://localhost:8081"
echo ""
echo "🔍 To check canonical data:"
echo "   docker exec -it dp_postgres psql -U superset -d superset -c 'SELECT COUNT(*) FROM canonical.dim_bank_account;'"
echo ""
