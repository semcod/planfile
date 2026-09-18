from types import SimpleNamespace

from planfile import Planfile
from planfile.cli.groups.sync import core as sync_core
from planfile.sync.ticket_comments import queue_comment


def test_github_sync_delivers_queued_public_comment(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Mapped issue",
        integration=["github"],
        sync={"github": {"id": "12", "url": "https://github.com/acme/demo/issues/12"}},
    )
    issue = SimpleNamespace(
        html_url=ticket.sync["github"]["url"], pull_request=None, comments=[]
    )
    issue.get_comments = lambda: iter(issue.comments)
    def create_comment(body):
        comment = SimpleNamespace(body=body, html_url=issue.html_url + "#issuecomment-1")
        issue.comments.append(comment)
        return comment

    issue.create_comment = create_comment
    backend = SimpleNamespace(
        config={"repo": "acme/demo"},
        repo=SimpleNamespace(
            full_name="acme/demo", get_issue=lambda number: issue if number == 12 else None
        ),
    )

    class Config:
        config = {"integrations": {"github": {"repo": "acme/demo"}}}

        def load_configs(self):
            return None

        def get_integration_config(self, name):
            return self.config["integrations"][name]

    monkeypatch.setattr(sync_core, "IntegrationConfig", lambda _: Config())
    monkeypatch.setattr(sync_core, "_initialize_backend", lambda *args: backend)
    monkeypatch.setattr(sync_core, "_execute_sync_with_progress", lambda *args, **kwargs: None)

    queue_comment(pf.store, ticket.id, event_id="sync-run", public_body="Public verification")
    sync_core.sync_integration("github", str(tmp_path), False, "to", show_header=False)
    sync_core.sync_integration("github", str(tmp_path), False, "to", show_header=False)

    assert len(issue.comments) == 1
    assert issue.comments[0].body.startswith("Public verification")
