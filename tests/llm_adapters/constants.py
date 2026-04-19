CONSTANT_120 = 120.0
CONSTANT_200 = 200
CONSTANT_4000 = 4000

"""
LiteLLM adapters for testing planfile with various LLM providers.
"""

import os
from pathlib import Path
from typing import Any

try:
    import litellm
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    litellm = None

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None