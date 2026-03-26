#!/bin/bash

# Example 1: Complete workflow - planfile → llx → proxy
# This script demonstrates the full ecosystem integration

set -e

echo "=========================================="
echo "Planfile + LLX + Proxy Integration Example"
echo "=========================================="

# Create a test project
TEST_PROJECT=$(mktemp -d)
cd "$TEST_PROJECT"
echo "Created test project: $TEST_PROJECT"

# Create a sample Python project with high complexity
mkdir -p src/{models,views,controllers,services,utils}

# Create a god module (high complexity)
cat > src/god_module.py << 'EOF'
"""A god module with high complexity that needs refactoring."""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class UserType(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

@dataclass
class User:
    id: int
    name: str
    email: str
    type: UserType
    created_at: datetime

class UserService:
    """A service class doing too many things."""
    
    def __init__(self):
        self.users = []
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return json.load(f)
        return {"db_url": "sqlite:///app.db", "debug": False}
    
    def create_user(self, name: str, email: str, user_type: UserType) -> User:
        """Create a new user with validation."""
        if not name or not email:
            raise ValueError("Name and email are required")
            
        if "@" not in email:
            raise ValueError("Invalid email format")
            
        user = User(
            id=len(self.users) + 1,
            name=name.strip(),
            email=email.lower().strip(),
            type=user_type,
            created_at=datetime.now()
        )
        
        self.users.append(user)
        self.logger.info(f"Created user: {name}")
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        for user in self.users:
            if user.id == user_id:
                return user
        return None
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user attributes."""
        user = self.get_user(user_id)
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            self.logger.info(f"Updated user {user_id}")
        return user
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user by ID."""
        for i, user in enumerate(self.users):
            if user.id == user_id:
                del self.users[i]
                self.logger.info(f"Deleted user {user_id}")
                return True
        return False
    
    def get_users_by_type(self, user_type: UserType) -> List[User]:
        """Get all users of a specific type."""
        return [u for u in self.users if u.type == user_type]
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user (simplified)."""
        # In real app, this would check hashed password
        user = next((u for u in self.users if u.email == email), None)
        if user and password == "password123":  # Never do this!
            return user
        return None
    
    def export_to_json(self, filepath: str) -> None:
        """Export all users to JSON file."""
        data = []
        for user in self.users:
            data.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "type": user.type.value,
                "created_at": user.created_at.isoformat()
            })
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        self.logger.info(f"Exported {len(data)} users to {filepath}")
    
    def import_from_json(self, filepath: str) -> None:
        """Import users from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        
        for item in data:
            user_type = UserType(item["type"])
            user = User(
                id=item["id"],
                name=item["name"],
                email=item["email"],
                type=user_type,
                created_at=datetime.fromisoformat(item["created_at"])
            )
            self.users.append(user)
        
        self.logger.info(f"Imported {len(data)} users from {filepath}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get user statistics."""
        total = len(self.users)
        by_type = {}
        for ut in UserType:
            by_type[ut.value] = len(self.get_users_by_type(ut))
        
        return {
            "total_users": total,
            "by_type": by_type,
            "latest_user": max(self.users, key=lambda u: u.created_at).name if self.users else None
        }
    
    # ... more complex methods making this a god module
EOF

# Create other modules with various complexity levels
cat > src/models/user.py << 'EOF'
"""User model."""
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    name: str
    email: str
    created_at: datetime = datetime.now()
EOF

cat > src/controllers/user_controller.py << 'EOF'
"""User controller."""
from ..models.user import User
from ..services.user_service import UserService

class UserController:
    def __init__(self):
        self.service = UserService()
    
    def create_user(self, name: str, email: str) -> User:
        return self.service.create_user(name, email)
EOF

cat > src/services/user_service.py << 'EOF'
"""User service."""
from typing import List, Optional
from ..models.user import User

class UserService:
    def __init__(self):
        self.users: List[User] = []
    
    def create_user(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.users.append(user)
        return user
    
    def get_user(self, email: str) -> Optional[User]:
        for user in self.users:
            if user.email == email:
                return user
        return None
EOF

# Create requirements.txt
cat > requirements.txt << 'EOF'
pydantic>=2.0
typer>=0.12
EOF

echo -e "\n1. Generating strategy with planfile..."
# Use planfile to generate a refactoring strategy
planfile generate . --output strategy.yaml --sprints 3 --focus complexity --dry-run

echo -e "\n2. Analyzing with llx..."
# Analyze project with llx to get metrics
if command -v llx &> /dev/null; then
    llx analyze . --output metrics.json
    echo "LLX metrics saved to metrics.json"
else
    echo "LLX not installed, skipping analysis"
fi

echo -e "\n3. Setting up proxy configuration..."
# Create proxy config for model routing
cat > proxy-config.yaml << 'EOF'
routing:
  rules:
    - pattern: ".*refactor.*"
      models: ["anthropic/claude-sonnet-4", "openai/gpt-4"]
      fallback: true
    - pattern: ".*test.*"
      models: ["anthropic/claude-haiku-4.5"]
      cheap: true
    - pattern: ".*"
      models: ["openrouter/deepseek/deepseek-chat-v3"]
      default: true

budget:
  daily_limit: 10.0
  per_request_limit: 1.0

cache:
  enabled: true
  ttl: 3600
EOF

echo -e "\n4. Creating example tasks for each sprint..."
# Create task examples based on strategy
cat > tasks.yaml << 'EOF'
sprint_tasks:
  sprint-1:
    - name: "Extract user model from god_module.py"
      type: "refactor"
      priority: "high"
      model_hint: "balanced"
      description: "Move User class and related enums to separate module"
    
    - name: "Split UserService by responsibility"
      type: "refactor"
      priority: "high"
      model_hint: "premium"
      description: "Separate authentication, persistence, and business logic"
    
    - name: "Add unit tests for UserService"
      type: "test"
      priority: "medium"
      model_hint: "cheap"
      description: "Create comprehensive test suite"

  sprint-2:
    - name: "Implement repository pattern"
      type: "refactor"
      priority: "medium"
      model_hint: "balanced"
      description: "Add abstraction layer for data access"
    
    - name: "Add dependency injection"
      type: "refactor"
      priority: "medium"
      model_hint: "balanced"
      description: "Remove hardcoded dependencies"

  sprint-3:
    - name: "Add API documentation"
      type: "docs"
      priority: "low"
      model_hint: "cheap"
      description: "Generate OpenAPI spec"
    
    - name: "Performance optimization"
      type: "feature"
      priority: "low"
      model_hint: "premium"
      description: "Add caching and optimize queries"
EOF

echo -e "\n5. Example execution workflow..."
cat > workflow.md << 'EOF'
# Complete Refactoring Workflow

## Step 1: Generate Strategy
```bash
planfile generate . --output strategy.yaml --model anthropic/claude-sonnet-4
```

## Step 2: Analyze with LLX
```bash
llx analyze . --toon-dir .analysis
llx select-model --project . --task refactor
```

## Step 3: Configure Proxy
```bash
# Start proxy with routing config
docker run -p 4000:4000 -v $(pwd)/proxy-config.yaml:/config.yaml proxym
```

## Step 4: Execute Tasks
```bash
# For each task in strategy.yaml:
llx apply --task "Extract user model" --model routed-by-proxy

# Or use planfile to orchestrate:
planfile apply strategy.yaml --backend github --proxy localhost:4000
```

## Step 5: Track Progress
```bash
# Check progress in proxy dashboard
curl http://localhost:4000/dashboard/api/projects

# Or use planfile:
planfile review strategy.yaml --format markdown --output progress.md
```
EOF

echo -e "\n✅ Example project created at: $TEST_PROJECT"
echo -e "\nFiles created:"
find . -type f -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" | sort

# Cleanup instruction
echo -e "\nTo cleanup: rm -rf $TEST_PROJECT"
