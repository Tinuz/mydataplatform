#!/bin/bash

# Script om een veilige TOKEN_SECRET te genereren voor Konga
# Gebruik: ./generate-token-secret.sh

echo "🔐 Generating secure TOKEN_SECRET for Konga..."
echo ""

TOKEN=$(openssl rand -base64 32)

echo "Generated token:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$TOKEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Update docker-compose.yml:"
echo ""
echo "  konga:"
echo "    environment:"
echo "      TOKEN_SECRET: \"$TOKEN\""
echo ""
echo "⚠️  BELANGRIJK: Wijzig dit in productie en bewaar het veilig!"
