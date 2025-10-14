#!/bin/bash
# Health Check Script for Data Platform
# Quickly validates all services and data

# Don't exit on error - we want to continue checking
set +e

echo "🏥 Data Platform Health Check"
echo "=============================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

check_service() {
    local service=$1
    local container=$2
    
    if docker-compose ps | grep -q "$container.*Up"; then
        echo -e "${GREEN}✅ $service: Running${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $service: Not running${NC}"
        ((FAILED++))
    fi
}

check_data() {
    local description=$1
    local command=$2
    
    result=$(eval "$command" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$result" ]; then
        echo -e "${GREEN}✅ $description: $result${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $description: Failed or empty${NC}"
        ((FAILED++))
    fi
}

echo "📦 Checking Services..."
echo "----------------------"
check_service "PostgreSQL" "postgres"
check_service "Superset" "superset"
check_service "Dagster" "dagster"
check_service "MinIO" "minio"
check_service "Marquez" "marquez"
check_service "Kong" "kong"
check_service "Konga" "konga"

# Check Kafka (if streaming profile)
if docker-compose ps | grep -q "kafka.*Up"; then
    check_service "Kafka" "kafka"
    check_service "Iceberg REST" "iceberg-rest"
fi

# Check Amundsen (if amundsen profile)
if docker-compose ps | grep -q "amundsen.*Up"; then
    check_service "Amundsen Neo4j" "amundsen-neo4j"
    check_service "Amundsen Search" "amundsen-search"
    check_service "Amundsen Metadata" "amundsen-metadata"
fi

echo ""
echo "📊 Checking Data..."
echo "-------------------"

# Check PostgreSQL data
check_data "Cell Towers" "docker-compose exec -T postgres psql -U superset -d superset -tAc 'SELECT COUNT(*) || \" rows\" FROM cell_towers.clean_204' 2>/dev/null"

check_data "Crypto Bronze" "docker-compose exec -T postgres psql -U superset -d superset -tAc 'SELECT COUNT(*) || \" rows\" FROM crypto.trades_bronze' 2>/dev/null"

check_data "Crypto Silver" "docker-compose exec -T postgres psql -U superset -d superset -tAc 'SELECT COUNT(*) || \" rows\" FROM crypto.trades_1min' 2>/dev/null"

echo ""
echo "🔌 Checking Endpoints..."
echo "-------------------------"

# Check HTTP endpoints
check_endpoint() {
    local name=$1
    local url=$2
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|302\|401"; then
        echo -e "${GREEN}✅ $name: Accessible${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $name: Not accessible${NC}"
        ((FAILED++))
    fi
}

check_endpoint "Superset UI" "http://localhost:8088/health"
check_endpoint "Dagster UI" "http://localhost:3000/server_info"
check_endpoint "MinIO API" "http://localhost:9000/minio/health/live"

# Check Kafka (if streaming profile)
if docker-compose ps | grep -q "kafka.*Up"; then
    echo ""
    echo "📨 Checking Kafka..."
    echo "--------------------"
    
    topics=$(docker-compose exec -T kafka kafka-topics.sh --bootstrap-server localhost:9092 --list 2>/dev/null | wc -l)
    if [ "$topics" -gt 0 ]; then
        echo -e "${GREEN}✅ Kafka Topics: $topics topics${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  Kafka Topics: No topics found${NC}"
    fi
fi

echo ""
echo "📦 Checking MinIO Buckets..."
echo "-----------------------------"

buckets=$(docker-compose exec -T dagster python3 -c "
from minio import Minio
try:
    client = Minio('minio:9000', access_key='minio', secret_key='minio12345', secure=False)
    buckets = client.list_buckets()
    print(len(buckets))
except:
    print(0)
" 2>/dev/null)

if [ "$buckets" -gt 0 ]; then
    echo -e "${GREEN}✅ MinIO Buckets: $buckets buckets${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ MinIO Buckets: No buckets found${NC}"
    ((FAILED++))
fi

echo ""
echo "🎯 Health Check Summary"
echo "======================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! Platform is healthy.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some checks failed. Review issues above.${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "  1. Run: docker-compose ps"
    echo "  2. Check logs: docker-compose logs -f <service>"
    echo "  3. Restart services: docker-compose restart"
    echo "  4. Re-initialize: ./scripts/bootstrap.sh"
    exit 1
fi
