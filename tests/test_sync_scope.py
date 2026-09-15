from types import SimpleNamespace

from planfile.cli.groups.sync.core import _load_tickets_for_sync
from planfile.core.store import Store
from planfile.sync.base import TicketState
from planfile.sync.operations import _import_new_ticket, _process_external_ticket
from planfile.sync.outbound import sync_to_external


class StoreWithCustomSprints:
    def is_initialized(self):
        return True

    def _all_sprint_ids(self):
        return ["current", "backlog", "custom-review", "history-2026-09-14"]

    def load_sprint(self, sprint_id):
        tickets = {
                "current": {"PLF-1": {"name": "active", "integration": ["github"]}},
                "backlog": {"PLF-2": {"name": "backlog", "integration": ["github"]}},
                "custom-review": {
                    "PLF-3": {"name": "custom", "integration": ["github"]},
                    "PLF-2": {"name": "duplicate", "integration": ["github"]},
                },
                "history-2026-09-14": {
                    "PLF-4": {
                        "name": "done",
                        "status": "done",
                        "integration": ["github"],
                    }
                },
            }[sprint_id]
        return {"tickets": tickets}


def test_sync_scope_includes_custom_and_history_sprints():
    tickets, source, _, _ = _load_tickets_for_sync(StoreWithCustomSprints(), ".", "github")

    assert source == ".planfile/ structure"
    assert [ticket_id for ticket_id, _ in tickets] == ["PLF-1", "PLF-2", "PLF-3", "PLF-4"]


def test_sync_scope_can_select_exact_ticket_and_custom_sprint():
    tickets, _, _, _ = _load_tickets_for_sync(
        StoreWithCustomSprints(),
        ".",
        "github",
        ticket_ids=["PLF-3"],
        sprint_ids=["custom-review"],
    )

    assert [ticket_id for ticket_id, _ in tickets] == ["PLF-3"]


class FakeState:
    def __init__(self):
        self.mapping = {}

    def get_local_id(self, remote_id):
        return next((local for local, remote in self.mapping.items() if remote == remote_id), None)

    def save_sync(self, mapping):
        self.mapping.update(mapping)


def test_imported_ticket_has_id_and_is_readable_by_store(tmp_path):
    from planfile import Planfile

    pf = Planfile(str(tmp_path))
    backlog = {"tickets": {}}
    state = FakeState()
    external = TicketState(
        id="17",
        key="owner/repo#17",
        name="Imported issue",
        description="evidence",
        status="open",
        url="https://github.com/owner/repo/issues/17",
    )

    assert _import_new_ticket(backlog, external.model_dump(), "github", state, 0) == 1
    imported = backlog["tickets"]["GITHUB-17"]
    assert imported["id"] == "GITHUB-17"

    pf.store.save_backlog(backlog)
    assert pf.get_ticket("GITHUB-17").name == "Imported issue"


def test_existing_custom_sprint_is_updated_in_place():
    sections = {
        "custom-review": {
            "tickets": {
                "PLF-9": {
                    "id": "PLF-9",
                    "name": "old",
                    "integration": ["github"],
                    "sync": {"github": {"id": "9"}},
                }
            }
        },
        "current": {"tickets": {}},
        "backlog": {"tickets": {}},
    }
    state = FakeState()
    state.save_sync({"PLF-9": "9"})
    external = SimpleNamespace(
        id="9",
        name="new",
        description="fresh",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/9",
        key="owner/repo#9",
        metadata={},
    )

    imported, updated = _process_external_ticket(
        external,
        sections["current"],
        sections["backlog"],
        state,
        "github",
        False,
        0,
        0,
        sections=sections,
    )

    assert (imported, updated) == (0, 1)
    assert sections["custom-review"]["tickets"]["PLF-9"]["name"] == "new"


def test_outbound_custom_sprint_mapping_is_persisted(tmp_path):
    store = Store(tmp_path)
    store.init()
    ticket = {
        "id": "PLF-7",
        "name": "custom ticket",
        "description": "keep the source sprint",
        "status": "open",
        "integration": ["github"],
    }
    store.save_sprint("custom-review", {"tickets": {"PLF-7": ticket}})

    class Backend:
        config = {"repo": "owner/repo"}

        def create_ticket(self, payload):
            return SimpleNamespace(
                id="31", url="https://github.com/owner/repo/issues/31", key="owner/repo#31"
            )

    sync_to_external(
        Backend(), [("PLF-7", ticket)], False, store, "github"
    )

    saved = store.load_sprint("custom-review")["tickets"]["PLF-7"]
    assert saved["sync"]["github"]["id"] == "31"
    assert saved["sync"]["github"]["repository"] == "owner/repo"


def test_outbound_rejects_ticket_bound_to_another_repository(tmp_path):
    store = Store(tmp_path)
    store.init()
    ticket = {
        "id": "PLF-8",
        "name": "wrong repo",
        "integration": ["github"],
        "sync": {"github": {"repository": "other/repo", "id": "8"}},
    }

    class Backend:
        config = {"repo": "owner/repo"}

        def update_ticket(self, *args, **kwargs):
            raise AssertionError("must fail before remote mutation")

    try:
        sync_to_external(Backend(), [("PLF-8", ticket)], False, store, "github")
    except Exception as error:
        assert "failed for 1 ticket" in str(error)
    else:
        raise AssertionError("cross-repository mapping was accepted")


def test_inbound_sprint_scope_imports_into_selected_sprint():
    sections = {
        "custom-review": {"tickets": {}},
        "backlog": {"tickets": {}},
        "current": {"tickets": {}},
    }
    external = SimpleNamespace(
        id="44",
        name="scoped issue",
        description="only custom sprint",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/44",
        key="owner/repo#44",
        metadata={},
    )

    imported, updated = _process_external_ticket(
        external,
        sections["current"],
        sections["backlog"],
        FakeState(),
        "github",
        False,
        0,
        0,
        sections=sections,
        import_target=sections["custom-review"],
    )

    assert (imported, updated) == (1, 0)
    assert "GITHUB-44" in sections["custom-review"]["tickets"]
    assert "GITHUB-44" not in sections["backlog"]["tickets"]
