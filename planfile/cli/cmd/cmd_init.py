"""
planfile init — Interactive strategy wizard.

Asks the user a series of questions (multiple choice + free text) and generates
a strategy YAML without requiring any pre-existing template.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from planfile.cli.project_detector import detect_project, get_detected_values

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────

def _choice(prompt: str, options: list[tuple[str, str]], default: str | None = None, detected: bool = False) -> str:
    """Present a numbered multiple-choice prompt and return the chosen key."""
    detected_marker = " [dim](auto-detected)[/dim]" if detected else ""
    console.print(f"\n[bold cyan]{prompt}[/bold cyan]{detected_marker}")
    for i, (key, label) in enumerate(options, 1):
        marker = f"[dim]({i})[/dim]"
        console.print(f"  {marker} {label}")

    default_idx = None
    if default:
        default_idx = next((i for i, (k, _) in enumerate(options, 1) if k == default), None)

    hint = f" [dim](domyślnie {default_idx})[/dim]" if default_idx else ""
    while True:
        raw = Prompt.ask(f"  Wybór [1-{len(options)}]{hint}", default=str(default_idx) if default_idx else "")
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        except (ValueError, TypeError):
            pass
        console.print(f"  [red]Wpisz liczbę od 1 do {len(options)}[/red]")


def _ask(prompt: str, default: str | None = None, required: bool = False, detected: bool = False) -> str:
    """Ask a free-text question with optional auto-detected indicator."""
    detected_marker = " [dim](auto-detected)[/dim]" if detected else ""
    hint = f" [dim](enter = {default})[/dim]" if default else ""
    console.print(f"\n[bold cyan]{prompt}[/bold cyan]{detected_marker}{hint}")
    while True:
        val = Prompt.ask("  >", default=default or "")
        if val or not required:
            return val
        console.print("  [red]To pole jest wymagane.[/red]")


def _ask_list(prompt: str, example: str = "") -> list[str]:
    """Ask for a comma-separated list, return stripped items."""
    console.print(f"\n[bold cyan]{prompt}[/bold cyan]")
    if example:
        console.print(f"  [dim]Przykład: {example}[/dim]")
    raw = Prompt.ask("  >", default="")
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── sprint builder ────────────────────────────────────────────────────────

_SPRINT_PRESETS: dict[str, list[dict]] = {
    "api": [
        {"name": "Specyfikacja & Architektura", "duration": "1 tydzień",
         "objectives": ["Definicja endpointów (OpenAPI spec)", "Modele danych (Pydantic)", "Struktura projektu"]},
        {"name": "Implementacja", "duration": "2 tygodnie",
         "objectives": ["CRUD endpoints (FastAPI)", "Walidacja wejścia", "Warstwa bazy danych"]},
        {"name": "Testowanie", "duration": "1 tydzień",
         "objectives": ["Testy jednostkowe (pytest)", "Testy integracyjne (TestClient)", "Pokrycie > 80%"]},
        {"name": "Deploy & Monitoring", "duration": "1 tydzień",
         "objectives": ["Dockerfile + docker-compose", "Pipeline CI/CD", "Endpoint /health i /metrics"]},
    ],
    "web": [
        {"name": "Fundament & Setup", "duration": "2 tygodnie",
         "objectives": ["Struktura projektu", "Pipeline CI/CD", "Autentykacja"]},
        {"name": "Główne funkcje", "duration": "3 tygodnie",
         "objectives": ["Logika biznesowa", "Interfejs użytkownika", "Warstwa bazy danych"]},
        {"name": "Szlif & Deploy", "duration": "2 tygodnie",
         "objectives": ["Optymalizacja wydajności", "Wzmocnienie bezpieczeństwa", "Wdrożenie produkcyjne"]},
    ],
    "cli": [
        {"name": "Projekt CLI", "duration": "1 tydzień",
         "objectives": ["Struktura komend", "Interfejs użytkownika CLI", "Parsowanie argumentów"]},
        {"name": "Implementacja", "duration": "2 tygodnie",
         "objectives": ["Logika komend", "Obsługa błędów", "Konfiguracja"]},
        {"name": "Testowanie & Publikacja", "duration": "1 tydzień",
         "objectives": ["Testy e2e", "Dokumentacja", "PyPI / pakietowanie"]},
    ],
    "library": [
        {"name": "Projektowanie API", "duration": "1 tydzień",
         "objectives": ["Publiczne API biblioteki", "Typy i interfejsy", "Dokumentacja architektury"]},
        {"name": "Implementacja", "duration": "2 tygodnie",
         "objectives": ["Logika rdzenna", "Obsługa błędów", "Typy eksportowane"]},
        {"name": "Testy & Release", "duration": "1 tydzień",
         "objectives": ["Testy jednostkowe", "Testy integracyjne", "Publikacja pakietu"]},
    ],
    "custom": [],
}

_FOCUS_QUALITY_GATES: dict[str, list[dict]] = {
    "tdd": [
        {"name": "Test Coverage", "description": "Minimum test coverage",
         "criteria": ["pytest --cov >= 80%", "All tests passing"], "required": True},
    ],
    "security": [
        {"name": "Security Scan", "description": "No critical vulnerabilities",
         "criteria": ["bandit -r . returns 0 critical", "Dependencies up to date"], "required": True},
    ],
    "performance": [
        {"name": "Performance", "description": "Response time targets met",
         "criteria": ["p95 latency < 200ms", "No memory leaks"], "required": True},
    ],
    "none": [],
}


# ── main command ──────────────────────────────────────────────────────────

def init_strategy_cli(
    output: str = typer.Option("planfile.yaml", "--output", "-o", help="Output file path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation before saving"),
):
    """
    Interactive wizard — tworzy strategię przez zadawanie pytań.

    Nie wymaga szablonu. Pyta o typ projektu, cele, sprinty i bramki jakości.
    Automatycznie wykrywa dane projektu z pyproject.toml, package.json lub README.
    """
    console.print(Panel(
        "[bold]planfile init[/bold] — Interaktywny kreator strategii\n"
        "[dim]Odpowiedz na pytania, a wygeneruję plik planfile.yaml[/dim]",
        border_style="cyan",
    ))

    # ── Auto-detekcja projektu ────────────────────────────────────────────
    detected = get_detected_values()
    
    if detected["has_detection"]:
        source = detected["source"]
        console.print(f"\n[dim]ℹ️ Wykryto dane projektu z {source}[/dim]")

    # ── 1. Podstawowe informacje ──────────────────────────────────────────
    name = _ask("Nazwa projektu", default=detected["name"], required=True, detected=bool(detected["name"]))
    description = _ask("Krótki opis projektu (opcjonalnie)", default=detected["description"], detected=bool(detected["description"]))

    project_type = _choice(
        "Typ projektu",
        [
            ("api",     "REST API / serwis backendowy"),
            ("web",     "Aplikacja webowa (frontend + backend)"),
            ("cli",     "Narzędzie CLI"),
            ("library", "Biblioteka / pakiet Python"),
            ("custom",  "Własny (zdefiniuję sprinty ręcznie)"),
        ],
        default=detected["project_type"] or "api",
        detected=bool(detected["project_type"]),
    )

    domain = _ask("Domena biznesowa (np. e-commerce, finance, devtools)", default=detected["domain"], detected=bool(detected["domain"]))
    goal_short = _ask("Cel w jednym zdaniu", default=detected["goal"], required=True, detected=bool(detected["goal"]))

    # ── 2. Sprinty ───────────────────────────────────────────────────────
    sprints_data: list[dict] = []

    if project_type == "custom":
        n_sprints = int(_ask("Ile sprintów?", default="3"))
        for i in range(1, n_sprints + 1):
            console.print(f"\n[bold]Sprint {i}[/bold]")
            s_name = _ask(f"  Nazwa sprintu {i}", default=f"Sprint {i}", required=True)
            s_dur  = _ask(f"  Czas trwania", default="2 tygodnie")
            s_objs = _ask_list(
                f"  Cele sprintu {i} (oddzielone przecinkami)",
                example="Zaprojektuj architekturę, Skonfiguruj CI/CD"
            )
            sprints_data.append({"name": s_name, "duration": s_dur, "objectives": s_objs})
    else:
        preset = _SPRINT_PRESETS[project_type]
        console.print(f"\n[dim]Używam {len(preset)} domyślnych sprintów dla '{project_type}'. Możesz je dostosować.[/dim]")

        customize = Confirm.ask("  Chcesz edytować sprinty?", default=False)
        if customize:
            for i, s in enumerate(preset, 1):
                console.print(f"\n[bold]Sprint {i}: {s['name']}[/bold]")
                s["name"]     = _ask("  Nazwa", default=s["name"])
                s["duration"] = _ask("  Czas trwania", default=s["duration"])
                edited_objs   = _ask_list(
                    "  Cele (oddzielone przecinkami)",
                    example=", ".join(s["objectives"][:2])
                )
                s["objectives"] = edited_objs if edited_objs else s["objectives"]

        sprints_data = preset

        # Dodatkowe sprinty?
        while Confirm.ask("\n  Dodać kolejny sprint?", default=False):
            i = len(sprints_data) + 1
            s_name = _ask(f"  Nazwa sprintu {i}", default=f"Sprint {i}", required=True)
            s_dur  = _ask("  Czas trwania", default="1 tydzień")
            s_objs = _ask_list("  Cele sprintu", example="...")
            sprints_data.append({"name": s_name, "duration": s_dur, "objectives": s_objs})

    # ── 3. Priorytety / focus ─────────────────────────────────────────────
    focus = _choice(
        "Główny priorytet projektu",
        [
            ("tdd",         "TDD / Jakość kodu i testy"),
            ("security",    "Bezpieczeństwo"),
            ("performance", "Wydajność"),
            ("none",        "Brak szczególnego priorytetu"),
        ],
        default="tdd" if detected["has_tests"] else "none",
        detected=detected["has_tests"],
    )
    
    # Show detected quality gates if any
    if detected["quality_gates"]:
        console.print(f"\n[dim]Wykryto {len(detected['quality_gates'])} bramek jakości z plików projektu:[/dim]")
        for gate in detected["quality_gates"]:
            console.print(f"  [dim]• {gate['name']}[/dim]")
    
    extra_gates = _ask_list(
        "Dodatkowe bramki jakości (opcjonalnie, enter = pomiń)",
        example="Docker image builds, API docs generated"
    )

    # ── 4. Model hints ────────────────────────────────────────────────────
    model_tier = _choice(
        "Preferowany tier modeli LLM",
        [
            ("free",     "Darmowe (openrouter free / local)"),
            ("cheap",    "Tanie (gpt-4o-mini, haiku)"),
            ("balanced", "Zbalansowane (claude-sonnet, gpt-4o)"),
            ("premium",  "Premium (claude-opus, gpt-4)"),
        ],
        default=detected["model_tier"] or "cheap",
        detected=bool(detected.get("model_tier")),
    )

    # ── Budowanie YAML ────────────────────────────────────────────────────
    sprints_yaml = []
    for i, s in enumerate(sprints_data, 1):
        sprints_yaml.append({
            "id":         i,
            "name":       s["name"],
            "length_days": {"1 tydzień": 7, "2 tygodnie": 14, "3 tygodnie": 21}.get(s.get("duration", ""), 14),
            "duration":   s.get("duration", "2 tygodnie"),
            "objectives": s.get("objectives", []),
        })

    # Start with focus quality gates
    quality_gates = list(_FOCUS_QUALITY_GATES.get(focus, []))
    
    # Add detected quality gates from project files
    for gate in detected["quality_gates"]:
        quality_gates.append({
            "name": gate["name"],
            "description": gate["description"],
            "criteria": gate["criteria"],
            "required": gate["required"],
        })
    
    # Add extra gates from user input
    for gate_text in extra_gates:
        quality_gates.append({
            "name": gate_text,
            "description": gate_text,
            "criteria": [gate_text],
            "required": True,
        })

    strategy_dict = {
        "name": name,
        "version": "1.0.0",
        "project_type": project_type,
        "domain": domain,
        "description": description or None,
        "goal": {
            "short": goal_short,
            "quality": [],
            "delivery": [],
            "metrics": [],
        },
        "sprints": sprints_yaml,
        "tasks": {"patterns": []},
        "quality_gates": quality_gates,
        "metadata": {
            "model_tier": model_tier,
            "focus": focus,
        },
    }

    # ── Podsumowanie ──────────────────────────────────────────────────────
    console.print("\n")
    table = Table(title="Podsumowanie strategii", border_style="cyan")
    table.add_column("Parametr", style="bold")
    table.add_column("Wartość", style="green")
    table.add_row("Nazwa",         name)
    table.add_row("Typ projektu",  project_type)
    table.add_row("Domena",        domain)
    table.add_row("Cel",           goal_short)
    table.add_row("Sprinty",       str(len(sprints_yaml)))
    table.add_row("Fokus",         focus)
    table.add_row("Tier modelu",   model_tier)
    table.add_row("Plik wyjściowy", output)
    console.print(table)

    if not yes and not Confirm.ask("\nZapisać strategię?", default=True):
        console.print("[yellow]Anulowano.[/yellow]")
        raise typer.Exit(0)

    # ── Zapis ─────────────────────────────────────────────────────────────
    import yaml  # noqa: F401 — available in planfile venv
    out_path = Path(output)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(strategy_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    console.print(f"\n[green]✓[/green] Zapisano strategię: [bold]{out_path}[/bold]")
    console.print("\n[dim]Następne kroki:[/dim]")
    console.print(f"  1. Przejrzyj:  planfile validate {output}")
    console.print(f"  2. Statystyki: planfile stats {output}")
    console.print(f"  3. Wykonaj:    llx plan apply {output} ./my-project")
