"""
Interactive strategy builder using LLX with local LLM.
"""
import subprocess
from pathlib import Path
from typing import Any

from planfile.models import Goal, ModelHints, Sprint, Strategy, TaskPattern, TaskType


class LLXStrategyBuilder:
    """Interactive strategy builder using LLX."""

    def __init__(
        self,
        llx_path: str = "llx",
        model: str = "qwen2.5:3b",
        local: bool = True
    ):
        """
        Initialize strategy builder.
        
        Args:
            llx_path: Path to llx command
            model: Model to use (e.g., "qwen2.5:3b")
            local: Use local model
        """
        self.llx_path = llx_path
        self.model = model
        self.local = local

    def _call_llx(self, prompt: str) -> str:
        """
        Call LLX with the given prompt.
        
        Args:
            prompt: Prompt to send to LLX
            
        Returns:
            LLM response as string
        """
        cmd = [self.llx_path, "chat"]

        if self.local:
            cmd.extend(["--local"])

        cmd.extend(["--model", self.model, "--prompt", prompt])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error calling LLX: {e}")
            print(f"Stderr: {e.stderr}")
            return ""

    def ask_llm_questions(self) -> dict[str, Any]:
        """
        Ask LLM questions to build strategy interactively.
        
        Returns:
            Dictionary with collected answers
        """
        answers = {}

        print("🎯 Building Strategy with LLX")
        print("=" * 50)

        # 1. Basic project info
        print("\n1. Project Goal")
        print("-" * 20)

        answers["goal"] = self._call_llx(
            "Ask user: What is the short description of this project's goal? "
            "Answer in one sentence."
        )
        print(f"Goal: {answers['goal']}")

        answers["quality_goals"] = self._call_llm(
            "Ask user: What are the quality goals for this project? "
            "List 3-5 bullet points."
        )
        print(f"Quality goals: {answers['quality_goals']}")

        answers["delivery_goals"] = self._call_llm(
            "Ask user: What are the delivery goals (deadlines, environments, etc.)? "
            "List 2-3 bullet points."
        )
        print(f"Delivery goals: {answers['delivery_goals']}")

        # 2. Project details
        print("\n2. Project Details")
        print("-" * 20)

        answers["project_type"] = self._call_llx(
            "Ask user: What type of project is this? "
            "Choose one: web, mobile, api, desktop, library"
        )
        print(f"Project type: {answers['project_type']}")

        answers["domain"] = self._call_llx(
            "Ask user: What business domain does this project belong to? "
            "Examples: fintech, healthcare, education, ecommerce, social"
        )
        print(f"Domain: {answers['domain']}")

        # 3. Sprints
        print("\n3. Sprints")
        print("-" * 20)

        answers["sprints"] = []
        sprint_count = int(self._call_llx(
            "Ask user: How many sprints do you want to plan? (1-5)"
        ))

        for i in range(1, sprint_count + 1):
            objectives = self._call_llm(
                f"Ask user: What are the objectives for sprint {i}? "
                f"List up to 5 bullet points."
            )

            sprint_name = self._call_llm(
                f"Ask user: What is the name for sprint {i}?"
            )

            answers["sprints"].append({
                "id": i,
                "name": sprint_name,
                "objectives": self._parse_bullet_list(objectives),
                "length_days": 14  # Default
            })
            print(f"Sprint {i}: {sprint_name}")

        # 4. Task patterns
        print("\n4. Task Patterns")
        print("-" * 20)

        # Feature pattern
        feature_title = self._call_llx(
            "Suggest a title template for feature tasks. "
            "Use placeholders like {feature_name} or {component}."
        )
        feature_desc = self._call_llx(
            "Suggest a description template for feature tasks. "
            "Include sections for requirements, acceptance criteria, and notes."
        )

        answers["feature_pattern"] = {
            "title": feature_title,
            "description": feature_desc
        }

        # Bug pattern
        bug_title = self._call_llx(
            "Suggest a title template for bug tasks. "
            "Use placeholders like {issue_description} or {component}."
        )
        bug_desc = self._call_llx(
            "Suggest a description template for bug tasks. "
            "Include sections for reproduction steps, expected behavior, and environment."
        )

        answers["bug_pattern"] = {
            "title": bug_title,
            "description": bug_desc
        }

        # Tech debt pattern
        tech_debt_title = self._call_llx(
            "Suggest a title template for tech debt tasks. "
            "Use placeholders like {area} or {reason}."
        )
        tech_debt_desc = self._call_llx(
            "Suggest a description template for tech debt tasks. "
            "Include sections for current problem, proposed solution, and impact."
        )

        answers["tech_debt_pattern"] = {
            "title": tech_debt_title,
            "description": tech_debt_desc
        }

        # 5. Quality gates
        print("\n5. Quality Gates")
        print("-" * 20)

        answers["quality_gates"] = []
        has_gates = self._call_llx(
            "Ask user: Do you want to define quality gates? (yes/no)"
        ).lower() == "yes"

        if has_gates:
            gate_count = int(self._call_llx(
                "Ask user: How many quality gates? (1-3)"
            ))

            for i in range(gate_count):
                gate_name = self._call_llx(
                    f"Ask user: What is the name of quality gate {i+1}?"
                )
                gate_desc = self._call_llx(
                    f"Ask user: Describe quality gate '{gate_name}'."
                )
                gate_criteria = self._call_llx(
                    f"Ask user: What are the criteria for '{gate_name}'? List 2-4 bullet points."
                )

                answers["quality_gates"].append({
                    "name": gate_name,
                    "description": gate_desc,
                    "criteria": self._parse_bullet_list(gate_criteria),
                    "required": True
                })

        return answers

    def _parse_bullet_list(self, text: str) -> list[str]:
        """Parse bullet points from text."""
        lines = text.strip().split('\n')
        bullets = []
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '*', '•', '1.', '2.', '3.', '4.', '5.')):
                # Remove bullet marker
                clean = line[2:] if line.startswith(('- ', '*', '•')) else line.split('.', 1)[1].strip()
                bullets.append(clean)
        return bullets

    def answers_to_strategy(self, answers: dict[str, Any]) -> Strategy:
        """
        Convert answers to a validated Strategy object.
        
        Args:
            answers: Collected answers from LLM
            
        Returns:
            Validated Strategy object
        """
        # Build goal object
        goal = Goal(
            short=answers["goal"],
            quality=self._parse_bullet_list(answers["quality_goals"]),
            delivery=self._parse_bullet_list(answers["delivery_goals"])
        )

        # Build task patterns
        patterns = []

        # Feature pattern
        patterns.append(TaskPattern(
            id="feature",
            type=TaskType.feature,
            title=answers["feature_pattern"]["title"],
            description=answers["feature_pattern"]["description"],
            model_hints=ModelHints(
                design="balanced",
                implementation="balanced"
            )
        ))

        # Bug pattern
        patterns.append(TaskPattern(
            id="bug",
            type=TaskType.bug,
            title=answers["bug_pattern"]["title"],
            description=answers["bug_pattern"]["description"],
            priority="highest",
            model_hints=ModelHints(
                triage="balanced",
                implementation="local"
            )
        ))

        # Tech debt pattern
        patterns.append(TaskPattern(
            id="tech_debt",
            type=TaskType.tech_debt,
            title=answers["tech_debt_pattern"]["title"],
            description=answers["tech_debt_pattern"]["description"],
            priority="medium",
            model_hints=ModelHints(
                implementation="local"
            )
        ))

        # Build sprints
        sprints = []
        for sprint_data in answers["sprints"]:
            sprint = Sprint(**sprint_data)
            # Add default task patterns to each sprint
            sprint.tasks = ["feature", "bug", "tech_debt"]
            sprints.append(sprint)

        # Build quality gates
        quality_gates = []
        for gate_data in answers.get("quality_gates", []):
            from planfile.models import QualityGate
            quality_gates.append(QualityGate(**gate_data))

        # Create strategy
        strategy_data = {
            "name": f"{answers['domain'].title()} Strategy",
            "version": "0.1.0",
            "project_type": answers["project_type"],
            "domain": answers["domain"],
            "goal": goal,
            "sprints": sprints,
            "tasks": {"patterns": patterns},
            "quality_gates": quality_gates,
            "metadata": {
                "generated_by": "llx-strategy-builder",
                "model": self.model
            }
        }

        # Validate and return
        return Strategy.model_validate(strategy_data)

    def build_strategy(self, output_path: str | None = None) -> Strategy:
        """
        Build strategy interactively.
        
        Args:
            output_path: Optional path to save the strategy YAML
            
        Returns:
            Built Strategy object
        """
        # Collect answers
        answers = self.ask_llm_questions()

        # Convert to strategy
        strategy = self.answers_to_strategy(answers)

        # Save if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(strategy.model_dump_yaml())
            print(f"\n✅ Strategy saved to: {output_path}")

        return strategy


def create_strategy_command(
    output: str = "strategy.yaml",
    model: str = "qwen2.5:3b",
    local: bool = True
) -> None:
    """
    CLI command to create strategy interactively.
    
    Args:
        output: Output file path
        model: LLM model to use
        local: Use local model
    """
    builder = LLXStrategyBuilder(model=model, local=local)
    strategy = builder.build_strategy(output)

    print("\n✨ Strategy created successfully!")
    print(f"   Name: {strategy.name}")
    print(f"   Sprints: {len(strategy.sprints)}")
    print(f"   Task patterns: {len(strategy.get_task_patterns())}")
    print(f"   Quality gates: {len(strategy.quality_gates)}")
