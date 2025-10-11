#!/bin/bash
set -e

echo "🚀 Kong + Konga Setup Script voor Apple Silicon"
echo "================================================"
echo ""

# Kleuren voor output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stap 1: Start postgres_konga en kong
echo -e "${BLUE}📦 Stap 1: Start postgres_konga en kong...${NC}"
docker-compose --profile standard up -d postgres_konga kong

# Stap 2: Wacht tot postgres_konga healthy is
echo -e "${BLUE}⏳ Stap 2: Wacht tot postgres_konga healthy is...${NC}"
for i in {1..30}; do
    if docker-compose ps postgres_konga | grep -q "healthy"; then
        echo -e "${GREEN}✅ postgres_konga is healthy!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Stap 3: Controleer of Konga database al is geïnitialiseerd
echo -e "${BLUE}🔍 Stap 3: Controleer database status...${NC}"
TABLE_COUNT=$(docker-compose exec -T postgres_konga psql -U konga -d konga -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'konga_%';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -ge "10" ]; then
    echo -e "${GREEN}✅ Konga database is al geïnitialiseerd (${TABLE_COUNT} tabellen gevonden)${NC}"
else
    echo -e "${YELLOW}⚠️  Konga database moet worden geïnitialiseerd...${NC}"
    
    # Stap 4: Initialiseer Konga database
    echo -e "${BLUE}🔧 Stap 4: Initialiseer Konga database...${NC}"
    docker-compose run --rm konga -c prepare -a postgres -u postgresql://konga:konga@postgres_konga:5432/konga
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database succesvol geïnitialiseerd!${NC}"
    else
        echo -e "${YELLOW}⚠️  Database initialisatie gefaald, maar we proberen verder...${NC}"
    fi
fi

# Stap 5: Start Konga
echo -e "${BLUE}🚀 Stap 5: Start Konga...${NC}"
docker-compose up -d konga

# Stap 6: Wacht tot Konga beschikbaar is
echo -e "${BLUE}⏳ Stap 6: Wacht tot Konga beschikbaar is...${NC}"
sleep 5

for i in {1..20}; do
    if curl -s http://localhost:1337 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Konga is beschikbaar!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Stap 7: Status check
echo ""
echo -e "${BLUE}📊 Status overzicht:${NC}"
echo "===================="
docker-compose ps | grep -E "(kong|konga)" | grep -E "Up|healthy"

echo ""
echo -e "${GREEN}✅ Setup compleet!${NC}"
echo ""
echo "🌐 Services:"
echo "   - Kong Proxy:    http://localhost:8000"
echo "   - Kong Admin:    http://localhost:8001"
echo "   - Konga UI:      http://localhost:1337"
echo ""
echo "📝 Volgende stappen:"
echo "   1. Open http://localhost:1337"
echo "   2. Registreer een admin account"
echo "   3. Voeg Kong connectie toe: http://kong:8001"
echo ""
echo "📚 Meer info: zie kong/README.md en kong/APPLE_SILICON_FIX.md"
