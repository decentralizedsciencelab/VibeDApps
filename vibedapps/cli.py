#!/usr/bin/env python3
"""
Command-line interface for VibeDApps.

Runs the pipeline in-process, so no server needs to be up.

    vibedapps create --interactive
    vibedapps create --config myproject.json
    vibedapps list
    vibedapps show <project_id>
    vibedapps export <project_id> --output ./my_dapp
    vibedapps review ./path/to/code --agent security
"""

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

from vibedapps.pipeline import DAppGenerator, ProjectSpec

PROJECTS_DIR = Path.home() / ".vibedapps" / "projects"

CONTRACT_FEATURES = {
    "erc20": ["mintable", "burnable", "pausable", "snapshot", "permit"],
    "erc721": ["mintable", "burnable", "enumerable", "uri_storage", "royalties"],
    "erc1155": ["mintable", "burnable", "pausable", "supply_tracking"],
    "dao": ["voting", "timelock", "treasury", "delegation"],
    "defi": ["staking", "liquidity_pool", "yield_farming", "flash_loans"],
    "marketplace": ["auction", "fixed_price", "offers", "royalties"],
    "custom": [],
}

BACKENDS = {
    "express": "javascript",
    "hardhat": "javascript",
    "truffle": "javascript",
    "flask": "python",
    "fastapi": "python",
    "django": "python",
    "minimal": "javascript",
}

FRONTENDS = ["react", "vue", "nextjs", "html"]


def print_header(text: str):
    if RICH_AVAILABLE:
        console.print(Panel(f"[bold cyan]{text}[/bold cyan]", expand=False))
    else:
        print(f"\n{'=' * 60}\n{text}\n{'=' * 60}")


def print_success(text: str):
    if RICH_AVAILABLE:
        console.print(f"[bold green]✓[/bold green] {text}")
    else:
        print(f"✓ {text}")


def print_error(text: str):
    if RICH_AVAILABLE:
        console.print(f"[bold red]✗[/bold red] {text}")
    else:
        print(f"✗ {text}")


def print_warning(text: str):
    if RICH_AVAILABLE:
        console.print(f"[bold yellow]⚠[/bold yellow] {text}")
    else:
        print(f"⚠ {text}")


def _ask(prompt: str, default: str = "") -> str:
    if RICH_AVAILABLE:
        return Prompt.ask(f"[cyan]{prompt}[/cyan]", default=default)
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _confirm(prompt: str, default: bool = True) -> bool:
    if RICH_AVAILABLE:
        return Confirm.ask(f"[cyan]{prompt}[/cyan]", default=default)
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _choose(prompt: str, options: List[str], default: str) -> str:
    if RICH_AVAILABLE:
        return Prompt.ask(f"[cyan]{prompt}[/cyan]", choices=options, default=default)
    answer = input(f"{prompt} ({'/'.join(options)}) [{default}]: ").strip().lower()
    return answer if answer in options else default


def interactive_create_project() -> ProjectSpec:
    """Interactive project creation wizard."""
    print_header("VibeDApps — Interactive Project Creation")

    project_name = _ask("Project name", "MyDApp")
    description = _ask("Project description", "A decentralized application")

    contract_type = _choose("Contract type", list(CONTRACT_FEATURES.keys()), "erc20")

    contract_features = {}
    for feature in CONTRACT_FEATURES[contract_type]:
        contract_features[feature] = _confirm(f"  Include {feature}?", default=False)

    backend_type = _choose("Backend framework", list(BACKENDS.keys()), "express")
    backend_language = BACKENDS[backend_type]

    frontend_framework = _choose("Frontend framework", FRONTENDS, "react")
    dark_mode = _confirm("Include dark mode?", default=True)

    wallets = [w for w in ("MetaMask", "WalletConnect", "Coinbase Wallet")
               if _confirm(f"  Include {w} wallet?", default=(w == "MetaMask"))]
    if not wallets:
        wallets = ["MetaMask"]

    security_audit = _confirm("Perform security audit?", default=True)
    network = _choose("Deployment network",
                      ["ethereum-sepolia", "ethereum", "polygon", "bsc", "arbitrum"],
                      "ethereum-sepolia")

    strategy = _choose("Generation strategy", ["auto", "llm_only", "tool_based", "hybrid"], "auto")

    return ProjectSpec(
        projectName=project_name,
        projectDescription=description,
        contractType=contract_type,
        contractFeatures=contract_features,
        backendType=backend_type,
        backendLanguage=backend_language,
        frontendFramework=frontend_framework,
        uiComponents={"darkMode": dark_mode, "wallets": wallets},
        securityChecks={"enabled": security_audit},
        deploymentOptions={"network": network},
        generationStrategy=None if strategy == "auto" else strategy,
    )


def load_project_config(config_file: Path) -> ProjectSpec:
    """Load project configuration from a JSON file."""
    try:
        with open(config_file) as f:
            return ProjectSpec(**json.load(f))
    except Exception as e:
        print_error(f"Failed to load config file: {e}")
        sys.exit(1)


def build_llm_service(backend: str, model: Optional[str] = None):
    """Construct the LLM backend: 'openai' (API key) or 'claude-cli' (local CLI auth)."""
    if backend == "claude-cli":
        from vibedapps.llm.claude_cli_service import ClaudeCLIService
        return ClaudeCLIService(model=model or "sonnet")
    from vibedapps.llm.openai_service import OpenAIService
    return OpenAIService()


async def create_project(spec: ProjectSpec, llm_backend: str, llm_model: Optional[str],
                         output: Optional[Path], make_zip: bool) -> None:
    """Generate a DApp with the local pipeline and save it to disk."""
    generator = DAppGenerator(llm_service=build_llm_service(llm_backend, llm_model))

    try:
        tools = await generator.detect_tools()
        if tools:
            print_success(f"Detected dev tools: {', '.join(tools)}")
        else:
            print_warning("No dev tools detected (Hardhat/Foundry) — using LLM-only generation")
    except Exception as e:
        print_warning(f"Tool detection failed ({e}) — using LLM-only generation")

    if RICH_AVAILABLE:
        console.print(f"\n[bold]Generating[/bold] [cyan]{spec.projectName}[/cyan] "
                      f"({spec.contractType} / {spec.backendType} / {spec.frontendFramework})\n")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as bar:
            task = bar.add_task("starting...", total=None)
            result = await generator.generate(
                spec, progress=lambda stage, pct: bar.update(task, description=f"{stage} ({pct}%)")
            )
    else:
        print(f"\nGenerating {spec.projectName} "
              f"({spec.contractType} / {spec.backendType} / {spec.frontendFramework})\n")
        result = await generator.generate(
            spec, progress=lambda stage, pct: print(f"  [{pct:3d}%] {stage}")
        )

    project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = output or (PROJECTS_DIR / project_id)
    generator.package(result, project_dir, make_zip=make_zip)

    # Metadata enables `list` / `show` / `export`
    (project_dir / "metadata.json").write_text(json.dumps({
        "spec": result["spec"],
        "project_id": result["project_id"],
        "generation_strategy": result["generation_strategy"],
        "tools_used": result["tools_used"],
        "created_at": datetime.now().isoformat(),
    }, indent=2))

    print_success(f"Project generated: {project_dir}")
    print(f"  Strategy: {result['generation_strategy']}")
    if result["tools_used"]:
        print(f"  Tools used: {', '.join(result['tools_used'])}")
    if result["fallback_occurred"]:
        print_warning("Fallback to LLM-only generation occurred")
    audit = result["files"].get("audit") or {}
    if audit:
        print(f"  Audit risk level: {audit.get('risk_level', 'unknown')}")


def list_projects():
    print_header("Generated DApp Projects")
    if not PROJECTS_DIR.exists() or not any(PROJECTS_DIR.iterdir()):
        print_warning(f"No projects found in {PROJECTS_DIR}")
        return

    rows = []
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        metadata_file = project_dir / "metadata.json"
        if project_dir.is_dir() and metadata_file.exists():
            meta = json.loads(metadata_file.read_text())
            spec = meta.get("spec", {})
            created = meta.get("created_at", "unknown")
            rows.append((project_dir.name, spec.get("projectName", "?"),
                         spec.get("contractType", "?"), created.split("T")[0]))

    if RICH_AVAILABLE:
        table = Table(title="Projects")
        for col in ("ID", "Name", "Type", "Created"):
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        console.print(table)
    else:
        print(f"{'ID':<20} {'Name':<20} {'Type':<12} {'Created':<12}")
        print("-" * 66)
        for row in rows:
            print(f"{row[0]:<20} {row[1]:<20} {row[2]:<12} {row[3]:<12}")


def show_project(project_id: str):
    project_dir = PROJECTS_DIR / project_id
    metadata_file = project_dir / "metadata.json"
    if not metadata_file.exists():
        print_error(f"Project not found: {project_id}")
        return

    meta = json.loads(metadata_file.read_text())
    spec = meta.get("spec", {})
    print_header(f"Project: {spec.get('projectName')}")
    print(f"Description: {spec.get('projectDescription')}")
    print(f"Contract: {spec.get('contractType')} "
          f"(features: {', '.join(k for k, v in spec.get('contractFeatures', {}).items() if v) or 'none'})")
    print(f"Backend: {spec.get('backendType')} ({spec.get('backendLanguage')})")
    print(f"Frontend: {spec.get('frontendFramework')}")
    print(f"Strategy: {meta.get('generation_strategy', 'unknown')}")
    print("\nFiles:")
    for file_path in sorted(project_dir.rglob("*")):
        if file_path.is_file() and file_path.name != "metadata.json":
            print(f"  {file_path.relative_to(project_dir)}")


def export_project(project_id: str, output_dir: Optional[Path]):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        print_error(f"Project not found: {project_id}")
        return

    output_dir = Path(output_dir) if output_dir else Path.cwd() / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in project_dir.iterdir():
        if item.name == "metadata.json":
            continue
        if item.is_file():
            shutil.copy2(item, output_dir / item.name)
        else:
            shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)
    print_success(f"Project exported to: {output_dir}")


async def run_code_review(path: str, agent_type: str, min_severity: Optional[str],
                          output_file: Optional[Path], llm_backend: str, llm_model: Optional[str]):
    """Run one or all review agents over a file or directory."""
    from vibedapps.agents.specialized.api_contract_agent import APIContractAgent
    from vibedapps.agents.specialized.architecture_agent import ArchitectureAgent
    from vibedapps.agents.specialized.code_quality_agent import CodeQualityAgent
    from vibedapps.agents.specialized.documentation_agent import DocumentationAgent
    from vibedapps.agents.specialized.error_handling_agent import ErrorHandlingAgent
    from vibedapps.agents.specialized.performance_agent import PerformanceAgent
    from vibedapps.agents.specialized.security_auditor_agent import SecurityAuditorAgent
    from vibedapps.agents.specialized.test_coverage_agent import TestCoverageAgent

    llm = build_llm_service(llm_backend, llm_model)
    agent_map = {
        "security": SecurityAuditorAgent(llm_service=llm),
        "quality": CodeQualityAgent(llm_service=llm),
        "error-handling": ErrorHandlingAgent(llm_service=llm),
        "performance": PerformanceAgent(llm_service=llm),
        "test-coverage": TestCoverageAgent(llm_service=llm),
        "documentation": DocumentationAgent(llm_service=llm),
        "architecture": ArchitectureAgent(llm_service=llm),
        "api-contract": APIContractAgent(llm_service=llm),
    }
    agents_to_run = list(agent_map.values()) if agent_type == "all" else [agent_map[agent_type]]

    print_header(f"Code Review: {path}")
    reports = []
    for agent in agents_to_run:
        print(f"Running {agent.config.name}...")
        try:
            reports.append(await agent.review(path))
        except Exception as e:
            print_error(f"Error running {agent.config.name}: {e}")

    findings = [f for r in reports for f in r.findings]
    if min_severity:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        cutoff = order.get(min_severity.lower(), 4)
        findings = [f for f in findings if order.get(f.severity.value, 4) <= cutoff]

    if not findings:
        print_success("No issues found!")
    else:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for finding in sorted(findings, key=lambda f: order.get(f.severity.value, 4)):
            print(f"\n[{finding.severity.value.upper()}] {finding.title}")
            print(f"  Location: {finding.location}")
            print(f"  Fix: {finding.recommendation}")

    if output_file:
        output_file.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "reports": [r.to_dict() for r in reports],
        }, indent=2))
        print_success(f"Review report saved to: {output_file}")


def _add_llm_args(subparser):
    subparser.add_argument("--llm", choices=["openai", "claude-cli"], default="openai",
                           help="LLM backend: OpenAI API (needs OPENAI_API_KEY) or local claude CLI")
    subparser.add_argument("--model", help="Model override for the chosen backend")


async def async_main():
    parser = argparse.ArgumentParser(
        prog="vibedapps",
        description="VibeDApps — generate complete DApps (contracts, backend, frontend, tests) with AI agents",
    )
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create", help="Create a new DApp project")
    group = create_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--interactive", "-i", action="store_true", help="Interactive wizard")
    group.add_argument("--config", "-c", type=Path, help="JSON spec file")
    create_parser.add_argument("--output", "-o", type=Path, help="Output directory")
    create_parser.add_argument("--zip", action="store_true", help="Also produce a .zip archive")
    create_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    _add_llm_args(create_parser)

    subparsers.add_parser("list", help="List generated projects")

    show_parser = subparsers.add_parser("show", help="Show project details")
    show_parser.add_argument("project_id")

    export_parser = subparsers.add_parser("export", help="Export a project to a directory")
    export_parser.add_argument("project_id")
    export_parser.add_argument("--output", "-o", type=Path)

    review_parser = subparsers.add_parser("review", help="Review code with specialized agents")
    review_parser.add_argument("path")
    review_parser.add_argument("--agent", "-a", default="all",
                               choices=["all", "security", "quality", "error-handling", "performance",
                                        "test-coverage", "documentation", "architecture", "api-contract"])
    review_parser.add_argument("--severity", "-s",
                               choices=["critical", "high", "medium", "low", "info"])
    review_parser.add_argument("--output", "-o", type=Path, help="Save JSON report")
    _add_llm_args(review_parser)

    args = parser.parse_args()

    if args.command == "create":
        spec = interactive_create_project() if args.interactive else load_project_config(args.config)
        print("\nProject specification:")
        print(json.dumps(spec.model_dump(), indent=2))
        if not args.yes and not _confirm("\nProceed with generation?", default=True):
            print_warning("Cancelled")
            return
        await create_project(spec, args.llm, args.model, args.output, args.zip)
    elif args.command == "list":
        list_projects()
    elif args.command == "show":
        show_project(args.project_id)
    elif args.command == "export":
        export_project(args.project_id, args.output)
    elif args.command == "review":
        await run_code_review(args.path, args.agent, args.severity, args.output,
                              args.llm, args.model)
    else:
        parser.print_help()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
