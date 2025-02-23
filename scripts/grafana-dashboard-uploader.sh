#!/bin/bash

# Configuration
DASHBOARD_FILE="/Users/jwr003/coding/pytest-insight/pytest_insight/grafana/dashboards/dashboard_complete.json"
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. Please install it using:${NC}"
    echo "brew install jq"
    exit 1
fi

# Check if file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo -e "${RED}Error: Dashboard file not found at:${NC}"
    echo "$DASHBOARD_FILE"
    exit 1
fi

# Validate JSON
echo "Validating JSON..."
if ! jq empty "$DASHBOARD_FILE" 2>/dev/null; then
    echo -e "${RED}Error: Invalid JSON in dashboard file${NC}"
    exit 1
fi

# Upload dashboard
echo "Uploading dashboard..."
RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
    --data "@${DASHBOARD_FILE}" \
    "${GRAFANA_URL}/api/dashboards/db")

# Check response
if echo "$RESPONSE" | jq -e .uid > /dev/null 2>&1; then
    echo -e "${GREEN}Dashboard uploaded successfully!${NC}"
    echo "Dashboard UID: $(echo "$RESPONSE" | jq -r .uid)"
else
    echo -e "${RED}Failed to upload dashboard${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi
