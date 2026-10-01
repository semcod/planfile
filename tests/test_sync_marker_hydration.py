from unittest.mock import Mock

from github.Issue import Issue

from planfile.sync.github import GitHubBackend


def make_issue(number, body, *, pull_request=False):
    payload = {
        "number": number,
        "url": f"https://api.github.com/repos/test/project/issues/{number}",
        "html_url": f"https://github.com/test/project/issues/{number}",
        "state": "open",
        "body": body,
    }
    if pull_request:
        payload["pull_request"] = {"url": f"https://api.github.com/repos/test/project/pulls/{number}"}
    requester = Mock()
    requester.requestJsonAndCheck.return_value = ({}, payload)
    return Issue(requester, {}, payload, completed=False), requester


def test_marker_lookup_uses_list_payload_without_hydrating_every_issue(tmp_path):
    marker = "<!-- planfile:deduplication-key=test/project:PLF-1 -->"
    rows = [make_issue(n, "unrelated") for n in range(1, 5)]
    rows.append(make_issue(5, marker, pull_request=True))
    rows.append(make_issue(6, marker))
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "test/project", "cache_enabled": False, "cache_dir": str(tmp_path)}
    backend.repo = Mock(full_name="test/project")
    backend.repo.get_issues.return_value = [issue for issue, _ in rows]

    result = backend._find_issue_by_markers([marker])

    assert result.number == 6
    assert sum(requester.requestJsonAndCheck.call_count for _, requester in rows) == 0


def test_partial_issue_still_hydrates_and_excludes_pull_requests(tmp_path):
    marker = "<!-- planfile:deduplication-key=test/project:PLF-1 -->"
    _, requester = make_issue(7, marker, pull_request=True)
    partial = Issue(requester, {}, {"number": 7, "url": "https://api.github.com/repos/test/project/issues/7"}, completed=False)
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "test/project", "cache_enabled": False, "cache_dir": str(tmp_path)}
    backend.repo = Mock(full_name="test/project")
    backend.repo.get_issues.return_value = [partial]

    assert backend._find_issue_by_markers([marker]) is None
    assert requester.requestJsonAndCheck.call_count == 1
