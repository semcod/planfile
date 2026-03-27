#!/bin/bash

# GitHub Integration Example
# Demonstrates planfile with separate integration and ticket configs

set -e

echo "🚀 GitHub Integration Example"
echo "============================="

# Check if we're in the right directory
if [ ! -f "tickets.planfile.yaml" ]; then
    echo "❌ Error: tickets.planfile.yaml not found. Run from examples/github/"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copy .env.example to .env:"
    echo "   cp .env.example .env"
    echo "   Then edit .env with your GitHub token"
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
echo "Integration config: github.planfile.yaml"
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
    print(f'Tickets: {len(sprint[\"tickets\"])} in sprint')
    if 'backlog' in config and 'tickets' in config['backlog']:
        print(f', {len(config[\"backlog\"][\"tickets\"])} in backlog')
    else:
        print(', 0 in backlog')
"

# Show integration config
echo ""
echo "🔗 Integration Config:"
echo "---------------------"
python3 -c "
import yaml
import os
with open('github.planfile.yaml') as f:
    config = yaml.safe_load(f)
    github = config['integrations']['github']
    sync = github['sync']
    
    print(f'Repository: {github[\"repo\"]}')
    print(f'Token: {\"✅ Set\" if \"GITHUB_TOKEN\" in os.environ else \"❌ Not set\"}')
    print(f'Sync settings:')
    for key, value in sync.items():
        print(f'  {key}: {value}')
" 2>/dev/null || echo "Install python3-yaml to see detailed config"

# Instructions
echo ""
echo "📝 To Use This Example:"
echo "-----------------------"
echo "1. Copy .env.example to .env"
echo "2. Add your GitHub token to .env"
echo "3. Update repository in github.planfile.yaml"
echo "4. Install dependencies:"
echo "   pip install PyGithub"
echo "5. Run sync with:"
echo "   planfile sync github --dry-run  # Test without making changes"
echo "   planfile sync github             # Actual sync"
echo ""
echo "📖 See README.md for more details"
