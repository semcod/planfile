"""Credential isolation and mutation fencing around the canonical procache store."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import requests
from procache import SQLiteResponseCache


def session_identity(base_url: str, session: requests.Session) -> object | None:
    auth = session.auth
    if auth is None and session.trust_env:
        try:
            auth = requests.utils.get_netrc_auth(base_url)
        except OSError:
            return None
    if isinstance(auth, (requests.auth.HTTPBasicAuth, requests.auth.HTTPDigestAuth)):
        auth = (type(auth).__name__, auth.username, auth.password)
    elif auth is not None and not isinstance(auth, (tuple, list)):
        # Signing/custom authentication can hide its principal from the session.
        return None
    headers = {str(k).lower(): str(v) for k, v in session.headers.items()}
    cookies = sorted((c.domain, c.path, c.name, c.value) for c in session.cookies)
    return base_url, auth, headers, cookies


class ScopedReadCache:
    """Reuse process-safe reads without sharing records or cooldowns across accounts.

    A generation tombstone makes old flights unreachable after a mutation;
    deleting rows alone would let an older loader repopulate current reads.
    Identity inputs only enter hashed keys, never persisted metadata.
    """

    key = staticmethod(SQLiteResponseCache.key)

    def __init__(self, path: object, *, namespace: str, identity: Callable[[], object | None]) -> None:
        self._store = SQLiteResponseCache(path, namespace=namespace + "-scoped-v1")
        self._identity = identity

    def _authority(self) -> str | None:
        identity = self._identity()
        return self.key("account-v1", identity) if identity is not None else None

    def get_or_set(self, key: str, loader: Callable[[], bytes], *, ttl: float, **kwargs: Any) -> tuple[bytes, bool]:
        authority = self._authority()
        if authority is None or ttl == 0:
            return loader(), False
        epoch = self._store.get(self.key("epoch-v1", authority))
        scoped_key = self.key("read-v1", authority, epoch.value.hex() if epoch else "initial", key)
        if kwargs.get("cooldown_key") is not None:
            kwargs["cooldown_key"] = self.key("cooldown-v1", authority, kwargs["cooldown_key"])
        eligible = kwargs.pop("should_cache", None)
        classify = kwargs.get("is_rate_limit")
        if classify is not None:
            kwargs["is_rate_limit"] = lambda error: (
                getattr(getattr(error, "response", None), "status_code", None) == 429 or classify(error)
            )
        return self._store.get_or_set(
            scoped_key, loader, ttl=ttl,
            should_cache=lambda value: self._authority() == authority and (eligible is None or eligible(value)),
            **kwargs,
        )

    def clear(self) -> None:
        authority = self._authority()
        if authority is not None:
            self._store.put(self.key("epoch-v1", authority), uuid.uuid4().hex.encode(), ttl=86400)
