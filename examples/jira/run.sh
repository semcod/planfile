#!/bin/bash

# Jira Integration Example
# Demonstrates planfile with separate integration and ticket configs

set -e

echo "🚀 Jira Integration Example"
echo "============================"

# Check if we're in the right directory
if [ ! -f "tickets.planfile.yaml" ]; then
    echo "❌ Error: tickets.planfile.yaml not found. Run from examples/jira/"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copy .env.example to .env:"
    echo "   cp .env.example .env"
    echo "   Then edit .env with your Jira credentials"
    echo ""
    echo "Continuing with demo mode (no actual sync)..."
else
    # Load environment variables (skip comments)
    set -a
    source .env
    set +a
fi

# Show configuration
echo "📋 Configuration:"
echo "----------------"
echo "Integration config: jira.planfile.yaml"
echo "Tickets config: tickets.planfile.yaml"
echo "Environment: .env"

# Show project info
echo ""
echo "📊 Project Info:"
echo "---------------"
python3 -c "
import yaml
import os
with open('tickets.planfile.yaml') as f:
    config = yaml.safe_load(f)
    project = config['project']
    sprint = config['sprint']
    
    print(f'Name: {project[\"name\"]}')
    print(f'Prefix: {project[\"prefix\"]}')
    print(f'Sprint: {sprint[\"name\"]} ({sprint[\"status\"]})')
    print(f'Tickets: {len(sprint[\"tickets\"])} in sprint, {len(config[\"backlog\"][\"tickets\"])} in backlog')
"

# Show integration config
echo ""
echo "🔗 Integration Config:"
echo "---------------------"
python3 -c "
import yaml
import os
with open('jira.planfile.yaml') as f:
    config = yaml.safe_load(f)
    jira = config['integrations']['jira']
    sync = jira['sync']
    
    print(f'URL: {jira[\"url\"]}')
    print(f'Project: {jira[\"project\"]}')
    print(f'Email: {\"✅ Set\" if \"JIRA_EMAIL\" in os.environ else \"❌ Not set\"}')
    print(f'Token: {\"✅ Set\" if \"JIRA_TOKEN\" in os.environ else \"❌ Not set\"}')
    print(f'Issue Type: {sync[\"default_issue_type\"]}')
    print(f'Sync settings:')
    for key, value in sync.items():
        if key != 'default_issue_type':
            print(f'  {key}: {value}')
" 2>/dev/null || echo "Install python3-yaml to see detailed config"

# Instructions
echo ""
echo "📝 To Use This Example:"
echo "-----------------------"
echo "1. Copy .env.example to .env"
echo "2. Add your Jira credentials to .env"
echo "3. Update project and URL in jira.planfile.yaml"
echo "4. Install dependencies:"
echo "   pip install jira"
echo "5. Run sync with:"
echo "   planfile sync jira --dry-run  # Test without making changes"
echo "   planfile sync jira             # Actual sync"
echo ""
echo "📖 See README.md for more details"
