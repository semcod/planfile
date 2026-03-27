"""Mock GitHub API responses for offline testing."""

# Mock GitHub issue response
MOCK_ISSUE_RESPONSE = {
    "id": 123456789,
    "number": 42,
    "title": "Set up GitHub integration",
    "body": """**Description:** Configure planfile to sync with GitHub Issues

**Priority:** high
**Labels:** setup, integration

---
*This issue is managed by planfile*""",
    "state": "open",
    "user": {
        "login": "planfile-bot",
        "id": 987654321
    },
    "assignees": [],
    "labels": [
        {"name": "planfile"},
        {"name": "managed"},
        {"name": "priority/high"},
        {"name": "setup"},
        {"name": "integration"}
    ],
    "created_at": "2026-03-27T10:00:00Z",
    "updated_at": "2026-03-27T10:00:00Z",
    "closed_at": None,
    "pull_request": None,
    "milestone": None,
    "html_url": "https://github.com/myorg/myproject/issues/42",
    "url": "https://api.github.com/repos/myorg/myproject/issues/42"
}

# Mock GitHub issues list response
MOCK_ISSUES_LIST = {
    "total_count": 3,
    "incomplete_results": False,
    "items": [
        {
            **MOCK_ISSUE_RESPONSE,
            "number": 42,
            "title": "Set up GitHub integration",
            "state": "closed"
        },
        {
            **MOCK_ISSUE_RESPONSE,
            "number": 43,
            "title": "Create GitHub webhook for bi-directional sync",
            "state": "open",
            "labels": [
                {"name": "planfile"},
                {"name": "managed"},
                {"name": "priority/high"},
                {"name": "status/in-progress"},
                {"name": "webhook"},
                {"name": "sync"}
            ]
        },
        {
            **MOCK_ISSUE_RESPONSE,
            "number": 44,
            "title": "Test GitHub issue creation",
            "state": "open",
            "labels": [
                {"name": "planfile"},
                {"name": "managed"},
                {"name": "priority/normal"},
                {"name": "testing"}
            ]
        }
    ]
}

# Mock repository response
MOCK_REPO_RESPONSE = {
    "id": 12345678,
    "name": "myproject",
    "full_name": "myorg/myproject",
    "owner": {
        "login": "myorg",
        "id": 87654321
    },
    "private": False,
    "html_url": "https://github.com/myorg/myproject",
    "description": "Example project for GitHub integration",
    "default_branch": "main",
    "open_issues_count": 3,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-03-27T10:00:00Z"
}

# Mock milestone response (for future milestone support)
MOCK_MILESTONE = {
    "id": 23456789,
    "number": 1,
    "title": "Sprint 1",
    "description": "GitHub Integration Sprint",
    "state": "open",
    "open_issues": 2,
    "closed_issues": 1,
    "created_at": "2026-03-27T00:00:00Z",
    "updated_at": "2026-03-27T10:00:00Z",
    "due_on": "2026-04-10T23:59:59Z",
    "html_url": "https://github.com/myorg/myproject/milestone/1"
}
