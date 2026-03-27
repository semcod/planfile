#!/bin/bash

# Multi-Integration Example
# Demonstrates planfile with GitHub, GitLab, and Jira integrations

set -e

echo "🚀 Multi-Integration Example"
echo "============================"
echo "GitHub  ← Automated tool tasks"
echo "GitLab  ← CI/CD & infrastructure"
echo "Jira    ← Human-facing tasks"
echo ""

# Check if we're in the right directory
if [ ! -f "tickets.planfile.yaml" ]; then
    echo "❌ Error: tickets.planfile.yaml not found. Run from examples/multi-ticket/"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copy .env.example to .env:"
    echo "   cp .env.example .env"
    echo "   Then edit .env with your credentials"
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
echo "Integration configs: github.planfile.yaml, gitlab.planfile.yaml, jira.planfile.yaml"
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
"

# Count tickets by integration
echo ""
echo "🎫 Ticket Distribution:"
echo "----------------------"
python3 -c "
import yaml
with open('tickets.planfile.yaml') as f:
    config = yaml.safe_load(f)
    
    # Count sprint tickets
    sprint_counts = {'jira': 0, 'github': 0, 'gitlab': 0}
    backlog_counts = {'jira': 0, 'github': 0, 'gitlab': 0}
    
    for ticket in config['sprint']['tickets'].values():
        integration = ticket.get('integration', 'github')
        if isinstance(integration, list):
            for i in integration:
                sprint_counts[i] = sprint_counts.get(i, 0) + 1
        else:
            sprint_counts[integration] = sprint_counts.get(integration, 0) + 1
    
    for ticket in config['backlog']['tickets'].values():
        integration = ticket.get('integration', 'github')
        if isinstance(integration, list):
            for i in integration:
                backlog_counts[i] = backlog_counts.get(i, 0) + 1
        else:
            backlog_counts[integration] = backlog_counts.get(integration, 0) + 1
    
    print('Sprint tickets:')
    print(f'  Jira (human tasks):     {sprint_counts[\"jira\"]} tickets')
    print(f'  GitHub (automation):    {sprint_counts[\"github\"]} tickets')
    print(f'  GitLab (CI/CD):         {sprint_counts[\"gitlab\"]} tickets')
    print('')
    print('Backlog tickets:')
    print(f'  Jira (human tasks):     {backlog_counts[\"jira\"]} tickets')
    print(f'  GitHub (automation):    {backlog_counts[\"github\"]} tickets')
    print(f'  GitLab (CI/CD):         {backlog_counts[\"gitlab\"]} tickets')
"

# Show integration status
echo ""
echo "🔗 Integration Status:"
echo "---------------------"
python3 -c "
import os
integrations = {
    'GitHub': 'GITHUB_TOKEN' in os.environ,
    'GitLab': 'GITLAB_TOKEN' in os.environ,
    'Jira': 'JIRA_EMAIL' in os.environ and 'JIRA_TOKEN' in os.environ
}

for name, configured in integrations.items():
    status = '✅ Configured' if configured else '❌ Not configured'
    print(f'{name:10} {status}')
"

# Show sample tickets
echo ""
echo "📝 Sample Tickets by Integration:"
echo "---------------------------------"
python3 -c "
import yaml
with open('tickets.planfile.yaml') as f:
    config = yaml.safe_load(f)
    
    examples = {
        'jira': [],
        'github': [],
        'gitlab': []
    }
    
    for ticket_id, ticket in config['sprint']['tickets'].items():
        integration = ticket.get('integration', 'github')
        if isinstance(integration, list):
            integration = integration[0]  # Take first for example
        
        if len(examples[integration]) < 2:
            examples[integration].append((ticket_id, ticket['title'], ticket.get('labels', [])))
    
    for integration, tickets in examples.items():
        print(f'{integration.upper()}:')
        for ticket_id, title, labels in tickets:
            print(f'  {ticket_id}: {title}')
            if labels:
                print(f'         Labels: {\", \".join(labels[:3])}{'...' if len(labels) > 3 else ''}')
        print()
"

# Instructions
echo "💡 How it works:"
echo "----------------"
echo "• Tickets with 'integration: jira' sync to Jira (human tasks)"
echo "• Tickets with 'integration: github' sync to GitHub (automation)"
echo "• Tickets with 'integration: gitlab' sync to GitLab (CI/CD)"
echo "• Tickets can have multiple integrations: integration: [jira, github]"
echo ""
echo "📝 To Use This Example:"
echo "-----------------------"
echo "1. Copy .env.example to .env"
echo "2. Add credentials for the integrations you want to use"
echo "3. Update repository/project IDs in the integration configs"
echo "4. Run sync for specific integration:"
echo "   planfile sync jira     # Sync human tasks"
echo "   planfile sync github   # Sync automation tasks"
echo "   planfile sync gitlab   # Sync CI/CD tasks"
echo "5. Or sync all at once:"
echo "   planfile sync --all"
