import json

from planfile.sync.generic import GenericBackend


class Response:
    ok = True
    text = ""
    content = json.dumps({"tickets": []}).encode()


def test_generic_get_is_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    backend = GenericBackend("https://pm.example.test")
    calls = 0

    def request(**kwargs):
        nonlocal calls
        calls += 1
        return Response()

    backend.session.request = request

    assert backend._make_request("GET", "/tickets") == {"tickets": []}
    assert backend._make_request("GET", "/tickets") == {"tickets": []}
    assert calls == 1
