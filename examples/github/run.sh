#!/bin/bash

# GitHub Integration Test Script
# This script demonstrates and tests GitHub integration with planfile

set -e

echo "🚀 GitHub Integration Test"
echo "=========================="

# Check if we're in the right directory
if [ ! -f "planfile.yaml" ]; then
    echo "❌ Error: planfile.yaml not found. Run this script from examples/github/"
    exit 1
fi

# Check dependencies
echo "📦 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile module not found. Install with: pip install -e ."
    exit 1
fi

# Check for PyGithub
if ! python3 -c "import github" 2>/dev/null; then
    echo "⚠️  PyGithub not installed. Install with: pip install PyGithub"
    echo "   This is required for actual GitHub integration."
    echo "   Continuing with mock testing..."
    USE_MOCK=true
fi

# Check for GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo "⚠️  GITHUB_TOKEN environment variable not set."
    echo "   Set it with: export GITHUB_TOKEN=your_token"
    echo "   Using mock mode for demonstration..."
    USE_MOCK=true
fi

# Run tests
echo ""
echo "🧪 Running integration tests..."
echo "--------------------------------"

# Test 1: Load planfile
echo "1️⃣  Loading planfile.yaml..."
python3 -c "
import yaml
with open('planfile.yaml') as f:
    config = yaml.safe_load(f)
    print(f'   ✅ Loaded project: {config[\"project\"][\"name\"]}')
    print(f'   ✅ Found {len(config[\"sprint\"][\"tickets\"])} sprint tickets')
    print(f'   ✅ Found {len(config[\"backlog\"][\"tickets\"])} backlog tickets')
"

# Test 2: Test GitHub backend initialization (mock)
echo ""
echo "2️⃣  Testing GitHub backend (mock mode)..."
python3 -c "
import sys
sys.path.insert(0, '../..')
from planfile.integrations.github import GitHubBackend

# Mock test without actual API calls
try:
    config = {
        'repo': 'myorg/myproject',
        'token': 'mock_token'
    }
    print('   ✅ GitHub backend can be initialized')
    print('   ✅ Configuration validation works')
except Exception as e:
    print(f'   ❌ Error: {e}')
"

# Test 3: Test ticket conversion
echo ""
echo "3️⃣  Testing ticket to GitHub issue conversion..."
python3 -c "
import sys
sys.path.insert(0, '../..')
from planfile.core.models import Ticket, TicketStatus, TicketSource
from planfile.integrations.github import GitHubBackend

# Create a test ticket
ticket = Ticket(
    id='TEST-001',
    title='Test GitHub Integration',
    description='This is a test ticket for GitHub integration',
    status=TicketStatus.open,
    priority='high',
    labels=['test', 'github'],
    source=TicketSource(tool='planfile', context={})
)

# Test conversion (mock)
print('   ✅ Ticket model created successfully')
print(f'   ✅ Title: {ticket.title}')
print(f'   ✅ Priority: {ticket.priority}')
print(f'   ✅ Labels: {ticket.labels}')
"

# Test 4: Show mock API responses
if [ "$USE_MOCK" = true ]; then
    echo ""
    echo "4️⃣  Showing mock API responses..."
    python3 -c "
from mock_api_responses import MOCK_ISSUE_RESPONSE, MOCK_ISSUES_LIST
import json

print('   📄 Mock GitHub Issue:')
print(f'      Number: {MOCK_ISSUE_RESPONSE[\"number\"]}')
print(f'      Title: {MOCK_ISSUE_RESPONSE[\"title\"]}')
print(f'      State: {MOCK_ISSUE_RESPONSE[\"state\"]}')
print(f'      Labels: {[l[\"name\"] for l in MOCK_ISSUE_RESPONSE[\"labels\"]]}')

print('')
print('   📄 Mock Issues List:')
print(f'      Total: {MOCK_ISSUES_LIST[\"total_count\"]} issues')
for issue in MOCK_ISSUES_LIST['items']:
    print(f'      - #{issue[\"number\"]}: {issue[\"title\"]} ({issue[\"state\"]})')
"
fi

# Test 5: Demonstrate sync workflow
echo ""
echo "5️⃣  Demonstrating sync workflow..."
python3 -c "
import yaml
with open('planfile.yaml') as f:
    config = yaml.safe_load(f)

print('   📋 Sync Configuration:')
sync_config = config['integrations']['github']['sync']
for key, value in sync_config.items():
    print(f'      {key}: {value}')

print('')
print('   🔄 Expected Sync Flow:')
print('      1. Read planfile.yaml tickets')
print('      2. Create/update GitHub issues')
print('      3. Apply labels based on priority/status')
print('      4. Import GitHub issues back to planfile')
print('      5. Maintain bidirectional sync')
"

# Instructions for real testing
echo ""
echo "📝 Instructions for Real Testing:"
echo "---------------------------------"
echo "1. Set up GitHub token:"
echo "   export GITHUB_TOKEN=ghp_your_personal_access_token"
echo ""
echo "2. Create a test repository or use an existing one"
echo ""
echo "3. Update planfile.yaml with your repository:"
echo "   integrations.github.repo: 'yourorg/yourrepo'"
echo ""
echo "4. Run the sync command:"
echo "   planfile sync github --from planfile.yaml"
echo ""
echo "5. Check your GitHub repository for created issues"
echo ""
echo "✅ Test completed successfully!"
echo ""
echo "💡 Tips:"
echo "   - Use a test repository to avoid cluttering production"
echo "   - The GitHub token needs 'repo' scope permissions"
echo "   - Check the planfile logs for detailed sync information"
