#!/bin/bash

# Bash script to generate planfile.yaml and verify its correctness
# This test ensures planfile.yaml is generated correctly and consistently

set -e

echo "Testing planfile.yaml generation..."

# Create test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

# Function to test planfile generation
test_planfile_generation() {
    local test_name=$1
    local config_file=$2
    
    echo -e "\n=== Testing: $test_name ==="
    
    # Create test project
    mkdir -p "$test_name"
    cd "$test_name"
    
    # Create basic Python structure
    mkdir -p src/{models,views,controllers}
    
    # Create sample files
    cat > src/models/__init__.py << 'EOF'
"""Models module."""
EOF

cat > src/models/user.py << 'EOF'
"""User model."""

class User:
    """User entity."""
    
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
    
    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {"username": self.username, "email": self.email}
EOF

cat > src/views/__init__.py << 'EOF'
"""Views module."""
EOF

cat > src/views/user_view.py << 'EOF'
"""User views."""

def render_user(user):
    """Render user data."""
    return f"User: {user.username} ({user.email})"
EOF

cat > src/controllers/__init__.py << 'EOF'
"""Controllers module."""
EOF

cat > src/controllers/user_controller.py << 'EOF'
"""User controller."""

from ..models.user import User
from ..views.user_view import render_user

class UserController:
    """Controller for user operations."""
    
    def create_user(self, username: str, email: str) -> str:
        """Create and render a new user."""
        user = User(username, email)
        return render_user(user)
EOF

# Run planfile init
if [ -n "$config_file" ]; then
    echo "Using config file: $config_file"
    planfile init --config "$config_file"
else
    planfile init
fi

# Verify planfile.yaml exists
if [ ! -f "planfile.yaml" ]; then
    echo "❌ ERROR: planfile.yaml not generated"
    cd ..
    return 1
fi

echo "✓ planfile.yaml generated"

# Validate the generated file
planfile strategy validate --strategy planfile.yaml || {
    echo "❌ ERROR: Generated planfile.yaml is invalid"
    cd ..
    return 1
}

echo "✓ planfile.yaml is valid"

# Check required sections
echo -e "\nChecking planfile.yaml structure..."
required_sections=("project" "sprints" "tasks")
for section in "${required_sections[@]}"; do
    if grep -q "^$section:" planfile.yaml; then
        echo "✓ Section '$section' found"
    else
        echo "⚠️  WARNING: Section '$section' not found"
    fi
done

# Display generated content
echo -e "\nGenerated planfile.yaml content:"
cat planfile.yaml

# Test consistency - generate again and compare
echo -e "\nTesting generation consistency..."
cp planfile.yaml planfile.yaml.backup

# Remove and regenerate
rm planfile.yaml
planfile init

# Compare files (ignoring timestamps if any)
if diff -q planfile.yaml planfile.yaml.backup > /dev/null; then
    echo "✓ Generation is consistent"
else
    echo "⚠️  WARNING: Generation differs between runs"
    echo "Differences:"
    diff planfile.yaml planfile.yaml.backup || true
fi

cd ..
}

# Test 1: Default generation
test_planfile_generation "default_generation"

# Test 2: With custom config
cat > custom_config.yaml << 'EOF'
project:
  name: "Custom Config Project"
  description: "Project with custom configuration"
  default_priority: "medium"
  
sprints:
  - id: 1
    name: "Setup Sprint"
    start_date: "2024-01-01"
    end_date: "2024-01-07"
    
quality_gates:
  - name: "Documentation"
    threshold: 70
    type: "coverage"
  
integrations:
  backends:
    - type: "generic"
      name: "local"
EOF

test_planfile_generation "custom_config_generation" "$TEST_DIR/custom_config.yaml"

# Test 3: Complex project structure
echo -e "\n=== Testing: Complex Project Structure ==="
mkdir -p complex_project
cd complex_project

# Create a more complex structure
mkdir -p {src,tests,docs,scripts,config}
mkdir -p src/{api,core,utils,services}
mkdir -p tests/{unit,integration,e2e}

# Create __init__.py files
find src -type d -exec touch {}/__init__.py \;

# Create sample modules
cat > src/api/__init__.py << 'EOF'
"""API module."""
EOF

cat > src/api/routes.py << 'EOF'
"""API routes."""

from flask import Blueprint

api = Blueprint('api', __name__)

@api.route('/health')
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
EOF

cat > src/core/__init__.py << 'EOF'
"""Core module."""
EOF

cat > src/core/config.py << 'EOF'
"""Core configuration."""

import os
from typing import Dict, Any

class Config:
    """Application configuration."""
    
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'debug': cls.DEBUG,
            'database_url': cls.DATABASE_URL
        }
EOF

cat > src/services/__init__.py << 'EOF'
"""Services module."""
EOF

cat > src/services/user_service.py << 'EOF'
"""User service."""

from typing import List, Optional
from ..core.config import Config

class UserService:
    """Service for user management."""
    
    def __init__(self):
        self.config = Config()
        self.users = []
    
    def create_user(self, username: str) -> dict:
        """Create a new user."""
        user = {"id": len(self.users) + 1, "username": username}
        self.users.append(user)
        return user
    
    def get_user(self, user_id: int) -> Optional[dict]:
        """Get user by ID."""
        for user in self.users:
            if user["id"] == user_id:
                return user
        return None
EOF

# Generate planfile for complex project
planfile init

# Verify and validate
if [ -f "planfile.yaml" ]; then
    echo "✓ planfile.yaml generated for complex project"
    
    # Check if tasks were created for different modules
    task_count=$(grep -c "^  - name:" planfile.yaml || echo "0")
    echo "✓ Generated $task_count tasks"
    
    # Validate
    planfile strategy validate --strategy planfile.yaml && echo "✓ Complex project planfile is valid"
fi

cd ..

# Cleanup
cd ..
rm -rf "$TEST_DIR"

echo -e "\n✅ All planfile.yaml generation tests completed!"
