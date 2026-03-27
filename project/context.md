# System Architecture Analysis

## Overview

- **Project**: /home/tom/github/semcod/planfile
- **Primary Language**: python
- **Languages**: python: 77, shell: 20, javascript: 1
- **Analysis Mode**: static
- **Total Functions**: 474
- **Total Classes**: 60
- **Modules**: 98
- **Entry Points**: 371

## Architecture by Module

### examples.htmlcov.coverage_html_cb_dd2e7eb5
- **Functions**: 77
- **File**: `coverage_html_cb_dd2e7eb5.js`

### planfile.analysis.generator
- **Functions**: 17
- **Classes**: 1
- **File**: `generator.py`

### planfile.core.models
- **Functions**: 17
- **Classes**: 11
- **File**: `models.py`

### examples.ecosystem.01_full_workflow
- **Functions**: 17
- **Classes**: 6
- **File**: `01_full_workflow.sh`

### planfile.loaders.yaml_loader
- **Functions**: 15
- **File**: `yaml_loader.py`

### planfile.core.store
- **Functions**: 15
- **Classes**: 1
- **File**: `store.py`

### planfile.analysis.external_tools
- **Functions**: 13
- **Classes**: 2
- **File**: `external_tools.py`

### run_examples
- **Functions**: 13
- **File**: `run_examples.sh`

### planfile.executor_standalone
- **Functions**: 12
- **Classes**: 3
- **File**: `executor_standalone.py`

### planfile.loaders.cli_loader
- **Functions**: 10
- **File**: `cli_loader.py`

### planfile.analysis.file_analyzer
- **Functions**: 10
- **Classes**: 1
- **File**: `file_analyzer.py`

### planfile.analysis.sprint_generator
- **Functions**: 10
- **Classes**: 1
- **File**: `sprint_generator.py`

### planfile.analysis.parsers.toon_parser
- **Functions**: 10
- **File**: `toon_parser.py`

### planfile.sync.jira
- **Functions**: 9
- **Classes**: 1
- **File**: `jira.py`

### planfile.sync.generic
- **Functions**: 9
- **Classes**: 1
- **File**: `generic.py`

### planfile.ci
- **Functions**: 9
- **Classes**: 3
- **File**: `ci.py`

### planfile.cli.auto_loop
- **Functions**: 9
- **File**: `auto_loop.py`

### planfile.integrations.jira
- **Functions**: 9
- **Classes**: 1
- **File**: `jira.py`

### planfile.integrations.generic
- **Functions**: 9
- **Classes**: 1
- **File**: `generic.py`

### planfile.sync.base
- **Functions**: 9
- **Classes**: 4
- **File**: `base.py`

## Key Entry Points

Main execution flows into the system:

### planfile.cli.extra_commands.add_extra_commands
> Add health and examples commands to the CLI app.
- **Calls**: app.command, typer.Typer, examples_app.command, examples_app.command, app.add_typer, typer.Argument, _get_examples_dir, examples_dir.iterdir

### planfile.cli.cmd.cmd_ticket.register_ticket_commands
> Register ticket subcommands on the typer app.
- **Calls**: typer.Typer, ticket_app.command, ticket_app.command, ticket_app.command, ticket_app.command, ticket_app.command, ticket_app.command, app.add_typer

### planfile.cli.cmd.cmd_init.init_strategy_cli
> Interactive wizard — tworzy strategię przez zadawanie pytań.

Nie wymaga szablonu. Pyta o typ projektu, cele, sprinty i bramki jakości.
- **Calls**: typer.Option, typer.Option, console.print, planfile.cli.cmd.cmd_init._ask, planfile.cli.cmd.cmd_init._ask, planfile.cli.cmd.cmd_init._choice, planfile.cli.cmd.cmd_init._ask, planfile.cli.cmd.cmd_init._ask

### examples.ecosystem.04_llx_integration.example_metric_driven_planning
> Example: Generate strategy based on actual project metrics.
- **Calls**: examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, LLXIntegration, examples.bash-generation.verify_planfile.print, llx.analyze_project, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print

### examples.ecosystem.03_proxy_routing.example_strategy_generation_with_proxy
> Example: Generate strategy using proxy for smart model routing.
- **Calls**: examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, ProxyClient, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, enumerate

### planfile.cli.cmd.cmd_generate.generate_from_files_cmd
> Generate planfile from file analysis (no LLM required).
- **Calls**: typer.Argument, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option

### planfile.cli.cmd.cmd_review.review_strategy_cli
> Review strategy execution and progress.
- **Calls**: typer.Argument, typer.Argument, typer.Option, typer.Option, typer.Option, typer.Option, planfile.cli.cmd.cmd_utils._load_backend_config, planfile.runner.review_strategy

### planfile.cli.auto_loop.auto_loop
> Run automated CI/CD loop: test → ticket → fix → retest.

This command will:
1. Run tests and code analysis
2. If tests fail, generate bug reports with
- **Calls**: app.command, typer.Argument, typer.Argument, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option

### planfile.cli.cmd.cmd_export.register_export_commands
> Register export and merge commands on the typer app.
- **Calls**: app.command, app.command, typer.Argument, typer.Option, typer.Option, typer.Argument, typer.Option, typer.Option

### planfile.cli.auto_loop.ci_status
> Check current CI status without running tests.
- **Calls**: app.command, typer.Argument, console.print, results_file.exists, coverage_file.exists, list, json.loads, console.print

### examples.ecosystem.02_mcp_integration.example_mcp_session
> Example of an LLM agent using planfile MCP tools.
- **Calls**: examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.ecosystem.02_mcp_integration.run_mcp_tool

### examples.ecosystem.04_llx_integration.LLXIntegration._parse_llx_output
> Parse LLX analysis output.
- **Calls**: None.split, ProjectMetrics, output.strip, line.split, value.strip, int, int, float

### planfile.cli.cmd.cmd_stats.register_stats_commands
> Register stats command on the typer app.
- **Calls**: app.command, typer.Argument, planfile.loaders.yaml_loader.load_strategy_yaml, planfile.cli.cmd.cmd_stats.calculate_strategy_stats, Table, table.add_column, table.add_column, table.add_row

### planfile.core.models.Strategy.merge
> Merge with other strategies to create a combined strategy.
- **Calls**: self.model_dump, set, merged_data.get, Strategy, merged_data.get, all_sprints.append, merged_data.get, all_gates.append

### planfile.cli.cmd.cmd_compare.register_compare_commands
> Register compare command on the typer app.
- **Calls**: app.command, typer.Argument, typer.Argument, typer.Option, planfile.loaders.yaml_loader.load_strategy_yaml, planfile.loaders.yaml_loader.load_strategy_yaml, planfile.cli.cmd.cmd_compare.compare_strategies, console.print

### planfile.cli.cmd.cmd_validate.validate_strategy_cli
> Validate a strategy YAML file.
- **Calls**: typer.Argument, typer.Option, planfile.loaders.yaml_loader.load_strategy_yaml, console.print, console.print, console.print, console.print, console.print

### planfile.core.models.Strategy.to_llx_format
> Convert to LLX-compatible format.
- **Calls**: self.model_dump, isinstance, data.get, data.get, isinstance, data.get, goal.setdefault, goal.setdefault

### planfile.cli.cmd.cmd_apply.apply_strategy_cli
> Apply a strategy to create tickets.
- **Calls**: typer.Argument, typer.Argument, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option

### planfile.cli.cmd.cmd_generate.generate_strategy_cli
> Generate strategy.yaml from project analysis + LLM.
- **Calls**: typer.Argument, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option, typer.Option, console.print

### planfile.core.models.Strategy.get_stats
> Get strategy statistics.
- **Calls**: len, sum, len, sum, isinstance, hasattr, durations.append, sum

### examples.ecosystem.03_proxy_routing.example_budget_tracking
> Example: Budget tracking with proxy.
- **Calls**: examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, ProxyClient, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print

### planfile.analysis.external_tools.ExternalToolRunner.parse_code2llm_output
> Parse code2llm analysis.toon.yaml output.
- **Calls**: content.split, AnalysisResults, re.search, re.search, analysis_file.exists, self._mock_code2llm_data, open, f.read

### planfile.analysis.parsers.toon_parser._parse_summary_section
> Parse summary section for metrics.
- **Calls**: re.search, re.search, metrics.append, int, metrics.append, issues.append, ExtractedMetric, int

### planfile.core.models.Sprint.convert_tasks
- **Calls**: field_validator, isinstance, isinstance, isinstance, tasks.append, isinstance, tasks.append, tasks.append

### planfile.analysis.generator.PlanfileGenerator.generate_from_analysis
> Generate planfile from analyzed files.
- **Calls**: self.analyzer.analyze_directory, self.generator.generate_sprints, self.generator.generate_tickets, self._extract_key_metrics, self._create_strategy_object, Path, self._generate_goal, self._generate_goals

### examples.htmlcov.coverage_html_cb_dd2e7eb5.sortColumn
- **Calls**: examples.htmlcov.coverage_html_cb_dd2e7eb5.getAttribute, examples.htmlcov.coverage_html_cb_dd2e7eb5.forEach, examples.htmlcov.coverage_html_cb_dd2e7eb5.setAttribute, examples.htmlcov.coverage_html_cb_dd2e7eb5.indexOf, examples.htmlcov.coverage_html_cb_dd2e7eb5.from, examples.htmlcov.coverage_html_cb_dd2e7eb5.closest, examples.htmlcov.coverage_html_cb_dd2e7eb5.querySelectorAll, examples.htmlcov.coverage_html_cb_dd2e7eb5.sort

### examples.htmlcov.coverage_html_cb_dd2e7eb5.table
- **Calls**: examples.htmlcov.coverage_html_cb_dd2e7eb5.map, examples.htmlcov.coverage_html_cb_dd2e7eb5.getElementById, examples.htmlcov.coverage_html_cb_dd2e7eb5.setItem, examples.htmlcov.coverage_html_cb_dd2e7eb5.toLowerCase, examples.htmlcov.coverage_html_cb_dd2e7eb5.stringify, examples.htmlcov.coverage_html_cb_dd2e7eb5.forEach, examples.htmlcov.coverage_html_cb_dd2e7eb5.contains, examples.htmlcov.coverage_html_cb_dd2e7eb5.includes

### examples.htmlcov.coverage_html_cb_dd2e7eb5.table_body_rows
- **Calls**: examples.htmlcov.coverage_html_cb_dd2e7eb5.map, examples.htmlcov.coverage_html_cb_dd2e7eb5.getElementById, examples.htmlcov.coverage_html_cb_dd2e7eb5.setItem, examples.htmlcov.coverage_html_cb_dd2e7eb5.toLowerCase, examples.htmlcov.coverage_html_cb_dd2e7eb5.stringify, examples.htmlcov.coverage_html_cb_dd2e7eb5.forEach, examples.htmlcov.coverage_html_cb_dd2e7eb5.contains, examples.htmlcov.coverage_html_cb_dd2e7eb5.includes

### examples.htmlcov.coverage_html_cb_dd2e7eb5.no_rows
- **Calls**: examples.htmlcov.coverage_html_cb_dd2e7eb5.map, examples.htmlcov.coverage_html_cb_dd2e7eb5.getElementById, examples.htmlcov.coverage_html_cb_dd2e7eb5.setItem, examples.htmlcov.coverage_html_cb_dd2e7eb5.toLowerCase, examples.htmlcov.coverage_html_cb_dd2e7eb5.stringify, examples.htmlcov.coverage_html_cb_dd2e7eb5.forEach, examples.htmlcov.coverage_html_cb_dd2e7eb5.contains, examples.htmlcov.coverage_html_cb_dd2e7eb5.includes

### examples.htmlcov.coverage_html_cb_dd2e7eb5.footer
- **Calls**: examples.htmlcov.coverage_html_cb_dd2e7eb5.map, examples.htmlcov.coverage_html_cb_dd2e7eb5.getElementById, examples.htmlcov.coverage_html_cb_dd2e7eb5.setItem, examples.htmlcov.coverage_html_cb_dd2e7eb5.toLowerCase, examples.htmlcov.coverage_html_cb_dd2e7eb5.stringify, examples.htmlcov.coverage_html_cb_dd2e7eb5.forEach, examples.htmlcov.coverage_html_cb_dd2e7eb5.contains, examples.htmlcov.coverage_html_cb_dd2e7eb5.includes

## Process Flows

Key execution flows identified:

### Flow 1: add_extra_commands
```
add_extra_commands [planfile.cli.extra_commands]
```

### Flow 2: register_ticket_commands
```
register_ticket_commands [planfile.cli.cmd.cmd_ticket]
```

### Flow 3: init_strategy_cli
```
init_strategy_cli [planfile.cli.cmd.cmd_init]
  └─> _ask
  └─> _ask
```

### Flow 4: example_metric_driven_planning
```
example_metric_driven_planning [examples.ecosystem.04_llx_integration]
  └─ →> print
  └─ →> print
```

### Flow 5: example_strategy_generation_with_proxy
```
example_strategy_generation_with_proxy [examples.ecosystem.03_proxy_routing]
  └─ →> print
  └─ →> print
```

### Flow 6: generate_from_files_cmd
```
generate_from_files_cmd [planfile.cli.cmd.cmd_generate]
```

### Flow 7: review_strategy_cli
```
review_strategy_cli [planfile.cli.cmd.cmd_review]
```

### Flow 8: auto_loop
```
auto_loop [planfile.cli.auto_loop]
```

### Flow 9: register_export_commands
```
register_export_commands [planfile.cli.cmd.cmd_export]
```

### Flow 10: ci_status
```
ci_status [planfile.cli.auto_loop]
```

## Key Classes

### planfile.analysis.generator.PlanfileGenerator
> Generate comprehensive planfile from file analysis.
- **Methods**: 17
- **Key Methods**: planfile.analysis.generator.PlanfileGenerator.__init__, planfile.analysis.generator.PlanfileGenerator.generate_with_external_tools, planfile.analysis.generator.PlanfileGenerator._external_to_internal_analysis, planfile.analysis.generator.PlanfileGenerator._extract_external_metrics, planfile.analysis.generator.PlanfileGenerator.generate_from_analysis, planfile.analysis.generator.PlanfileGenerator.generate_from_current_project, planfile.analysis.generator.PlanfileGenerator._extract_key_metrics, planfile.analysis.generator.PlanfileGenerator._generate_goal, planfile.analysis.generator.PlanfileGenerator._generate_goals, planfile.analysis.generator.PlanfileGenerator._generate_quality_gates

### planfile.core.store.PlanfileStore
> Read/write tickets and sprints to .planfile/ YAML files.
- **Methods**: 15
- **Key Methods**: planfile.core.store.PlanfileStore.__init__, planfile.core.store.PlanfileStore.init, planfile.core.store.PlanfileStore.is_initialized, planfile.core.store.PlanfileStore.create_ticket, planfile.core.store.PlanfileStore.get_ticket, planfile.core.store.PlanfileStore.update_ticket, planfile.core.store.PlanfileStore.delete_ticket, planfile.core.store.PlanfileStore.list_tickets, planfile.core.store.PlanfileStore.move_ticket, planfile.core.store.PlanfileStore.next_id

### planfile.core.models.Strategy
> Main strategy configuration - simplified and more flexible.
- **Methods**: 13
- **Key Methods**: planfile.core.models.Strategy.get_task_patterns, planfile.core.models.Strategy.get_sprint, planfile.core.models.Strategy.validate_sprint_ids, planfile.core.models.Strategy.model_validate_yaml, planfile.core.models.Strategy.model_dump_yaml, planfile.core.models.Strategy.to_llx_format, planfile.core.models.Strategy.compare, planfile.core.models.Strategy.merge, planfile.core.models.Strategy.export, planfile.core.models.Strategy.get_stats
- **Inherits**: BaseModel

### planfile.analysis.external_tools.ExternalToolRunner
> Runner for external code analysis tools.
- **Methods**: 11
- **Key Methods**: planfile.analysis.external_tools.ExternalToolRunner.__init__, planfile.analysis.external_tools.ExternalToolRunner.run_all, planfile.analysis.external_tools.ExternalToolRunner.run_code2llm, planfile.analysis.external_tools.ExternalToolRunner.run_vallm, planfile.analysis.external_tools.ExternalToolRunner.run_redup, planfile.analysis.external_tools.ExternalToolRunner.parse_code2llm_output, planfile.analysis.external_tools.ExternalToolRunner.parse_vallm_output, planfile.analysis.external_tools.ExternalToolRunner.parse_redup_output, planfile.analysis.external_tools.ExternalToolRunner._mock_code2llm_data, planfile.analysis.external_tools.ExternalToolRunner._mock_vallm_data

### planfile.analysis.file_analyzer.FileAnalyzer
> Analyzes YAML/JSON files to extract issues and metrics.
- **Methods**: 10
- **Key Methods**: planfile.analysis.file_analyzer.FileAnalyzer.__init__, planfile.analysis.file_analyzer.FileAnalyzer.analyze_file, planfile.analysis.file_analyzer.FileAnalyzer._analyze_toon, planfile.analysis.file_analyzer.FileAnalyzer._analyze_yaml, planfile.analysis.file_analyzer.FileAnalyzer._analyze_json, planfile.analysis.file_analyzer.FileAnalyzer._analyze_text, planfile.analysis.file_analyzer.FileAnalyzer._extract_from_yaml_structure, planfile.analysis.file_analyzer.FileAnalyzer._extract_from_json_structure, planfile.analysis.file_analyzer.FileAnalyzer.analyze_directory, planfile.analysis.file_analyzer.FileAnalyzer._generate_summary

### planfile.analysis.sprint_generator.SprintGenerator
> Generates sprints and tickets from extracted information.
- **Methods**: 10
- **Key Methods**: planfile.analysis.sprint_generator.SprintGenerator.__init__, planfile.analysis.sprint_generator.SprintGenerator.generate_sprints, planfile.analysis.sprint_generator.SprintGenerator._group_issues_by_priority, planfile.analysis.sprint_generator.SprintGenerator._get_high_and_quality_issues, planfile.analysis.sprint_generator.SprintGenerator._get_remaining_medium_issues, planfile.analysis.sprint_generator.SprintGenerator._create_sprint, planfile.analysis.sprint_generator.SprintGenerator._map_category_to_task_type, planfile.analysis.sprint_generator.SprintGenerator._get_highest_priority, planfile.analysis.sprint_generator.SprintGenerator._estimate_effort, planfile.analysis.sprint_generator.SprintGenerator.generate_tickets

### planfile.sync.jira.JiraBackend
> Jira integration backend.
- **Methods**: 9
- **Key Methods**: planfile.sync.jira.JiraBackend.__init__, planfile.sync.jira.JiraBackend._validate_config, planfile.sync.jira.JiraBackend._map_priority_to_jira, planfile.sync.jira.JiraBackend._map_task_type_to_jira, planfile.sync.jira.JiraBackend.create_ticket, planfile.sync.jira.JiraBackend.update_ticket, planfile.sync.jira.JiraBackend.get_ticket, planfile.sync.jira.JiraBackend.list_tickets, planfile.sync.jira.JiraBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.sync.generic.GenericBackend
> Generic HTTP API backend for PM systems.
- **Methods**: 9
- **Key Methods**: planfile.sync.generic.GenericBackend.__init__, planfile.sync.generic.GenericBackend._validate_config, planfile.sync.generic.GenericBackend._make_request, planfile.sync.generic.GenericBackend.create_ticket, planfile.sync.generic.GenericBackend.update_ticket, planfile.sync.generic.GenericBackend._build_update_data, planfile.sync.generic.GenericBackend.get_ticket, planfile.sync.generic.GenericBackend.list_tickets, planfile.sync.generic.GenericBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.ci.CIRunner
> CI/CD runner with automated bug-fix loop and ticket creation.
- **Methods**: 9
- **Key Methods**: planfile.ci.CIRunner.__init__, planfile.ci.CIRunner.run_tests, planfile.ci.CIRunner.run_code_analysis, planfile.ci.CIRunner.generate_bug_report, planfile.ci.CIRunner.create_bug_tickets, planfile.ci.CIRunner.auto_fix_bugs, planfile.ci.CIRunner.check_strategy_completion, planfile.ci.CIRunner.run_loop, planfile.ci.CIRunner.save_results

### planfile.integrations.jira.JiraBackend
> Jira integration backend.
- **Methods**: 9
- **Key Methods**: planfile.integrations.jira.JiraBackend.__init__, planfile.integrations.jira.JiraBackend._validate_config, planfile.integrations.jira.JiraBackend._map_priority_to_jira, planfile.integrations.jira.JiraBackend._map_task_type_to_jira, planfile.integrations.jira.JiraBackend.create_ticket, planfile.integrations.jira.JiraBackend.update_ticket, planfile.integrations.jira.JiraBackend.get_ticket, planfile.integrations.jira.JiraBackend.list_tickets, planfile.integrations.jira.JiraBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.integrations.generic.GenericBackend
> Generic HTTP API backend for PM systems.
- **Methods**: 9
- **Key Methods**: planfile.integrations.generic.GenericBackend.__init__, planfile.integrations.generic.GenericBackend._validate_config, planfile.integrations.generic.GenericBackend._make_request, planfile.integrations.generic.GenericBackend.create_ticket, planfile.integrations.generic.GenericBackend.update_ticket, planfile.integrations.generic.GenericBackend._build_update_data, planfile.integrations.generic.GenericBackend.get_ticket, planfile.integrations.generic.GenericBackend.list_tickets, planfile.integrations.generic.GenericBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.Planfile
> Main entry point — convenience wrapper around PlanfileStore.
- **Methods**: 7
- **Key Methods**: planfile.Planfile.__init__, planfile.Planfile.auto_discover, planfile.Planfile.create_ticket, planfile.Planfile.get_ticket, planfile.Planfile.list_tickets, planfile.Planfile.update_ticket, planfile.Planfile.create_tickets_bulk

### planfile.sync.gitlab.GitLabBackend
> GitLab Issues integration backend.
- **Methods**: 7
- **Key Methods**: planfile.sync.gitlab.GitLabBackend.__init__, planfile.sync.gitlab.GitLabBackend._validate_config, planfile.sync.gitlab.GitLabBackend.create_ticket, planfile.sync.gitlab.GitLabBackend.update_ticket, planfile.sync.gitlab.GitLabBackend.get_ticket, planfile.sync.gitlab.GitLabBackend.list_tickets, planfile.sync.gitlab.GitLabBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.sync.github.GitHubBackend
> GitHub Issues integration backend.
- **Methods**: 7
- **Key Methods**: planfile.sync.github.GitHubBackend.__init__, planfile.sync.github.GitHubBackend._validate_config, planfile.sync.github.GitHubBackend.create_ticket, planfile.sync.github.GitHubBackend.update_ticket, planfile.sync.github.GitHubBackend.get_ticket, planfile.sync.github.GitHubBackend.list_tickets, planfile.sync.github.GitHubBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.executor_standalone.StrategyExecutor
> Standalone strategy executor.
- **Methods**: 7
- **Key Methods**: planfile.executor_standalone.StrategyExecutor.__init__, planfile.executor_standalone.StrategyExecutor._default_config, planfile.executor_standalone.StrategyExecutor.execute_strategy, planfile.executor_standalone.StrategyExecutor._execute_task, planfile.executor_standalone.StrategyExecutor._select_model, planfile.executor_standalone.StrategyExecutor._build_prompt, planfile.executor_standalone.StrategyExecutor._get_project_metrics

### planfile.integrations.gitlab.GitLabBackend
> GitLab Issues integration backend.
- **Methods**: 7
- **Key Methods**: planfile.integrations.gitlab.GitLabBackend.__init__, planfile.integrations.gitlab.GitLabBackend._validate_config, planfile.integrations.gitlab.GitLabBackend.create_ticket, planfile.integrations.gitlab.GitLabBackend.update_ticket, planfile.integrations.gitlab.GitLabBackend.get_ticket, planfile.integrations.gitlab.GitLabBackend.list_tickets, planfile.integrations.gitlab.GitLabBackend.search_tickets
- **Inherits**: BasePMBackend

### planfile.integrations.github.GitHubBackend
> GitHub Issues integration backend.
- **Methods**: 7
- **Key Methods**: planfile.integrations.github.GitHubBackend.__init__, planfile.integrations.github.GitHubBackend._validate_config, planfile.integrations.github.GitHubBackend.create_ticket, planfile.integrations.github.GitHubBackend.update_ticket, planfile.integrations.github.GitHubBackend.get_ticket, planfile.integrations.github.GitHubBackend.list_tickets, planfile.integrations.github.GitHubBackend.search_tickets
- **Inherits**: BasePMBackend

### examples.llx_validator.LLXValidator
> Use LLX to validate generated code and strategies.
- **Methods**: 6
- **Key Methods**: examples.llx_validator.LLXValidator.__init__, examples.llx_validator.LLXValidator.validate_strategy, examples.llx_validator.LLXValidator.analyze_generated_code, examples.llx_validator.LLXValidator._is_llx_available, examples.llx_validator.LLXValidator._parse_llx_analysis, examples.llx_validator.LLXValidator._basic_code_analysis

### examples.ecosystem.04_llx_integration.LLXIntegration
> Integration with LLX for code analysis and model selection.
- **Methods**: 6
- **Key Methods**: examples.ecosystem.04_llx_integration.LLXIntegration.__init__, examples.ecosystem.04_llx_integration.LLXIntegration.analyze_project, examples.ecosystem.04_llx_integration.LLXIntegration._parse_llx_output, examples.ecosystem.04_llx_integration.LLXIntegration._basic_analysis, examples.ecosystem.04_llx_integration.LLXIntegration.select_model, examples.ecosystem.04_llx_integration.LLXIntegration.get_task_scope

### planfile.sync.state.SyncState
> Persist mapping between local ticket IDs and remote IDs.
- **Methods**: 5
- **Key Methods**: planfile.sync.state.SyncState.__init__, planfile.sync.state.SyncState.get_last_sync, planfile.sync.state.SyncState.save_sync, planfile.sync.state.SyncState.get_remote_id, planfile.sync.state.SyncState.get_local_id

## Data Transformation Functions

Key functions that process and transform data:

### examples.llx_validator.LLXValidator.validate_strategy
> Validate a strategy file using LLX.
- **Output to**: self._is_llx_available, subprocess.run, str, str

### examples.llx_validator.LLXValidator._parse_llx_analysis
> Parse LLX analysis output.
- **Output to**: None.split, output.strip, line.split, value.strip, key.strip

### planfile.examples.example_validate_strategy
> Load and validate an existing strategy.
- **Output to**: planfile.runner.load_valid_strategy, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, examples.bash-generation.verify_planfile.print, len

### planfile.sync.gitlab.GitLabBackend._validate_config
> Validate GitLab configuration.
- **Output to**: self.config.get, ValueError, self.config.get, ValueError

### planfile.sync.jira.JiraBackend._validate_config
> Validate Jira configuration.
- **Output to**: self.config.get, ValueError, self.config.get, ValueError, self.config.get

### planfile.sync.github.GitHubBackend._validate_config
> Validate GitHub configuration.
- **Output to**: self.config.get, ValueError, self.config.get, ValueError, ValueError

### planfile.sync.generic.GenericBackend._validate_config
> Validate generic backend configuration.
- **Output to**: self.config.get, ValueError

### planfile.loaders.yaml_loader._transform_task_patterns
> Transform task patterns in the data.
- **Output to**: None.items, ModelHints, TaskType

### planfile.loaders.yaml_loader._transform_sprints
> Transform sprints in the data.

### planfile.loaders.yaml_loader._transform_goal
> Transform goal field in the data.
- **Output to**: isinstance, isinstance, Goal

### planfile.loaders.yaml_loader._format_validation_error
> Format validation error with context.
- **Output to**: hasattr, callable, e.errors, ValueError, ValueError

### planfile.loaders.yaml_loader._validate_sprints
> Validate sprint section.
- **Output to**: set, enumerate, issues.append, sprint_ids.add, issues.append

### planfile.loaders.yaml_loader._validate_gates
> Validate quality gates section.
- **Output to**: enumerate, issues.append, issues.append, issues.append

### planfile.loaders.yaml_loader._validate_task_patterns
> Validate task patterns section.
- **Output to**: None.items, enumerate, issues.append, issues.append, issues.append

### planfile.loaders.yaml_loader.validate_strategy_schema
> Validate strategy YAML file and return list of issues.

Args:
    file_path: Path to strategy YAML f
- **Output to**: planfile.loaders.yaml_loader._check_required_keys, planfile.loaders.yaml_loader._validate_sprints, planfile.loaders.yaml_loader._validate_gates, planfile.loaders.yaml_loader._validate_task_patterns, planfile.loaders.yaml_loader.load_yaml

### planfile.analysis.generator.PlanfileGenerator._parse_effort
- **Output to**: parse_effort

### planfile.importers.code2llm_importer._parse_evolution
> Parse NEXT[] section from evolution.toon.
- **Output to**: content.split, None.startswith, tickets.append, None.startswith, planfile.importers.code2llm_importer._evolution_item_to_ticket

### planfile.importers.code2llm_importer._parse_health
> Parse HEALTH[] section from analysis.toon.
- **Output to**: content.split, None.split, tickets.append, int, line.strip

### planfile.analysis.external_tools.ExternalToolRunner.parse_code2llm_output
> Parse code2llm analysis.toon.yaml output.
- **Output to**: content.split, AnalysisResults, re.search, re.search, analysis_file.exists

### planfile.analysis.external_tools.ExternalToolRunner.parse_vallm_output
> Parse vallm validation.toon.yaml output.
- **Output to**: AnalysisResults, re.search, validation_file.exists, self._mock_vallm_data, open

### planfile.analysis.external_tools.ExternalToolRunner.parse_redup_output
> Parse redup duplication.toon.yaml output.
- **Output to**: AnalysisResults, re.search, re.search, dup_file.exists, self._mock_redup_data

### planfile.cli.auto_loop._validate_strategy
> Validate strategy file exists.
- **Output to**: strategy.exists, console.print, typer.Exit

### planfile.llm.generator._parse_strategy_response
> Parse LLM YAML response into Strategy model.
- **Output to**: planfile.llm.generator._fix_yaml_formatting, yaml.safe_load, Strategy, None.split, None.split

### planfile.llm.generator._fix_yaml_formatting
> Fix common YAML formatting issues from LLM responses.
- **Output to**: yaml_text.split, enumerate, None.join, fixed_lines.append, prev_line.startswith

### planfile.integrations.gitlab.GitLabBackend._validate_config
> Validate GitLab configuration.
- **Output to**: self.config.get, ValueError, self.config.get, ValueError

## Behavioral Patterns

### recursion_extract_from_yaml_structure
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: planfile.analysis.parsers.yaml_parser.extract_from_yaml_structure

### state_machine_SyncState
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: planfile.sync.state.SyncState.__init__, planfile.sync.state.SyncState.get_last_sync, planfile.sync.state.SyncState.save_sync, planfile.sync.state.SyncState.get_remote_id, planfile.sync.state.SyncState.get_local_id

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `planfile.cli.extra_commands.add_extra_commands` - 109 calls
- `planfile.cli.cmd.cmd_ticket.register_ticket_commands` - 70 calls
- `planfile.cli.cmd.cmd_init.init_strategy_cli` - 70 calls
- `examples.ecosystem.04_llx_integration.example_metric_driven_planning` - 57 calls
- `examples.ecosystem.03_proxy_routing.example_strategy_generation_with_proxy` - 56 calls
- `planfile.cli.cmd.cmd_generate.generate_from_files_cmd` - 45 calls
- `planfile.cli.cmd.cmd_review.review_strategy_cli` - 40 calls
- `planfile.cli.auto_loop.auto_loop` - 39 calls
- `planfile.cli.cmd.cmd_export.register_export_commands` - 38 calls
- `planfile.analysis.parsers.text_parser.analyze_text` - 30 calls
- `planfile.cli.auto_loop.ci_status` - 27 calls
- `examples.ecosystem.02_mcp_integration.example_mcp_session` - 26 calls
- `planfile.cli.cmd.cmd_stats.register_stats_commands` - 25 calls
- `planfile.runner.run_strategy` - 23 calls
- `planfile.core.models.Strategy.merge` - 23 calls
- `planfile.cli.cmd.cmd_compare.compare_strategies` - 22 calls
- `planfile.cli.cmd.cmd_compare.register_compare_commands` - 22 calls
- `planfile.cli.cmd.cmd_validate.validate_strategy_cli` - 22 calls
- `planfile.core.models.Strategy.to_llx_format` - 20 calls
- `planfile.cli.cmd.cmd_apply.apply_strategy_cli` - 20 calls
- `planfile.cli.cmd.cmd_generate.generate_strategy_cli` - 20 calls
- `planfile.analysis.parsers.yaml_parser.analyze_yaml` - 20 calls
- `planfile.core.models.Strategy.get_stats` - 19 calls
- `examples.ecosystem.03_proxy_routing.example_budget_tracking` - 19 calls
- `planfile.analysis.external_tools.ExternalToolRunner.parse_code2llm_output` - 17 calls
- `planfile.mcp.server.handle_tool_call` - 17 calls
- `planfile.core.models.Sprint.convert_tasks` - 16 calls
- `planfile.loaders.cli_loader.export_results_to_markdown` - 15 calls
- `planfile.analysis.generator.PlanfileGenerator.generate_from_analysis` - 15 calls
- `planfile.cli.cmd.cmd_utils.get_backend` - 15 calls
- `planfile.analysis.parsers.toon_parser.analyze_toon` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.sortColumn` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.table` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.table_body_rows` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.no_rows` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.footer` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.ratio_columns` - 15 calls
- `examples.htmlcov.coverage_html_cb_dd2e7eb5.filter_handler` - 15 calls
- `planfile.core.store.PlanfileStore.list_tickets` - 14 calls
- `planfile.core.models.Strategy.compare` - 14 calls

## System Interactions

How components interact:

```mermaid
graph TD
    add_extra_commands --> command
    add_extra_commands --> Typer
    add_extra_commands --> add_typer
    register_ticket_comm --> Typer
    register_ticket_comm --> command
    init_strategy_cli --> Option
    init_strategy_cli --> print
    init_strategy_cli --> _ask
    example_metric_drive --> print
    example_metric_drive --> LLXIntegration
    example_strategy_gen --> print
    example_strategy_gen --> ProxyClient
    generate_from_files_ --> Argument
    generate_from_files_ --> Option
    review_strategy_cli --> Argument
    review_strategy_cli --> Option
    auto_loop --> command
    auto_loop --> Argument
    auto_loop --> Option
    register_export_comm --> command
    register_export_comm --> Argument
    register_export_comm --> Option
    ci_status --> command
    ci_status --> Argument
    ci_status --> print
    ci_status --> exists
    example_mcp_session --> print
    _parse_llx_output --> split
    _parse_llx_output --> ProjectMetrics
    _parse_llx_output --> strip
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.