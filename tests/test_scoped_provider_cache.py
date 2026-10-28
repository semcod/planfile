from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import requests
from procache import ProviderCooldownError

from planfile.sync.generic import GenericBackend
from planfile.sync.github_projects import GitHubProjectsBackend
from planfile.sync.onedev import OneDevBackend


def reply(data, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(data).encode()
    return response


@pytest.fixture(params=["generic", "onedev", "graphql"])
def provider(request, tmp_path, monkeypatch):
    monkeypatch.setenv("SUBACTOR_PROCACHE_PATH", str(tmp_path / "providers.sqlite3"))
    def make(credential="placeholder_a"):
        if request.param == "generic":
            backend = GenericBackend("https://provider.test", api_key=credential)
        elif request.param == "onedev":
            backend = OneDevBackend("https://provider.test", "owner/repo", username="test", password=credential)
        else:
            backend = GitHubProjectsBackend(token=credential)
        session = getattr(backend, "session", None) or backend._session
        session.trust_env = False
        return backend, session
    def read(backend):
        if request.param == "generic":
            return backend._make_request("GET", "/records")
        if request.param == "onedev":
            return backend._request("GET", "/~api/issues/1")
        return backend._graphql("query { viewer { id } }", {})
    def mutate(backend):
        if request.param == "generic":
            return backend._make_request("PUT", "/records", data={"state": "new"})
        if request.param == "onedev":
            return backend._request("PUT", "/~api/issues/1", payload={"state": "new"})
        return backend._graphql("# update\nmutation { update { id } }", {})
    def route(session, callback):
        if request.param == "graphql":
            session.post = callback
        else:
            session.request = callback
    def response(data, status=200):
        return reply({"data": data} if request.param == "graphql" else data, status)
    return SimpleNamespace(make=make, read=read, mutate=mutate, route=route, response=response,
                           kind=request.param, path=tmp_path / "providers.sqlite3")


def test_records_are_reused_between_matching_clients(provider):
    first, a = provider.make()
    second, b = provider.make()
    provider.route(a, lambda *args, **kwargs: provider.response({"id": "record"}))
    provider.route(b, lambda *args, **kwargs: pytest.fail("duplicate upstream read"))
    assert provider.read(first) == provider.read(second) == {"id": "record"}


def test_credentials_and_representations_are_isolated(provider):
    first, a = provider.make()
    other, b = provider.make("placeholder_b")
    provider.route(a, lambda *args, **kwargs: provider.response({"id": "first"}))
    provider.route(b, lambda *args, **kwargs: provider.response({"id": "other"}))
    assert provider.read(first) == {"id": "first"}
    assert provider.read(other) == {"id": "other"}
    a.headers["X-Tenant"] = "different"
    provider.route(a, lambda *args, **kwargs: provider.response({"id": "new-tenant"}))
    assert provider.read(first) == {"id": "new-tenant"}


def test_mutations_are_live_and_invalidate_only_their_account(provider):
    first, a = provider.make()
    other, b = provider.make("placeholder_b")
    provider.route(a, lambda *args, **kwargs: provider.response({"id": "old"}))
    provider.route(b, lambda *args, **kwargs: provider.response({"id": "other"}))
    provider.read(first)
    provider.read(other)
    writes = []
    provider.route(a, lambda *args, **kwargs: (writes.append(1) or provider.response({"id": "new"})))
    provider.mutate(first)
    provider.mutate(first)
    assert len(writes) == 2
    assert provider.read(first) == {"id": "new"}
    provider.route(b, lambda *args, **kwargs: pytest.fail("other account invalidated"))
    assert provider.read(other) == {"id": "other"}


def test_inflight_read_cannot_repopulate_after_mutation(provider):
    first, a = provider.make()
    writer, b = provider.make()
    started, finish = threading.Event(), threading.Event()
    def slow(*args, **kwargs):
        started.set()
        assert finish.wait(5)
        return provider.response({"id": "old"})
    provider.route(a, slow)
    provider.route(b, lambda *args, **kwargs: provider.response({"id": "new"}))
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(provider.read, first)
        assert started.wait(5)
        provider.mutate(writer)
        assert provider.read(writer) == {"id": "new"}
        finish.set()
        assert old.result() == {"id": "old"}
    provider.route(b, lambda *args, **kwargs: pytest.fail("old generation overwrote new one"))
    assert provider.read(writer) == {"id": "new"}


def test_unknown_mutation_outcome_also_invalidates(provider):
    backend, session = provider.make()
    provider.route(session, lambda *args, **kwargs: provider.response({"id": "old"}))
    provider.read(backend)
    def fail(*args, **kwargs):
        raise requests.Timeout("unknown remote outcome")
    provider.route(session, fail)
    with pytest.raises(requests.Timeout):
        provider.mutate(backend)
    provider.route(session, lambda *args, **kwargs: provider.response({"id": "new"}))
    assert provider.read(backend) == {"id": "new"}


def test_failures_are_not_persisted(provider):
    backend, session = provider.make()
    provider.route(session, lambda *args, **kwargs: provider.response({"error": "failed"}, 500))
    with pytest.raises((RuntimeError, requests.HTTPError)):
        provider.read(backend)
    provider.route(session, lambda *args, **kwargs: provider.response({"id": "recovered"}))
    assert provider.read(backend) == {"id": "recovered"}


def test_rate_limit_cooldown_is_not_shared_between_accounts(provider):
    backend, a = provider.make()
    other, b = provider.make("placeholder_b")
    provider.route(a, lambda *args, **kwargs: provider.response({"error": "limited"}, 429))
    with pytest.raises((RuntimeError, requests.HTTPError)):
        provider.read(backend)
    provider.route(a, lambda *args, **kwargs: pytest.fail("cooldown bypassed"))
    with pytest.raises(ProviderCooldownError):
        provider.read(backend)
    provider.route(b, lambda *args, **kwargs: provider.response({"id": "other"}))
    assert provider.read(other) == {"id": "other"}


def test_credentials_do_not_enter_persisted_records(provider):
    backend, session = provider.make()
    provider.route(session, lambda *args, **kwargs: provider.response({"id": "record"}))
    provider.read(backend)
    with sqlite3.connect(provider.path) as db:
        assert "placeholder_a" not in repr(db.execute("SELECT * FROM responses").fetchall())


def test_custom_authentication_bypasses_shared_cache(provider):
    backend, session = provider.make()
    session.auth = lambda prepared: prepared
    calls = []
    provider.route(session, lambda *args, **kwargs: (calls.append(1) or provider.response({"id": "record"})))
    provider.read(backend)
    provider.read(backend)
    assert len(calls) == 2


def test_generic_invalid_json_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBACTOR_PROCACHE_PATH", str(tmp_path / "generic.sqlite3"))
    backend = GenericBackend("https://provider.test", api_key="placeholder_a")
    backend.session.trust_env = False
    result = reply({})
    result._content = b"invalid-json"
    backend.session.request = lambda **kwargs: result
    with pytest.raises(ValueError):
        backend._make_request("GET", "/records")
    backend.session.request = lambda **kwargs: reply({"id": "valid"})
    assert backend._make_request("GET", "/records") == {"id": "valid"}
