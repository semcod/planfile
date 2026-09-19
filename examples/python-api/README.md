# Python Library API Examples

Run these synchronous demonstrations with Planfile installed in your Python environment:

```bash
python examples/python-api/01_basic_usage.py
bash examples/python-api/run_all.sh
```

Each script creates a fresh temporary `.planfile` store, then removes it on exit.
The runner does not install packages or synchronize external integrations.
`demo_store.py` also isolates calls to the decorated example functions when imported.
Nested examples share the current demonstration store; separate runs start fresh.
The helper temporarily changes the process working directory and is intended for
these synchronous examples, not concurrent application code.

- `01_basic_usage.py`: initialization, ticket creation and the `quick_ticket` helper.
- `02_ticket_management.py`: create, read, update, bulk import and sprint moves.
- `03_integration.py` and `03_integration_simple.py`: logger and error decorators.
- `04_advanced_filtering.py` and `04_analytics_simple.py`: filtering and exports.
- `05_dsl_usage.py`: parsing and local DSL operations.

Select a specific interpreter with `PYTHON=/path/to/python bash examples/python-api/run_all.sh`.
To retain real tickets in an application, initialize Planfile for an explicit project
and use its current API (`name` for ticket names). Do not copy the disposable-store
wrapper into application lifecycle code. Existing project queues are never cleaned
or migrated by these demonstrations.
