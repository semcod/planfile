# GitHub Integration Example

This example demonstrates how to integrate planfile with GitHub Issues for bidirectional synchronization.

## Overview

The GitHub integration allows you to:
- Sync planfile tickets to GitHub Issues
- Import GitHub Issues back into planfile
- Maintain status and priority mapping through labels
- Use GitHub as the issue tracking interface while managing sprints in planfile

## Files in this Example

- `planfile.yaml` - Configuration file with GitHub integration settings and sample tickets
- `run.sh` - Test script that demonstrates the integration
- `mock_api_responses.py` - Mock API responses for offline testing
- `README.md` - This documentation file

## Prerequisites

1. **Install planfile** (if not already installed):
   ```bash
   pip install -e .
   ```

2. **Install PyGithub** (required for GitHub integration):
   ```bash
   pip install PyGithub
   ```

3. **Create a GitHub Personal Access Token**:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate a new token with the `repo` scope
   - Save the token securely

## Setup

1. **Set the GitHub token as an environment variable**:
   ```bash
   export GITHUB_TOKEN=ghp_your_personal_access_token
   ```

2. **Update the repository in planfile.yaml**:
   ```yaml
   integrations:
     github:
       repo: "yourorg/yourrepo"  # Change this to your repository
   ```

3. **Ensure you have write access to the target repository**.

## Running the Example

### Quick Test (Mock Mode)

Run the test script without a real GitHub token to see how it works:
```bash
./run.sh
```

This will:
- Load and validate the planfile.yaml
- Test the GitHub backend initialization
- Show mock API responses
- Demonstrate the expected sync workflow

### Real Integration Test

With a valid GitHub token and repository:
```bash
./run.sh
```

Then run the actual sync:
```bash
planfile sync github --from planfile.yaml
```

## Configuration Options

### GitHub Integration Settings

```yaml
integrations:
  github:
    repo: "owner/repository"        # Required: GitHub repository
    token: "${GITHUB_TOKEN}"        # Optional: defaults to GITHUB_TOKEN env var
    
    sync:
      create_issues: true           # Create GitHub issues from planfile tickets
      import_issues: true           # Import GitHub issues into planfile
      
      default_labels:               # Labels added to all created issues
        - "planfile"
        - "managed"
      
      priority_labels:              # Map planfile priorities to GitHub labels
        critical: "priority/critical"
        high: "priority/high"
        normal: "priority/normal"
        low: "priority/low"
      
      status_labels:                # Map planfile statuses to GitHub labels
        open: null                  # null = no label
        in_progress: "status/in-progress"
        review: "status/review"
        done: "status/done"
        blocked: "status/blocked"
```

## How It Works

### Sync Direction: planfile → GitHub

1. Reads tickets from the current sprint and backlog
2. Creates or updates GitHub Issues
3. Applies labels based on priority and status
4. Stores GitHub issue number in ticket metadata

### Sync Direction: GitHub → planfile

1. Fetches issues from the repository
2. Creates planfile tickets for issues without corresponding tickets
3. Updates status based on issue state and labels
4. Preserves GitHub issue number for mapping

### Bidirectional Sync

- Uses GitHub issue number to track relationships
- Updates in either direction are synchronized
- Conflicts are resolved with the most recent change

## Common Use Cases

### 1. GitHub as Primary Issue Tracker
- Team members work in GitHub Issues
- Planfile manages sprint planning and progress tracking
- Regular sync keeps both systems aligned

### 2. Planfile as Primary Manager
- Create tickets in planfile during sprint planning
- Sync to GitHub for developers to work on
- Import progress updates back to planfile

### 3. Hybrid Approach
- Use planfile for internal tickets
- Use GitHub for external/customer-facing issues
- Selective sync based on labels or criteria

## Troubleshooting

### Common Issues

1. **"PyGithub is required" error**
   ```bash
   pip install PyGithub
   ```

2. **"GitHub token is required" error**
   ```bash
   export GITHUB_TOKEN=your_token
   ```

3. **"Repository not found" error**
   - Check the repository format: "owner/repo"
   - Ensure the token has access to the repository
   - Verify the repository exists

4. **Permission denied**
   - Ensure the token has the `repo` scope
   - Check that you have write access to the repository

### Debug Mode

Enable debug logging to see detailed API calls:
```bash
export PLANFILE_DEBUG=1
planfile sync github --from planfile.yaml
```

## Best Practices

1. **Use a test repository** when first setting up the integration
2. **Back up your planfile.yaml** before running large syncs
3. **Use labels consistently** to maintain proper status mapping
4. **Review sync logs** to catch any issues early
5. **Set up webhook notifications** for real-time updates (future feature)

## Advanced Features

### Custom Label Mapping

You can customize the label mapping to match your team's workflow:
```yaml
integrations:
  github:
    sync:
      priority_labels:
        critical: "urgent"
        high: "high-priority"
        normal: "normal-priority"
        low: "low-priority"
```

### Selective Sync

Sync only specific tickets based on labels:
```yaml
integrations:
  github:
    sync:
      only_with_labels: ["github-sync"]
      exclude_labels: ["internal-only"]
```

### Milestone Support (Future)

The integration will support GitHub milestones in a future version:
- Sync planfile sprints to GitHub milestones
- Track progress in both systems
- Automatic milestone creation

## Contributing

To contribute to the GitHub integration:
1. Check the source code in `planfile/integrations/github.py`
2. Run tests with `python -m pytest tests/`
3. Submit pull requests with your improvements

## Support

For issues or questions:
- Check the planfile documentation
- Open an issue on the planfile repository
- Join the planfile community discussions
