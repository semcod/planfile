from dataclasses import dataclass
from typing import Any

@dataclass
class LLMTestResult:
    """Result of LLM test."""
    provider: str
    model: str
    success: bool
    response_time: float
    token_count: int | None = None
    cost: float | None = None
    error: str | None = None
    response: str | None = None