from types import SimpleNamespace

import pytest

from planfile import Planfile
from planfile.sync.ticket_comments import (
    pending_comment_ids,
    queue_comment,
    sync_comment,
    sync_pending_comments,
)


@pytest.fixture
def context(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Repair",
        sync={"github": {"id": "12", "url": "https://github.com/maskservice/c2004/issues/12"}},
    )
    issue = SimpleNamespace(
        html_url=ticket.sync["github"]["url"], pull_request=None, body="Human text", comments=[]
    )
    issue.get_comments = lambda: iter(issue.comments)

    def create(body):
        comment = SimpleNamespace(body=body, html_url=issue.html_url + "#issuecomment-1")
        issue.comments.append(comment)
        return comment

    issue.create_comment = create
    backend = SimpleNamespace(
        config={"repo": "maskservice/c2004"},
        repo=SimpleNamespace(
            full_name="maskservice/c2004", get_issue=lambda n: issue if n == 12 else None
        ),
    )
    return pf.store, ticket, backend, issue


def test_exact_comment_only_and_idempotent(context):
    store, ticket, backend, issue = context
    first = queue_comment(
        store, ticket.id, event_id="run1", public_body="Verified: 5 tests passed."
    )
    queue_comment(store, ticket.id, event_id="unrelated", public_body="Do not send yet")
    assert first == queue_comment(
        store, ticket.id, event_id="run1", public_body="Verified: 5 tests passed."
    )
    result = sync_comment(store, backend, first)
    assert sync_comment(store, backend, first) == result
    assert len(issue.comments) == 1
    assert issue.body == "Human text"
    assert store.get_ticket(ticket.id).status == "open"


def test_uncertain_post_reconciles_without_duplicate(context):
    store, ticket, backend, issue = context
    event = queue_comment(store, ticket.id, event_id="run1", public_body="Verified")
    create = issue.create_comment

    def lost_response(body):
        create(body)
        raise TimeoutError("private transport details")

    issue.create_comment = lost_response
    with pytest.raises(TimeoutError):
        sync_comment(store, backend, event)
    assert sync_comment(store, backend, event)["state"] == "delivered"
    assert len(issue.comments) == 1


def test_changed_event_or_mapping_is_rejected(context):
    store, ticket, backend, issue = context
    event = queue_comment(store, ticket.id, event_id="run1", public_body="Verified")
    with pytest.raises(ValueError, match="different public text"):
        queue_comment(store, ticket.id, event_id="run1", public_body="Changed")
    store.update_ticket(
        ticket.id,
        sync={"github": {"id": "13", "url": "https://github.com/maskservice/c2004/issues/13"}},
    )
    with pytest.raises(ValueError, match="mapping changed"):
        sync_comment(store, backend, event)
    assert issue.comments == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://github.com/maskservice/c2004/pull/12"),
        ("url", "https://example.com/a/b/issues/12"),
        ("id", "13"),
    ],
)
def test_invalid_mapping(context, field, value):
    store, ticket, _, _ = context
    mapping = dict(ticket.sync["github"])
    mapping[field] = value
    store.update_ticket(ticket.id, sync={"github": mapping})
    with pytest.raises(ValueError, match="exact GitHub"):
        queue_comment(store, ticket.id, event_id="run1", public_body="Verified")


def test_wrong_backend_rejected(context):
    store, ticket, backend, issue = context
    event = queue_comment(store, ticket.id, event_id="run1", public_body="Verified")
    backend.config["repo"] = "other/repository"
    with pytest.raises(ValueError, match="different repository"):
        sync_comment(store, backend, event)
    assert issue.comments == []


def test_symlink_storage_rejected(context, tmp_path):
    store, ticket, _, _ = context
    (tmp_path / ".subactor").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        queue_comment(store, ticket.id, event_id="run1", public_body="Verified")


def test_notes_not_exported(context):
    store, ticket, backend, issue = context
    store.update_ticket(ticket.id, outputs={"notes": ["private raw execution logs"]})
    event = queue_comment(store, ticket.id, event_id="run1", public_body="Verified")
    sync_comment(store, backend, event)
    assert "private" not in issue.comments[0].body


def test_external_mapping_with_unknown_status_can_publish(context):
    store, ticket, backend, issue = context
    raw = store.load_sprint("current")
    record = raw["tickets"].pop(ticket.id)
    record["id"] = "GITHUB-12"
    record["status"] = "waiting_input"
    raw["tickets"]["GITHUB-12"] = record
    store.save_sprint("current", raw)

    event = queue_comment(store, "GITHUB-12", event_id="external-1", public_body="Status verified")
    assert event in pending_comment_ids(store)
    assert sync_pending_comments(store, backend) == [
        {"id": event, "state": "delivered", "url": issue.html_url + "#issuecomment-1"}
    ]
    assert pending_comment_ids(store) == []
