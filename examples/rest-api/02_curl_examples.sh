#!/bin/bash
# curl examples for planfile REST API

set -e

BASE_URL="${PLANFILE_URL:-http://localhost:8000}"

echo "=========================================="
echo "Planfile REST API - curl Examples"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}$1${NC}"
}

# 1. Health check
print_step "1. Health Check"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo

# 2. List all tickets
print_step "2. List All Tickets"
curl -s "$BASE_URL/tickets" | python3 -m json.tool
echo

# 3. Create a ticket
print_step "3. Create New Ticket"
TICKET_RESPONSE=$(curl -s -X POST "$BASE_URL/tickets" \
    -H "Content-Type: application/json" \
    -d '{
        "title": "API Test: Fix authentication bug",
        "description": "Users cannot login with OAuth provider",
        "priority": "high",
        "sprint": "current"
    }')
echo "$TICKET_RESPONSE" | python3 -m json.tool

# Extract ticket ID for later use
TICKET_ID=$(echo "$TICKET_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'TICKET-1'))")
echo "Created ticket ID: $TICKET_ID"
echo

# 4. Get specific ticket
print_step "4. Get Specific Ticket ($TICKET_ID)"
curl -s "$BASE_URL/tickets/$TICKET_ID" | python3 -m json.tool
echo

# 5. Update ticket
print_step "5. Update Ticket Status"
curl -s -X PATCH "$BASE_URL/tickets/$TICKET_ID" \
    -H "Content-Type: application/json" \
    -d '{"status": "in_progress", "priority": "critical"}' | python3 -m json.tool
echo

# 6. Create multiple tickets
print_step "6. Create Multiple Tickets"
for i in 1 2 3; do
    curl -s -X POST "$BASE_URL/tickets" \
        -H "Content-Type: application/json" \
        -d "{\"title\": \"Bulk Ticket $i\", \"priority\": \"medium\", \"sprint\": \"current\"}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Created: {d[\"id\"]}')"
done
echo

# 7. List with filters
print_step "7. Filter Tickets by Sprint"
curl -s "$BASE_URL/tickets?sprint=current" | python3 -c "
import sys, json
tickets = json.load(sys.stdin)
print(f'Tickets in current sprint: {len(tickets)}')
for t in tickets[:5]:
    print(f\"  {t['id']}: {t['title'][:40]}...\")
"
echo

# 8. Move ticket to sprint
print_step "8. Move Ticket to Different Sprint"
curl -s -X POST "$BASE_URL/tickets/$TICKET_ID/move?to_sprint=backlog" | python3 -m json.tool
echo

# 9. Delete ticket (commented out to preserve data)
# print_step "9. Delete Ticket"
# curl -s -X DELETE "$BASE_URL/tickets/$TICKET_ID"
# echo "Deleted ticket $TICKET_ID"

echo
echo "=========================================="
echo -e "${GREEN}All curl examples completed!${NC}"
echo "=========================================="
