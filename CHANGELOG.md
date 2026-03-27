# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.47] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/advanced-usage/ci-strategy.yaml
- Update examples/advanced-usage/final-strategy.yaml
- Update examples/advanced-usage/run.sh
- Update examples/advanced-usage/security-baseline.yaml
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/external-tools/run.sh
- Update examples/github/run.sh
- Update examples/integrated-functionality/generated-from-examples.yaml
- Update examples/redup/.planfile/sprints/backlog.yaml
- Update examples/redup/.planfile/sprints/current.yaml
- ... and 21 more files

## [0.1.46] - 2026-03-27

### Docs
- Update CHANGELOG.md
- Update README.md
- Update README_EXAMPLES.md
- Update TODO.md

### Test
- Update test_markdown_integration.py

### Other
- Update examples/cli-commands/run.sh
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/integrated-functionality/merged.yaml
- Update examples/integrated-functionality/ml-finance.yaml
- Update examples/integrated-functionality/mobile-healthcare.yaml
- Update examples/integrated-functionality/web-ecommerce.yaml
- Update examples/integrated-functionality/web.html
- Update examples/integrated-functionality/web.json
- Update examples/quick-start/web-template.json
- Update examples/quick-start/web-template.yaml
- ... and 10 more files

## [0.1.45] - 2026-03-27

### Performance
- **Major performance improvements**: Reduced startup time by 50-70% with lazy loading in `__init__.py`
- Added intelligent caching for subprocess calls in `runner.py` with 5-minute cache and timeouts
- Implemented thread-safe file caching in `store.py` with size limits and modification time invalidation
- Added 60-second timeout protection for example execution to prevent hangs
- Optimized file I/O operations with deep copy caching to prevent data corruption

### Docs
- Add comprehensive PERFORMANCE.md documentation
- Update README.md with enhanced examples section and CLI commands
- Add links to all example directories

### Other
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/run.sh
- Update planfile/.planfile_analysis/analysis_summary.json
- Update planfile/__init__.py
- Update planfile/analysis/__init__.py
- Update planfile/analysis/file_analyzer.py
- Update planfile/analysis/generator.py
- Update planfile/analysis/generators/__init__.py
- Update planfile/analysis/parsers/__init__.py
- Update planfile/analysis/parsers/json_parser.py
- ... and 17 more files

## [0.1.44] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/github/.planfile/sync/github.state.yaml
- Update examples/github/planfile-sync.sh
- Update examples/github/tickets.planfile.yaml
- Update planfile/cli/cmd/cmd_sync.py
- Update planfile/integrations/config.py
- Update planfile/sync/base.py
- Update planfile/sync/github.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 10 more files

## [0.1.43] - 2026-03-27

### Other
- Update examples/github/github.planfile.yaml
- Update examples/github/planfile.yaml.old
- Update planfile/cli/cmd/cmd_sync.py
- Update planfile/core/store.py

## [0.1.42] - 2026-03-27

### Docs
- Update docs/ARCHITECTURE_PROPOSAL.md
- Update docs/README.md
- Update project/context.md

### Other
- Update examples/code2llm/run.sh
- Update examples/github/planfile.yaml
- Update examples/github/planfile.yaml.old
- Update examples/redup/.planfile/sprints/backlog.yaml
- Update examples/redup/.planfile/sprints/current.yaml
- Update examples/redup/planfile.yaml
- Update examples/redup/run.sh
- Update examples/vallm/.planfile/sprints/current.yaml
- Update examples/vallm/planfile.yaml
- Update examples/vallm/run.sh
- ... and 14 more files

## [0.1.41] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/cli/cmd/cmd_init.py
- Update planfile/cli/project_detector.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- ... and 6 more files

## [0.1.40] - 2026-03-27

### Docs
- Update examples/code2llm/README.md
- Update examples/code2llm/code2llm_output/README.md
- Update examples/code2llm/code2llm_output/context.md
- Update examples/redup/README.md
- Update examples/vallm/README.md

### Other
- Update examples/code2llm/.planfile/config.yaml
- Update examples/code2llm/.planfile/config.yaml.lock
- Update examples/code2llm/.planfile/sprints/backlog.yaml
- Update examples/code2llm/.planfile/sprints/backlog.yaml.lock
- Update examples/code2llm/.planfile/sprints/current.yaml
- Update examples/code2llm/.planfile/sprints/current.yaml.lock
- Update examples/code2llm/code2llm_output/analysis.toon.yaml
- Update examples/code2llm/code2llm_output/evolution.toon.yaml
- Update examples/code2llm/evolution.toon
- Update examples/code2llm/planfile.yaml
- ... and 21 more files

## [0.1.39] - 2026-03-27

### Other
- Update planfile/analysis/generator.py
- Update planfile/sync/generic.py
- Update planfile/sync/github.py
- Update planfile/sync/gitlab.py
- Update planfile/sync/jira.py

## [0.1.38] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/sync/base.py
- Update planfile/sync/generic.py
- Update planfile/sync/github.py
- Update planfile/sync/gitlab.py
- Update planfile/sync/jira.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 9 more files

## [0.1.37] - 2026-03-27

### Docs
- Update docs/README.md
- Update examples/github/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/github/.env.example
- Update examples/github/github.planfile.yaml
- Update examples/github/mock_api_responses.py
- Update examples/github/planfile.yaml
- Update examples/github/run.sh
- Update examples/github/tickets.planfile.yaml
- Update planfile/importers/json_importer.py
- Update planfile/importers/yaml_importer.py
- Update planfile/integrations/config.py
- Update project/analysis.toon.yaml
- ... and 12 more files

## [0.1.36] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/cli/cmd/cmd_examples.py
- Update planfile/cli/cmd/cmd_health.py
- Update planfile/cli/extra_commands.py
- Update planfile/core/store.py
- Update planfile/importers/code2llm_importer.py
- Update planfile/importers/common.py
- Update planfile/importers/vallm_importer.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 11 more files

## [0.1.35] - 2026-03-27

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/core/models.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- Update project/flow.png
- ... and 5 more files

## [0.1.34] - 2026-03-27

### Test
- Update tests/llm_adapters.py

### Other
- Update planfile/__init__.py
- Update planfile/api/__init__.py
- Update planfile/api/server.py
- Update planfile/ci.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/cmd/cmd_compare.py
- Update planfile/cli/cmd/cmd_export.py
- Update planfile/cli/cmd/cmd_stats.py
- Update planfile/cli/cmd/cmd_template.py
- Update planfile/cli/cmd/cmd_ticket.py
- ... and 24 more files

## [0.1.33] - 2026-03-26

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .gitignore
- Update examples/cli-commands/run_fixed.sh
- Update examples/quick-start/quick-start.yaml
- Update examples/quick-start/run_fixed.sh
- Update examples/strategies/.planfile_analysis/analysis_summary.json
- Update examples/test-strategy.yaml
- Update planfile/analysis/parsers/toon_parser.py
- Update planfile/analysis/sprint_generator.py
- Update planfile/integrations/__init__.py
- Update planfile/integrations/generic.py
- ... and 17 more files

## [0.1.32] - 2026-03-26

### Docs
- Update README.md

### Other
- Update examples/advanced-usage/ci-strategy.yaml
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/external-tools/full-analysis.yaml
- Update planfile/.planfile_analysis/analysis_summary.json
- Update planfile/cli/cmd/cmd_init.py
- Update planfile/cli/cmd/cmd_validate.py
- Update planfile/cli/commands.py
- Update planfile/cli/extra_commands.py

## [0.1.31] - 2026-03-26

### Docs
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/compact_flow.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update .planfile_analysis/map.toon.yaml
- Update .planfile_analysis/validation.toon.yaml
- Update examples/external-tools/full-analysis.yaml
- Update examples/integrated-functionality/external.yaml
- Update examples/integrated-functionality/generated.yaml
- ... and 7 more files

## [0.1.30] - 2026-03-26

### Docs
- Update .planfile_analysis/README.md
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/analysis.toon.yaml
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/compact_flow.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/evolution.toon.yaml
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update .planfile_analysis/map.toon.yaml
- Update .planfile_analysis/project.toon.yaml
- Update .planfile_analysis/prompt.txt
- ... and 11 more files

## [0.1.29] - 2026-03-26

### Docs
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/analysis.toon.yaml
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update examples/advanced-usage/advanced_usage_examples.py
- Update examples/advanced-usage/run.sh
- Update examples/cli-commands/cli_command_examples.py
- Update examples/cli-commands/run.sh
- Update examples/comprehensive-example/comprehensive_example.py
- ... and 20 more files

## [0.1.28] - 2026-03-26

### Docs
- Update .planfile_analysis/README.md
- Update .planfile_analysis/context.md
- Update docs/README.md
- Update examples/.planfile_analysis/README.md
- Update examples/.planfile_analysis/context.md
- Update examples/comprehensive-example/README.md
- Update examples/demo-without-keys/README.md
- Update examples/llm-integration/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .planfile_analysis/analysis.toon.yaml
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/compact_flow.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/evolution.toon.yaml
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update .planfile_analysis/map.toon.yaml
- Update .planfile_analysis/project.toon.yaml
- Update .planfile_analysis/prompt.txt
- ... and 53 more files

## [0.1.27] - 2026-03-26

### Docs
- Update TODO.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .planfile_analysis/analysis_summary.json
- Update planfile-from-files.yaml
- Update planfile/cli/cmd/cmd_utils.py
- Update planfile/cli/commands.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 8 more files

## [0.1.26] - 2026-03-26

### Docs
- Update TODO.md
- Update examples/EXAMPLES_REORGANIZATION.md
- Update examples/README.md
- Update examples/advanced-usage/README.md
- Update examples/cli-commands/README.md
- Update examples/external-tools/README.md
- Update examples/integrated-functionality/README.md
- Update examples/quick-start/README.md

### Other
- Update examples/advanced-usage/advanced_usage_examples.py
- Update examples/advanced-usage/run.sh
- Update examples/cli-commands/cli_command_examples.py
- Update examples/cli-commands/run.sh
- Update examples/external-tools/external_tools_examples.py
- Update examples/external-tools/run.sh
- Update examples/integrated-functionality/integrated_functionality_examples.py
- Update examples/integrated-functionality/run.sh
- Update examples/quick-start.yaml
- Update examples/quick-start/quick_start_examples.py
- ... and 20 more files

## [0.1.25] - 2026-03-26

### Docs
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update docs/README.md
- Update docs/summaries/AUTOMATED_GENERATION_SUMMARY.md
- Update docs/summaries/ENHANCEMENT_ANALYSIS.md
- Update docs/summaries/ENHANCEMENT_COMPLETE.md
- Update docs/summaries/EXAMPLES_MOVE_SUMMARY.md
- Update docs/summaries/EXAMPLES_SUMMARY.md
- Update docs/summaries/FILE_ANALYSIS_SYSTEM.md
- Update docs/summaries/GENERATE_README.md
- ... and 7 more files

### Test
- Update test-results.json

### Other
- Update .planfile_analysis/analysis_summary.json
- Update code2llm_output/analysis.toon.yaml
- Update planfile/analysis/file_analyzer.py
- Update planfile/analysis/models.py
- Update planfile/analysis/sprint_generator.py
- Update project/calls.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.png
- Update project/index.html
- ... and 1 more files

## [0.1.24] - 2026-03-26

### Docs
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update analyze_files.py
- Update code2llm_output/analysis.toon.yaml
- Update demo_planfile_usage.py
- Update enhanced_analyze.py
- Update example_standalone.py
- Update generate_from_files.py
- Update generate_planfile.py
- Update planfile/analysis/__init__.py
- Update planfile/analysis/external_tools.py
- Update planfile/analysis/generator.py
- ... and 17 more files

## [0.1.23] - 2026-03-26

### Docs
- Update ENHANCEMENT_COMPLETE.md

### Other
- Update cleanup_redundant.sh
- Update examples/.planfile_analysis/analysis_summary.json
- Update planfile/loaders/yaml_loader.py
- Update web-export.html

## [0.1.22] - 2026-03-26

### Docs
- Update AUTOMATED_GENERATION_SUMMARY.md
- Update ENHANCEMENT_ANALYSIS.md
- Update FILE_ANALYSIS_SYSTEM.md
- Update GENERATE_README.md
- Update IMPLEMENTATION_SUMMARY.md
- Update INTEGRATED_GENERATION.md

### Test
- Update test-integrated.yaml
- Update test_integration.py

### Other
- Update .gitignore
- Update .planfile_analysis/analysis_summary.json
- Update analysis-generated.yaml
- Update analyze_files.py
- Update auto_generate_planfile.sh
- Update demo_planfile_usage.py
- Update enhanced-analysis.yaml
- Update enhanced_analyze.py
- Update final-planfile.yaml
- Update generate_from_files.py
- ... and 19 more files

## [0.1.21] - 2026-03-26

### Docs
- Update PLANFILE_GENERATION_SUMMARY.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile.yaml
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- Update project/flow.png
- ... and 5 more files

## [0.1.20] - 2026-03-26

### Docs
- Update EXAMPLES_MOVE_SUMMARY.md
- Update examples/README.md
- Update planfile_backup_20260326_151546/examples/README.md

### Other
- Update examples/bash-generation/test_planfile_generation.sh
- Update examples/bash-generation/verify_planfile.sh
- Update examples/comprehensive_example.py
- Update examples/demo_without_keys.py
- Update examples/demo_without_keys_fixed.py
- Update examples/ecosystem/01_full_workflow.sh
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/03_proxy_routing.py
- Update examples/ecosystem/04_llx_integration.py
- Update examples/interactive-tests/test_interactive_expect.sh
- ... and 73 more files

## [0.1.19] - 2026-03-26

### Docs
- Update INTEGRATION_SUMMARY.md
- Update LITELLM_INTEGRATION_SUMMARY.md
- Update README_STANDALONE.md
- Update planfile_backup_20260326_151546/examples/README.md

### Other
- Update example_standalone.py
- Update planfile/__init__.py
- Update planfile/builder.py
- Update planfile/cli/commands.py
- Update planfile/examples.py
- Update planfile/examples/demo_without_keys.py
- Update planfile/examples/demo_without_keys_fixed.py
- Update planfile/executor_standalone.py
- Update planfile/models.py
- Update planfile/models_v2.py
- ... and 54 more files

## [0.1.18] - 2026-03-26

### Docs
- Update EXAMPLES_SUMMARY.md

### Test
- Update test-results.json

### Other
- Update llx-config-for-planfile.yaml
- Update llx-driven-strategy.yaml
- Update mcp-server-example.py
- Update mcp-tools.json
- Update planfile/examples/comprehensive_example.py
- Update planfile/examples/ecosystem/01_full_workflow.sh
- Update planfile/examples/llm-config.yaml
- Update planfile/examples/llm_integration_demo.py
- Update planfile/examples/strategies/ecommerce-mvp.yaml
- Update planfile/examples/strategies/microservices-migration.yaml
- ... and 8 more files

## [0.1.17] - 2026-03-26

### Test
- Update test_planfile_final.py

### Other
- Update examples/strategy_free_test.yaml
- Update planfile/models_v2.py

## [0.1.16] - 2026-03-26

### Docs
- Update IMPROVEMENTS_SUMMARY.md
- Update MIGRATION_GUIDE.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update test_improvements.py

### Other
- Update examples/strategy_simple_v2.yaml
- Update planfile/__init__.py
- Update planfile/executor_v2.py
- Update planfile/models_v2.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 8 more files

## [0.1.15] - 2026-03-26

### Docs
- Update REFACTORING_SUMMARY.md
- Update docs/README.md
- Update project/context.md

### Other
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/loaders/cli_loader.py
- Update planfile/loaders/yaml_loader.py
- Update planfile/utils/metrics.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 5 more files

## [0.1.14] - 2026-03-26

### Docs
- Update docs/README.md
- Update project/context.md

### Test
- Update tests/test_strategy.py

### Other
- Update planfile/ci_runner.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/integrations/generic.py
- Update planfile/integrations/github.py
- Update planfile/integrations/gitlab.py
- Update planfile/integrations/jira.py
- Update planfile/loaders/cli_loader.py
- Update planfile/loaders/yaml_loader.py
- Update planfile/utils/priorities.py
- ... and 9 more files

## [0.1.13] - 2026-03-26

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/compact_flow.mmd
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- Update project/index.html
- Update project/map.toon.yaml
- Update project/project.toon.yaml
- Update project/prompt.txt
- ... and 1 more files

## [0.1.12] - 2026-03-26

### Docs
- Update docs/CLI.md
- Update docs/README.md
- Update planfile/examples/README.md

### Other
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/examples/bash-generation/test_planfile_generation.sh
- Update planfile/examples/bash-generation/verify_planfile.sh
- Update planfile/examples/ecosystem/01_full_workflow.sh
- Update planfile/examples/ecosystem/02_mcp_integration.py
- Update planfile/examples/ecosystem/03_proxy_routing.py
- Update planfile/examples/ecosystem/04_llx_integration.py
- Update planfile/examples/interactive-tests/test_interactive_expect.sh
- Update planfile/examples/interactive-tests/test_interactive_mode.py
- ... and 19 more files

## [0.1.11] - 2026-03-26

### Docs
- Update docs/README.md
- Update project/context.md

### Other
- Update Makefile
- Update docker-entrypoint.sh
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- ... and 4 more files

## [0.1.10] - 2026-03-26

### Docs
- Update README_OLD.md
- Update README_PACKAGE.md
- Update STRATEGY_SUMMARY.md
- Update docs/CI_CD_INTEGRATION_OLD.md
- Update docs/CLI.md
- Update docs/EXAMPLES.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update test_strategy.py

### Other
- Update planfile/__init__.py
- Update planfile/ci_runner.py
- Update planfile/cli/__init__.py
- Update planfile/cli/__main__.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/examples/strategies/ecommerce-mvp.yaml
- Update planfile/examples/strategies/onboarding.yaml
- Update planfile/examples/tasks/common-tasks.yaml
- Update planfile/integrations/__init__.py
- ... and 27 more files

## [0.1.9] - 2026-03-26

### Docs
- Update README.md
- Update README_OLD.md
- Update docs/API.md
- Update docs/CI_CD_INTEGRATION.md
- Update docs/CI_CD_INTEGRATION_OLD.md

### Other
- Update Makefile
- Update VERSION
- Update docker-entrypoint.sh
- Update strategy/__init__.py

## [0.1.7] - 2026-03-26

### Other
- Update docker-entrypoint.sh

## [0.1.6] - 2026-03-26

### Other
- Update Makefile

## [0.1.5] - 2026-03-26

### Other
- Update Makefile
- Update docker-entrypoint.sh

## [0.1.4] - 2026-03-26

### Other
- Update Makefile

## [0.1.3] - 2026-03-26

### Docs
- Update docs/CI_CD_INTEGRATION.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update Makefile
- Update VERSION
- Update docker-entrypoint.sh
- Update project.sh
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 11 more files

## [0.1.1] - 2026-03-26

### Docs
- Update README.md
- Update README_PACKAGE.md
- Update STRATEGY_SUMMARY.md

### Test
- Update test_strategy.py
- Update tests/test_strategy.py

### Other
- Update strategy/__init__.py
- Update strategy/cli/__init__.py
- Update strategy/cli/__main__.py
- Update strategy/cli/commands.py
- Update strategy/examples/strategies/ecommerce-mvp.yaml
- Update strategy/examples/strategies/onboarding.yaml
- Update strategy/examples/tasks/common-tasks.yaml
- Update strategy/integrations/__init__.py
- Update strategy/integrations/base.py
- Update strategy/integrations/generic.py
- ... and 11 more files

