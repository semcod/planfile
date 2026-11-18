"""Monotonic operation deadlines for scoped GitHub inbound synchronization."""

from __future__ import annotations

import inspect
import math
import os
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any

try:
    from requests.exceptions import Timeout as RequestsTimeoutError
except Exception:  # pragma: no cover - requests is a PyGithub runtime dependency
    RequestsTimeoutError = None  # type: ignore[assignment,misc]

DEFAULT_INBOUND_TIMEOUT_SECONDS = 60.0
TIMEOUT_ENV_VAR = "PLANFILE_SYNC_TIMEOUT_SECONDS"
_MISSING = object()


class SyncDeadlineExceededError(RuntimeError, TimeoutError):
    """Raised when an inbound sync stage exceeds its monotonic operation deadline."""

    def __init__(
        self,
        stage: str,
        timeout_seconds: float,
        elapsed_seconds: float,
        completed_tickets: Iterable[str] = (),
        pending_tickets: Iterable[str] = (),
    ) -> None:
        self.stage = str(stage)
        self.timeout_seconds = float(timeout_seconds)
        self.elapsed_seconds = max(0.0, float(elapsed_seconds))
        self.completed_tickets = tuple(str(item) for item in completed_tickets)
        self.pending_tickets = tuple(str(item) for item in pending_tickets)
        super().__init__(
            f"GitHub inbound sync exceeded deadline of {self.timeout_seconds:.2f}s "
            f"during '{self.stage}' after {self.elapsed_seconds:.2f}s "
            f"(completed={len(self.completed_tickets)}, pending={len(self.pending_tickets)})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize structured deadline expiry diagnostics for JSON CLI output."""
        return {
            "error": "sync_deadline_exceeded",
            "stage": self.stage,
            "timeout_seconds": round(self.timeout_seconds, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "completed_tickets": list(self.completed_tickets),
            "pending_tickets": list(self.pending_tickets),
            "message": str(self),
        }


def _coerce_positive_seconds(value: Any, *, source: str) -> float:
    """Validate and coerce a positive, finite timeout duration in seconds."""
    if isinstance(value, bool):
        raise ValueError(f"{source} must be a positive finite number, got bool")
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source} must be a positive finite number, got {value!r}") from exc
    if not math.isfinite(seconds) or seconds <= 0.0:
        raise ValueError(f"{source} must be a positive finite number, got {value!r}")
    return seconds


class SyncDeadline:
    """Monotonic deadline tracker shared across stages of one inbound sync."""

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_INBOUND_TIMEOUT_SECONDS,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.timeout_seconds = _coerce_positive_seconds(
            timeout_seconds, source="timeout_seconds"
        )
        self._clock = clock or time.monotonic
        self.started_at = float(self._clock())
        self.current_stage = "repository_identity"

    def set_stage(self, stage: str) -> None:
        """Update the active inbound stage reported on requester timeouts."""
        self.current_stage = str(stage)

    def elapsed(self) -> float:
        """Return elapsed monotonic seconds since the deadline started."""
        return max(0.0, float(self._clock()) - self.started_at)

    def remaining(self) -> float:
        """Return remaining monotonic seconds before expiry (may be <= 0.0)."""
        return self.timeout_seconds - self.elapsed()

    def check(
        self,
        stage: str | None = None,
        *,
        completed_tickets: Iterable[str] = (),
        pending_tickets: Iterable[str] = (),
    ) -> float:
        """Raise SyncDeadlineExceededError if expired, else return remaining seconds."""
        active_stage = self.current_stage if stage is None else str(stage)
        elapsed = self.elapsed()
        remaining = self.timeout_seconds - elapsed
        if remaining <= 0.0:
            raise SyncDeadlineExceededError(
                stage=active_stage,
                timeout_seconds=self.timeout_seconds,
                elapsed_seconds=elapsed,
                completed_tickets=completed_tickets,
                pending_tickets=pending_tickets,
            )
        return remaining

    def clamp_timeout(
        self,
        existing_timeout: Any = None,
        *,
        stage: str | None = None,
        completed_tickets: Iterable[str] = (),
        pending_tickets: Iterable[str] = (),
    ) -> float:
        """Return remaining budget capped by an existing positive requester timeout."""
        remaining = self.check(
            stage=stage,
            completed_tickets=completed_tickets,
            pending_tickets=pending_tickets,
        )
        if (
            isinstance(existing_timeout, (int, float))
            and not isinstance(existing_timeout, bool)
            and math.isfinite(float(existing_timeout))
            and float(existing_timeout) > 0.0
        ):
            return min(float(existing_timeout), remaining)
        return remaining


def resolve_inbound_deadline(
    timeout_seconds: float | None = None,
    backend: Any = None,
    *,
    clock: Callable[[], float] | None = None,
) -> SyncDeadline:
    """Resolve effective monotonic deadline: explicit > config > env > 60.0s default."""
    if timeout_seconds is not None:
        resolved = _coerce_positive_seconds(timeout_seconds, source="--timeout")
    else:
        config = getattr(backend, "config", None) if backend is not None else None
        config_value = config.get("sync_timeout_seconds") if isinstance(config, dict) else None
        if config_value is not None:
            resolved = _coerce_positive_seconds(
                config_value, source="integrations.github.sync_timeout_seconds"
            )
        else:
            env_value = os.environ.get(TIMEOUT_ENV_VAR, "").strip()
            if env_value:
                resolved = _coerce_positive_seconds(env_value, source=TIMEOUT_ENV_VAR)
            else:
                resolved = DEFAULT_INBOUND_TIMEOUT_SECONDS
    return SyncDeadline(resolved, clock=clock)


def _timeout_exception_types() -> tuple[type[BaseException], ...]:
    if RequestsTimeoutError is not None:
        return (TimeoutError, RequestsTimeoutError)
    return (TimeoutError,)


def _is_scalar_or_none_timeout(value: Any) -> bool:
    if value is None:
        return True
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _collect_requesters(backend: Any) -> list[tuple[Any, Any]]:
    """Collect real requester objects owning _Requester__timeout without touching Mocks."""
    candidates: list[Any] = []
    if backend is None:
        return []
    for obj in (
        getattr(backend, "_identity_requester", None),
        getattr(getattr(backend, "github", None), "_Github__requester", None),
        getattr(getattr(backend, "github", None), "requester", None),
        getattr(getattr(backend, "repo", None), "_requester", None),
    ):
        if obj is not None:
            candidates.append(obj)

    seen_ids: set[int] = set()
    requesters: list[tuple[Any, Any]] = []
    while candidates:
        obj = candidates.pop(0)
        if id(obj) in seen_ids:
            continue
        seen_ids.add(id(obj))

        obj_dict = getattr(obj, "__dict__", None)
        if isinstance(obj_dict, dict):
            if "_Requester__timeout" in obj_dict:
                orig_timeout = obj_dict["_Requester__timeout"]
                if _is_scalar_or_none_timeout(orig_timeout):
                    requesters.append((obj, orig_timeout))
            if "_requester" in obj_dict and obj_dict["_requester"] is not None:
                candidates.append(obj_dict["_requester"])
    return requesters


def _patch_attr(
    obj: Any,
    attr_name: str,
    wrapper_factory: Callable[[Any], Any],
    patches: list[tuple[Any, str, Any]],
) -> None:
    """Safely wrap an existing callable attribute on obj and record restore state."""
    if obj is None:
        return
    static_val = inspect.getattr_static(obj, attr_name, _MISSING)
    if static_val is _MISSING:
        return
    bound = getattr(obj, attr_name, None)
    if not callable(bound):
        return
    obj_dict = getattr(obj, "__dict__", None)
    orig_in_dict = (
        obj_dict[attr_name] if isinstance(obj_dict, dict) and attr_name in obj_dict else _MISSING
    )
    setattr(obj, attr_name, wrapper_factory(bound))
    patches.append((obj, attr_name, orig_in_dict))


@contextmanager
def bind_backend_deadline(backend: Any, deadline: SyncDeadline) -> Iterator[SyncDeadline]:
    """Clamp PyGithub requester timeouts and enforce deadline across backend reads."""
    requesters = _collect_requesters(backend)
    patches: list[tuple[Any, str, Any]] = []
    timeout_excs = _timeout_exception_types()

    def _sync_requester_timeouts(stage: str) -> None:
        remaining = deadline.check(stage=stage)
        for req, orig_timeout in requesters:
            if (
                isinstance(orig_timeout, (int, float))
                and not isinstance(orig_timeout, bool)
                and math.isfinite(float(orig_timeout))
                and float(orig_timeout) > 0.0
            ):
                clamped = min(float(orig_timeout), remaining)
            else:
                clamped = remaining
            req._Requester__timeout = clamped

    def _wrap_call(fn: Callable[..., Any], *, fixed_stage: str | None = None) -> Callable[..., Any]:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            stage = fixed_stage if fixed_stage is not None else deadline.current_stage
            _sync_requester_timeouts(stage)
            try:
                return fn(*args, **kwargs)
            except SyncDeadlineExceededError:
                raise
            except timeout_excs as exc:
                elapsed = deadline.elapsed()
                if elapsed >= deadline.timeout_seconds:
                    raise SyncDeadlineExceededError(
                        stage=stage,
                        timeout_seconds=deadline.timeout_seconds,
                        elapsed_seconds=elapsed,
                    ) from exc
                raise

        return _wrapped

    try:
        _sync_requester_timeouts(deadline.current_stage)
        _patch_attr(
            backend,
            "resolve_repository_identity",
            lambda fn: _wrap_call(fn, fixed_stage="repository_identity"),
            patches,
        )
        _patch_attr(backend, "list_tickets", lambda fn: _wrap_call(fn), patches)
        _patch_attr(backend, "list_selected_tickets", lambda fn: _wrap_call(fn), patches)

        repo = getattr(backend, "repo", None)
        if repo is not None:
            _patch_attr(repo, "get_issue", lambda fn: _wrap_call(fn), patches)
            _patch_attr(repo, "get_issues", lambda fn: _wrap_call(fn), patches)

        for req, _ in requesters:
            _patch_attr(req, "requestJsonAndCheck", lambda fn: _wrap_call(fn), patches)
            _patch_attr(req, "requestJson", lambda fn: _wrap_call(fn), patches)

        yield deadline
    finally:
        for obj, attr_name, orig_in_dict in reversed(patches):
            if orig_in_dict is _MISSING:
                if hasattr(obj, "__dict__") and attr_name in obj.__dict__:
                    delattr(obj, attr_name)
            else:
                setattr(obj, attr_name, orig_in_dict)
        for req, orig_timeout in requesters:
            req._Requester__timeout = orig_timeout
