#!/bin/bash

# GitLab Integration Example
# Demonstrates planfile with separate integration and ticket configs

set -e

echo "🚀 GitLab Integration Example"
echo "=============================="

# Check if we're in the right directory
if [ ! -f "tickets.planfile.yaml" ]; then
    echo "❌ Error: tickets.planfile.yaml not found. Run from examples/gitlab/"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copy .env.example to .env:"
    echo "   cp .env.example .env"
    echo "   Then edit .env with your GitLab token"
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
echo "Integration config: gitlab.planfile.yaml"
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
with open('gitlab.planfile.yaml') as f:
    config = yaml.safe_load(f)
    gitlab = config['integrations']['gitlab']
    sync = gitlab['sync']
    
    print(f'URL: {gitlab[\"url\"]}')
    print(f'Project ID: {gitlab[\"project_id\"]}')
    print(f'Token: {\"✅ Set\" if \"GITLAB_TOKEN\" in os.environ else \"❌ Not set\"}')
    print(f'Sync settings:')
    for key, value in sync.items():
        print(f'  {key}: {value}')
" 2>/dev/null || echo "Install python3-yaml to see detailed config"

# Instructions
echo ""
echo "📝 To Use This Example:"
echo "-----------------------"
echo "1. Copy .env.example to .env"
echo "2. Add your GitLab token to .env"
echo "3. Update project_id in gitlab.planfile.yaml"
echo "4. Install dependencies:"
echo "   pip install python-gitlab"
echo "5. Run sync with:"
echo "   planfile sync gitlab --dry-run  # Test without making changes"
echo "   planfile sync gitlab             # Actual sync"
echo ""
echo "📖 See README.md for more details"
