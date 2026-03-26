# Planfile TODO List

## Completed Tasks
- [x] Identify and remove unnecessary and generated files (`htmlcov/`, `.coverage`, etc.)
- [x] Organize generated markdown summaries into `docs/summaries/` directory
- [x] Run projects in `examples/*` to ensure base correctness
- [x] Refactor `planfile/analysis/file_analyzer.py` (God module)
- [x] Refactor `planfile/analysis/generator.py` (God module)
- [x] Refactor `planfile/cli/commands.py` (God module)
- [x] Split highest-CC functions (e.g., `_analyze_toon`, `_extract_key_metrics`)
- [x] Preserve module boundaries and update imports/exports as per `map.toon.yaml`

## Pending Improvements
- [ ] Implement `--version` flag for the CLI to display the current version.
- [ ] Add an extensible Backend Registry to remove complex `if/elif` statements when creating integrations.
