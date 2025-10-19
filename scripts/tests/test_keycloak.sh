#!/bin/bash

# Test OAuth token endpoint
echo "Testing OAuth token endpoint..."
echo ""

TOKEN_RESPONSE=$(curl -s -X POST \
  "http://localhost:8085/realms/data-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=data-platform-api" \
  -d "client_secret=api_client_secret_2025" \
  -d "grant_type=password" \
  -d "username=john.engineer" \
  -d "password=Engineer2025!")

echo "Response:"
echo "$TOKEN_RESPONSE" | jq '.'

echo ""
echo "Access Token (decoded):"
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
  echo "✅ Token retrieved successfully!"
  echo ""
  echo "JWT Payload:"
  # Add padding for base64 decode
  PAYLOAD=$(echo "$ACCESS_TOKEN" | cut -d'.' -f2)
  # Add padding if needed
  MOD=$((${#PAYLOAD} % 4))
  if [ $MOD -eq 2 ]; then
    PAYLOAD="${PAYLOAD}=="
  elif [ $MOD -eq 3 ]; then
    PAYLOAD="${PAYLOAD}="
  fi
  echo "$PAYLOAD" | base64 -d 2>/dev/null | jq '.'
else
  echo "❌ Failed to retrieve token"
fi
