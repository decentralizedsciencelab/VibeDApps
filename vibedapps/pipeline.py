"""
The in-process generation pipeline. This is the library entry point.

The original project ran this behind a FastAPI server; here the agents
are wired up and called directly. Stages, in order: contract generation
(strategy auto-selected), security audit, backend, frontend, tests,
integration, and finally packaging to a directory on disk. Each stage
writes into a shared context so the next ones can build on it.
"""

import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.specialized.audit_agent import SmartContractAuditAgent
from vibedapps.agents.specialized.backend_agent import BackendAgent
from vibedapps.agents.specialized.frontend_agent import FrontendAgent
from vibedapps.agents.specialized.integration_agent import IntegrationAgent
from vibedapps.agents.specialized.smart_contract_agent import SmartContractAgent
from vibedapps.agents.specialized.test_generator_agent import TestGeneratorAgent
from vibedapps.memory.memory_store import InMemoryStore
from vibedapps.orchestration.generation_context import (
    BackendArtifact,
    ContractArtifact,
    DAppGenerationContext,
    FrontendArtifact,
    TestArtifact,
    create_context_from_specs,
)
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.registry import ToolRegistry


class ProjectSpec(BaseModel):
    """DApp project specification consumed by the generation pipeline."""
    projectName: str
    projectDescription: str = ""
    contractType: str = "erc20"
    contractFeatures: Dict[str, bool] = Field(default_factory=dict)
    backendType: str = "express"
    backendLanguage: str = "javascript"
    frontendFramework: str = "react"
    uiComponents: Dict[str, Any] = Field(default_factory=dict)
    securityChecks: Dict[str, bool] = Field(default_factory=lambda: {"enabled": True})
    deploymentOptions: Dict[str, Any] = Field(default_factory=lambda: {"network": "ethereum-sepolia"})
    # "llm_only", "tool_based", "hybrid", or None for automatic selection
    generationStrategy: Optional[str] = None
    preferredTools: Optional[List[str]] = None


# progress callback: (stage_name, percent_complete)
ProgressCallback = Callable[[str, int], None]


def _placeholder_abi() -> List[Dict[str, Any]]:
    """Fallback ABI when no compiler is available to produce a real one."""
    return [
        {
            "inputs": [],
            "name": "getValue",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "uint256", "name": "newValue", "type": "uint256"}],
            "name": "setValue",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]


def _safe_project_path(base_dir: Path, file_name: str) -> Optional[Path]:
    """Resolve file_name under base_dir, rejecting any path that escapes it.

    Generated file names come from LLM output; a name containing '..' or an
    absolute path must not be allowed to write outside the project directory.
    """
    candidate = (base_dir / file_name).resolve()
    base_resolved = base_dir.resolve()
    if base_resolved == candidate or base_resolved in candidate.parents:
        return candidate
    return None


class DAppGenerator:
    """Builds the agents once, then generates projects on demand.

    Typical use:
        generator = DAppGenerator()          # OpenAI backend, reads OPENAI_API_KEY
        await generator.detect_tools()       # optional, enables tool-based generation
        result = await generator.generate(spec)
        project_dir = generator.package(result, Path("./out"))
    """

    def __init__(self, llm_service=None):
        self.memory_store = InMemoryStore()
        if llm_service is None:
            from vibedapps.llm.openai_service import OpenAIService
            llm_service = OpenAIService()
        self.llm = llm_service
        self.tool_executor = ToolExecutor()
        self.tool_registry = ToolRegistry(tool_executor=self.tool_executor)
        self.tool_registry.register_default_tools()
        self.agents = self._build_agents()

    def _build_agents(self) -> Dict[str, Any]:
        contract_agent = SmartContractAgent(
            config=AgentConfig(
                name="Smart Contract Generator",
                description="Generates secure and efficient smart contract code based on specifications",
                capabilities=["erc20", "erc721", "erc1155", "dao", "defi", "marketplace", "custom"],
                model="gpt-4o",
                temperature=0.2,
                system_prompt=(
                    "You are a specialized agent for generating smart contract code. "
                    "You excel at writing secure, gas-efficient, and well-documented Solidity code. "
                    "Your task is to generate smart contracts based on user specifications, "
                    "following best practices and security standards."
                ),
            ),
            memory_store=self.memory_store,
            llm_service=self.llm,
            tool_registry=self.tool_registry,
            tool_executor=self.tool_executor,
        )

        backend_agent = BackendAgent(
            config=AgentConfig(
                name="DApp Backend Generator",
                description="Generates backend API code for interacting with blockchain and smart contracts",
                capabilities=["express", "hardhat", "truffle", "flask", "fastapi", "django", "minimal"],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a specialized agent for generating backend code for decentralized applications. "
                    "You excel at creating APIs that interact with blockchain networks and smart contracts. "
                    "Your task is to generate backend code based on user specifications, "
                    "following best practices for security and performance."
                ),
            ),
            memory_store=self.memory_store,
            llm_service=self.llm,
        )

        frontend_agent = FrontendAgent(
            config=AgentConfig(
                name="Frontend Generator",
                description="Generates modern, responsive frontend code for decentralized applications",
                capabilities=["react", "vue", "nextjs", "html"],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a specialized agent for generating frontend code for decentralized applications. "
                    "You excel at creating modern, responsive, and user-friendly interfaces that interact "
                    "with blockchain networks and smart contracts. Your task is to generate frontend code "
                    "based on user specifications, following best practices for web development and Web3 integration."
                ),
            ),
            memory_store=self.memory_store,
            llm_service=self.llm,
        )

        audit_agent = SmartContractAuditAgent(
            config=AgentConfig(
                name="Smart Contract Auditor",
                description="Audits smart contracts for security vulnerabilities and best practices",
                capabilities=["security_audit", "gas_optimization", "code_quality", "compliance_check"],
                model="gpt-4o",
                temperature=0.1,
                system_prompt=(
                    "You are a specialized agent for auditing smart contracts. "
                    "You excel at identifying security vulnerabilities, gas inefficiencies, "
                    "and code quality issues in blockchain code. Your task is to thoroughly "
                    "analyze smart contracts for potential risks, following industry best practices "
                    "and security standards."
                ),
            ),
            memory_store=self.memory_store,
            llm_service=self.llm,
        )

        test_agent = TestGeneratorAgent(memory_store=self.memory_store, llm_service=self.llm)
        integration_agent = IntegrationAgent(memory_store=self.memory_store, llm_service=self.llm)

        return {
            "contract": contract_agent,
            "backend": backend_agent,
            "frontend": frontend_agent,
            "audit": audit_agent,
            "test": test_agent,
            "integration": integration_agent,
        }

    async def detect_tools(self) -> List[str]:
        """Check which dev tools (Hardhat, Foundry, ...) exist on this machine.

        Skipping this is fine, generation just stays LLM-only.
        Returns the names of the tools that were found.
        """
        await self.tool_registry.detect_tools()
        return [tool.name for tool in self.tool_registry.get_available_tools()]

    async def generate(
        self,
        spec: ProjectSpec,
        progress: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Run all pipeline stages and return the result bundle.

        The returned dict holds project_id, the generation context, and the
        per-component outputs under "files" (contract, audit, backend,
        frontend, tests, integration). Pass it to package() to write the
        project to disk.
        """
        def report(stage: str, pct: int):
            if progress:
                progress(stage, pct)

        project_id = str(uuid.uuid4())
        specs_dict = spec.model_dump()
        context = create_context_from_specs(project_id, specs_dict)
        files: Dict[str, Any] = {}

        # ---- Stage 1: contract generation ----
        report("generating_contract", 5)
        contract_result = await self.agents["contract"].specialized_capability(
            specifications={
                "projectName": spec.projectName,
                "projectDescription": spec.projectDescription,
                "contractType": spec.contractType,
                "contractFeatures": spec.contractFeatures,
            },
            context=context,
            strategy=spec.generationStrategy,
        )
        context.add_contract_artifact(ContractArtifact(
            name=contract_result["contract_name"],
            source_code=contract_result["contract_code"],
            abi=contract_result.get("abi") or _placeholder_abi(),
            bytecode=contract_result.get("bytecode"),
        ))
        files["contract"] = contract_result

        # ---- Stage 2: security audit ----
        report("auditing_contract", 25)
        files["audit"] = await self.agents["audit"].specialized_capability(
            contract_code=contract_result["contract_code"]
        )

        # ---- Stage 3: backend (has contract ABI via context) ----
        report("generating_backend", 35)
        backend_result = await self.agents["backend"].specialized_capability(
            specifications={
                "projectName": spec.projectName,
                "projectDescription": spec.projectDescription,
                "backendType": spec.backendType,
                "backendLanguage": spec.backendLanguage,
                "deploymentOptions": spec.deploymentOptions,
            },
            context=context,
        )
        context.set_backend_artifact(BackendArtifact(
            language=backend_result["backend_language"],
            framework=backend_result["backend_type"],
            files=backend_result["files"],
            port=3001,
        ))
        files["backend"] = backend_result

        # ---- Stage 4: frontend (has contract + backend context) ----
        report("generating_frontend", 55)
        frontend_result = await self.agents["frontend"].specialized_capability(
            specifications={
                "projectName": spec.projectName,
                "projectDescription": spec.projectDescription,
                "frontendFramework": spec.frontendFramework,
                "uiComponents": spec.uiComponents,
            },
            context=context,
        )
        context.set_frontend_artifact(FrontendArtifact(
            framework=frontend_result["framework"],
            files=frontend_result["files"],
            port=3000,
        ))
        files["frontend"] = frontend_result

        # ---- Stage 5: tests ----
        report("generating_tests", 75)
        test_result = await self.agents["test"].specialized_capability(
            specifications=specs_dict,
            context=context,
        )
        context.set_test_artifact(TestArtifact(
            framework="hardhat",
            files=test_result["files"],
            test_count=test_result["test_count"],
        ))
        files["tests"] = test_result

        # ---- Stage 6: integration ----
        report("integrating", 90)
        files["integration"] = await self.agents["integration"].specialized_capability(
            specifications=specs_dict,
            context=context,
        )

        report("complete", 100)
        return {
            "project_id": project_id,
            "spec": specs_dict,
            "context": context,
            "files": files,
            "generation_strategy": context.generation_strategy,
            "tools_used": context.tools_used,
            "fallback_occurred": context.fallback_occurred,
        }

    def package(
        self,
        result: Dict[str, Any],
        output_dir: Path,
        make_zip: bool = False,
    ) -> Path:
        """Write the generated project to output_dir and return its path."""
        project_dir = Path(output_dir)
        if project_dir.exists():
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("contracts", "backend", "frontend", "test", "audit"):
            (project_dir / sub).mkdir(exist_ok=True)

        files = result["files"]
        spec = result["spec"]

        contract_data = files.get("contract")
        if contract_data:
            (project_dir / "contracts" / f"{contract_data['contract_name']}.sol").write_text(
                contract_data["contract_code"]
            )

        for component, base in (("backend", project_dir / "backend"),
                                ("frontend", project_dir / "frontend")):
            data = files.get(component) or {}
            for file_name, content in data.get("files", {}).items():
                path = _safe_project_path(base, file_name)
                if path is None:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

        # Test and integration file names already carry their own prefixes
        for component in ("tests", "integration"):
            data = files.get(component) or {}
            for file_name, content in data.get("files", {}).items():
                path = _safe_project_path(project_dir, file_name)
                if path is None:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

        audit_data = files.get("audit")
        if audit_data:
            report_lines = [
                "# Security Audit Report\n",
                f"## Risk Level: {audit_data.get('risk_level', 'Unknown')}\n",
                "## Findings:\n",
            ]
            for finding in audit_data.get("findings", []):
                report_lines += [
                    f"### {finding.get('title', 'Issue')}",
                    f"Severity: {finding.get('severity', 'Unknown')}",
                    f"Description: {finding.get('description', '')}\n",
                    f"Recommendation: {finding.get('recommendation', '')}\n",
                ]
            (project_dir / "audit" / "security_report.md").write_text("\n".join(report_lines))

        # The integration-generated package.json wires `npm test` to
        # `npx hardhat test`; ship a Hardhat config so that works as-is.
        if (files.get("tests") or {}).get("files") and not (project_dir / "hardhat.config.js").exists():
            (project_dir / "hardhat.config.js").write_text(
                'require("@nomicfoundation/hardhat-toolbox");\n\n'
                "/** @type import('hardhat/config').HardhatUserConfig */\n"
                'module.exports = {\n  solidity: "0.8.20",\n};\n'
            )

        readme = project_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {spec['projectName']}\n\n"
                f"{spec['projectDescription']}\n\n"
                "## Project Structure\n\n"
                "- `/contracts`: Smart contract code\n"
                "- `/backend`: Backend API code\n"
                "- `/frontend`: Frontend UI code\n"
                "- `/test`: Test suites\n"
                "- `/audit`: Security audit report\n\n"
                "## Generated with VibeDApps\n"
            )

        if make_zip:
            shutil.make_archive(str(project_dir), "zip", project_dir)

        return project_dir
