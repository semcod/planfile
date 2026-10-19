# planfile-native

Rust storage kernel for [planfile](../../README.md). It removes the write-path
bottleneck measured in `benches/bench_store.py`: every ticket mutation re-serialized the whole
sprint file with PyYAML and then re-walked it to build the JSON mirror.

| Function | Replaces | Contract |
|---|---|---|
| `dump_yaml(data, allow_unicode)` | `yaml.dump(..., Dumper=CSafeDumper, default_flow_style=False)` | byte-identical output |
| `dump_json(data)` | `json.dumps(_json_safe(data), ensure_ascii=False)` | byte-identical output |
| `write_sprint(path, data, ...)` | `_write_yaml_atomic` (dump, tmp, fsync, rename, stat, mirror) | one call, files `0600` |
| `normalize(value)` | `fastio._json_safe` | same result and types |
| `atomic_write_text(path, text)` | `fastio._atomic_write_text` | same semantics |

YAML stays the single source of truth. The emitter is a port of libyaml 0.2.5's block emitter
(`src/yaml.rs`, function names follow `emitter.c`) and the PyYAML implicit resolver
(`src/resolver.rs`), because sprint files live in users' repositories and any formatting change
would be a whole-file git diff.

## Fail-closed fallback

The extension accepts only what `yaml.SafeDumper` represents by *exact* type (`dict` with `str`
keys, `list`, `tuple`, `str`, `int`, `float`, `bool`, `None`, `date`, `datetime`). A subclass,
`set`, `bytes`, a container referenced twice (PyYAML would emit anchors), a cycle or a lone
surrogate raises `planfile_native.Unsupported` **before any file is touched**. planfile then runs
its pure-Python path, so behavior and errors are unchanged.

## Runtime switches (no hardcoded policy)

Read by `planfile/core/native.py`, not by the crate:

| Variable | Values | Default |
|---|---|---|
| `PLANFILE_NATIVE` | `auto` use when importable, `off` never, `verify` use and compare with PyYAML, raise on mismatch | `auto` |
| `PLANFILE_NATIVE_FSYNC` | `1` / `0`, durability of the write | `1` |

## Build and test

```bash
cd packages/planfile-native
cargo test                       # unit tests
maturin develop --release        # install into the active venv
pytest tests                     # differential tests against PyYAML
python benches/bench_store.py 3000
```

`planfile` imports `planfile_native` optionally; it is not a hard dependency.

## Standards alignment

- `wellmanifest/performance`: evidence-bound change; baseline and candidate come from the same
  workload (`benches/bench_store.py`), invariants are the parity tests, rollback is
  `PLANFILE_NATIVE=off`.
- `wellmanifest/nohardcode`: policy (enable, fsync, mirror version and suffix) is injected from
  Python or the environment, nothing is baked into the crate.
- `wellmanifest/data-plane` / `data-gateway`: see "Data-plane alignment" below.

## Data-plane alignment

planfile's storage follows the `sqlite-embedded-es-v1` shape of `wellmanifest/data-plane` only
in spirit: YAML sprint files are the authoritative writer per stream and the SQLite ticket index
(`planfile/core/sqlite_index.py`) is a rebuildable projection. This package is the single
*storage kernel* every write goes through (one operation layer, one authoritative writer, one
atomic commit point), which is the boundary a data-plane/data-gateway adapter would call.
It does **not** introduce an event store and does not change the source of truth; moving
planfile to event sourcing with YAML and SQLite as projections is a separate, larger decision.
The `data-gateway` one-line `typ: obiekt {zmienne}` format is not implemented here either.
