#!/bin/bash

# Script para probar el webhook de WhatsApp localmente

echo "🧪 Testing WhatsApp Webhook Integration"
echo "========================================"
echo ""

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# URL base (cambiar según tu entorno)
BASE_URL="http://localhost:8000"

echo "📍 Using base URL: $BASE_URL"
echo ""

# Cargar variables de entorno desde .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep WHATSAPP_VERIFY_TOKEN | xargs)
fi

# Test 1: Verificación del webhook (GET)
echo "Test 1: Webhook Verification (GET)"
echo "-----------------------------------"
VERIFY_TOKEN="${WHATSAPP_VERIFY_TOKEN:-test_verify_token_123}"
CHALLENGE="test_challenge_string"

echo "Using verify token: ${VERIFY_TOKEN:0:10}..."

echo "Sending verification request..."
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=$VERIFY_TOKEN&hub.challenge=$CHALLENGE")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Webhook verification successful"
    echo "   Response: $BODY"
else
    echo -e "${RED}❌ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "   Response: $BODY"
fi
echo ""

# Test 2: Mensaje de WhatsApp simulado (POST)
echo "Test 2: Incoming WhatsApp Message (POST)"
echo "-----------------------------------------"

# Payload simulado de WhatsApp
WEBHOOK_PAYLOAD='{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "15550000000",
          "phone_number_id": "PHONE_NUMBER_ID"
        },
        "contacts": [{
          "profile": {
            "name": "Test User"
          },
          "wa_id": "5491234567890"
        }],
        "messages": [{
          "from": "5491234567890",
          "id": "wamid.test123",
          "timestamp": "1234567890",
          "text": {
            "body": "Hola, busco alojamiento en Valencia"
          },
          "type": "text"
        }]
      },
      "field": "messages"
    }]
  }]
}'

echo "Sending test message..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/whatsapp/webhook/" \
  -H "Content-Type: application/json" \
  -d "$WEBHOOK_PAYLOAD")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Message received successfully"
    echo "   Response: $BODY"
else
    echo -e "${RED}❌ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "   Response: $BODY"
fi
echo ""

# Test 3: Health Check
echo "Test 3: Health Check"
echo "--------------------"
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Health check successful"
    echo "   Response: $BODY"
else
    echo -e "${RED}❌ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "   Response: $BODY"
fi
echo ""

echo "========================================"
echo "✨ Testing complete!"
echo ""
echo -e "${YELLOW}Note:${NC} Test 2 will only fully work if you have:"
echo "  - WhatsApp credentials configured in .env"
echo "  - MongoDB connection active"
echo "  - LLM API key configured"
