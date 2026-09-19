"""Provider quota failures retain scheduling evidence and useful diagnostics."""
from io import StringIO
from types import SimpleNamespace

import pytest
from github import GithubException
from rich.console import Console

from planfile.sync import operations
from planfile.sync.outbound import _retry_after_seconds


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("status,message,headers", [
    (403, "API rate limit exceeded", {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1800000000"}),
    (403, "You have exceeded a secondary rate limit", {"Retry-After": "45"}),
    (403, "Forbidden", {"x-ratelimit-remaining": "0"}),
    (429, "Too many requests", {"Retry-After": "60"}),
    (403, "Abuse detection mechanism triggered", {}),
    (403, "API rate limit exceeded for user 404", {}),
])
def test_rate_limits_preserve_original_exception_and_retry_hints(monkeypatch, operation, status, message, headers):
    error = GithubException(status, {"message": message}, headers)
    output = StringIO()
    monkeypatch.setattr(operations, "console", Console(file=output, width=200))
    calls = []
    def fail(kind):
        def invoke(*args, **kwargs):
            calls.append(kind)
            raise error
        return invoke
    backend = SimpleNamespace(config={"repo": "owner/repo"}, create_ticket=fail("create"), update_ticket=fail("update"))
    with pytest.raises(GithubException) as caught:
        if operation == "create":
            operations._create_new_ticket(backend, {"name": "Task"}, "PLF-001", "github", None, {})
        else:
            operations._update_existing_ticket(backend, {"name": "Task"}, "PLF-001", "1", "github", None)
    assert caught.value is error
    assert calls == [operation]  # A quota failure must not trigger a replacement create.
    text = output.getvalue()
    assert "rate limit exceeded" in text
    assert "permission denied" not in text
    assert "set-token" not in text and "auth switch" not in text
    if "Retry-After" in headers:
        assert _retry_after_seconds(caught.value) == int(headers["Retry-After"])
        assert headers["Retry-After"] in text
    if "X-RateLimit-Reset" in headers:
        assert headers["X-RateLimit-Reset"] in text


def test_access_denial_is_not_a_quota_failure(monkeypatch):
    error = GithubException(403, {"message": "Resource not accessible by integration"}, {"X-RateLimit-Remaining": "42"})
    output = StringIO()
    monkeypatch.setattr(operations, "console", Console(file=output))
    assert not operations._is_rate_limit_error(error)
    assert operations._is_permission_error(error)
    def fail(*args, **kwargs):
        raise error
    with pytest.raises(RuntimeError, match="required permissions") as caught:
        operations._update_existing_ticket(SimpleNamespace(update_ticket=fail), {}, "PLF-001", "1", "github", None)
    assert caught.value.__cause__ is error
    assert "permission denied" in output.getvalue()
    assert "rate limit exceeded" not in output.getvalue()


def test_unrelated_429_text_and_untrusted_headers_are_not_instructions(monkeypatch):
    assert not operations._is_rate_limit_error(RuntimeError("Could not update issue 429"))
    output = StringIO()
    monkeypatch.setattr(operations, "console", Console(file=output))
    error = GithubException(429, {"message": "private response"}, {"Retry-After": "[link=https://private.invalid]secret", "Authorization": "private-token"})
    operations._print_rate_limit_error("PLF-001", error)
    assert "private" not in output.getvalue()
    assert "secret" not in output.getvalue()
