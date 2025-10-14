#!/bin/bash

# Script to clean up all remaining Trino references in documentation

set -e

echo "🧹 Cleaning up Trino references from documentation..."
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FILES_TO_REMOVE=(
    "docs/CRYPTO_STREAM_QUICKSTART.md"
    "docs/CRYPTO_STREAM_ARCHITECTURE.md"
)

FILES_TO_UPDATE=(
    "docs/SUPERSET_DATABASE_CONNECTIONS.md"
    "docs/SUPERSET_QUICK_REFERENCE.md"
    "docs/README.md"
    "docs/QUICK_REFERENCE.md"
    "scripts/README.md"
    "orchestration/README.md"
    "orchestration/crypto_stream/README.md"
    "datahub/README.md"
    "amundsen/DEMO_SCRIPT.md"
)

# Remove large Trino-focused documentation
echo -e "${YELLOW}📁 Removing Trino-focused documentation...${NC}"
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "   ❌ Removing: $file"
        rm "$file"
    fi
done
echo ""

# Count remaining Trino references
echo -e "${YELLOW}🔍 Scanning for remaining Trino references...${NC}"
echo ""

TOTAL_MATCHES=0
for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        COUNT=$(grep -i "trino" "$file" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$COUNT" -gt 0 ]; then
            echo "   📄 $file: $COUNT references"
            TOTAL_MATCHES=$((TOTAL_MATCHES + COUNT))
        fi
    fi
done

echo ""
echo -e "${GREEN}✅ Removed ${#FILES_TO_REMOVE[@]} Trino-focused docs${NC}"
echo -e "${YELLOW}⚠️  Found $TOTAL_MATCHES Trino references in ${#FILES_TO_UPDATE[@]} remaining files${NC}"
echo ""
echo "📝 Manual review needed for:"
for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        COUNT=$(grep -i "trino" "$file" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$COUNT" -gt 0 ]; then
            echo "   - $file"
        fi
    fi
done
echo ""
echo "💡 Recommendation: These files mention Trino but may still be useful."
echo "   Review each file and either:"
echo "   1. Remove the Trino sections"
echo "   2. Replace with DuckDB/PostgreSQL alternatives"
echo "   3. Add a note that Trino has been removed"
