#!/bin/bash
set -e

echo "🚀 Trino Setup Script"
echo "====================="
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check of MinIO en Postgres draaien
echo -e "${BLUE}📦 Stap 1: Check dependencies...${NC}"

if ! docker-compose ps postgres | grep -q "healthy"; then
    echo -e "${YELLOW}⚠️  PostgreSQL is niet healthy, start eerst postgres${NC}"
    docker-compose --profile standard up -d postgres
    echo "Wacht op postgres..."
    sleep 10
fi

if ! docker-compose ps minio | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  MinIO is niet gestart, start MinIO${NC}"
    docker-compose --profile standard up -d minio
    echo "Wacht op MinIO..."
    sleep 5
fi

echo -e "${GREEN}✅ Dependencies zijn ready${NC}"
echo ""

# Start Trino
echo -e "${BLUE}🚀 Stap 2: Start Trino...${NC}"
docker-compose --profile standard up -d trino

# Wacht tot Trino healthy is
echo -e "${BLUE}⏳ Stap 3: Wacht tot Trino gereed is (kan 60 seconden duren)...${NC}"
echo "Trino heeft tijd nodig om op te starten..."

for i in {1..60}; do
    if docker-compose exec -T trino curl -sf http://localhost:8080/v1/info > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✅ Trino is gereed!${NC}"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Test queries
echo ""
echo -e "${BLUE}🧪 Stap 4: Test Trino connectie...${NC}"

# Test catalogs
echo "Testing catalogs..."
CATALOGS=$(docker-compose exec -T trino trino --execute "SHOW CATALOGS" 2>/dev/null | grep -E "(postgresql|minio|tpch)" | wc -l)

if [ "$CATALOGS" -ge "3" ]; then
    echo -e "${GREEN}✅ Alle catalogs zijn beschikbaar${NC}"
    docker-compose exec -T trino trino --execute "SHOW CATALOGS" 2>/dev/null | head -10
else
    echo -e "${YELLOW}⚠️  Niet alle catalogs zijn beschikbaar, check logs${NC}"
fi

echo ""
echo -e "${GREEN}✅ Setup compleet!${NC}"
echo ""
echo "🌐 Trino Web UI: http://localhost:8080"
echo ""
echo "📝 Test queries:"
echo "   docker-compose exec trino trino"
echo ""
echo "   Probeer deze queries:"
echo "   - SHOW CATALOGS;"
echo "   - SHOW SCHEMAS FROM postgresql;"
echo "   - SELECT * FROM tpch.tiny.nation;"
echo ""
echo "📚 Meer info: zie trino/README.md"
