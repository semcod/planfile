from unittest.mock import patch

from github import Github as RealGithub
from github import GithubException

from planfile.sync.github import GitHubBackend


def test_quota_surfaces_without_sdk_retries(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBACTOR_PROCACHE_PATH", str(tmp_path / "provider.sqlite3"))
    clients = []
    quota = GithubException(403, {"message": "API rate limit exceeded"}, {"Retry-After": "45"})
    def factory(token, **kwargs):
        # Bind the transport configuration actually passed to PyGithub.
        assert kwargs["retry"] == 0
        client = RealGithub(token, **kwargs)
        clients.append(client)
        return client
    with patch("planfile.sync.github.Github", side_effect=factory):
        with patch.object(RealGithub, "get_repo", side_effect=quota) as request:
            try:
                GitHubBackend("fixture/repo", token="test")
            except GithubException as observed:
                assert observed is quota
                assert observed.headers["Retry-After"] == "45"
            else:
                raise AssertionError("Quota error must reach caller")
    request.assert_called_once()
    for client in clients:
        client.close()
