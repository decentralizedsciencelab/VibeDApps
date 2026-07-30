"""
Shared state passed between agents during generation.

Each pipeline stage writes its artifacts here (contract source, ABI,
backend/frontend files, deployment metadata) so later stages can read
them. This is how the backend and frontend end up with the real ABI.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from vibedapps.tools.models import ToolExecutionResult


class ContractArtifact(BaseModel):
    """Artifact data for a generated smart contract"""
    name: str
    source_code: str
    abi: List[Dict[str, Any]] = Field(default_factory=list)
    bytecode: Optional[str] = None
    deployed_address: Optional[str] = None
    deployed_network: Optional[str] = None
    deployment_tx_hash: Optional[str] = None
    constructor_args: List[Any] = Field(default_factory=list)


class BackendArtifact(BaseModel):
    """Artifact data for generated backend code"""
    language: str  # javascript, python, typescript
    framework: str  # express, flask, fastapi, django
    files: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    entry_point: str = "index.js"
    port: int = 3001
    api_endpoints: List[str] = Field(default_factory=list)
    dependencies: Dict[str, str] = Field(default_factory=dict)


class FrontendArtifact(BaseModel):
    """Artifact data for generated frontend code"""
    framework: str  # react, vue, nextjs, html
    files: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    entry_point: str = "src/App.js"
    port: int = 3000
    backend_url: str = "http://localhost:3001"
    dependencies: Dict[str, str] = Field(default_factory=dict)


class TestArtifact(BaseModel):
    """Artifact data for generated tests"""
    framework: str  # hardhat, truffle, foundry
    files: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    test_count: int = 0
    coverage_target: float = 80.0


class DeploymentArtifact(BaseModel):
    """Artifact data for deployment configuration"""
    scripts: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    networks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # network_name -> config
    deployed_contracts: Dict[str, str] = Field(default_factory=dict)  # contract_name -> address


class DAppGenerationContext(BaseModel):
    """
    Shared context for DApp generation that gets passed between agents.

    This context accumulates data as each agent completes its work:
    1. SmartContractAgent -> adds contract artifacts
    2. DeploymentAgent -> adds deployment info (addresses, networks)
    3. BackendAgent -> adds backend files and API endpoints
    4. FrontendAgent -> adds frontend files
    5. TestGeneratorAgent -> adds test files
    6. IntegrationAgent -> ties everything together

    Example usage:
        context = DAppGenerationContext(
            project_id="abc123",
            project_name="MyToken",
            project_description="An ERC20 token"
        )

        # SmartContractAgent populates:
        context.add_contract_artifact(ContractArtifact(...))

        # BackendAgent accesses contract data:
        contract = context.get_primary_contract()
        contract_abi = contract.abi
    """

    # Project metadata
    project_id: str
    project_name: str
    project_description: str
    created_at: datetime = Field(default_factory=datetime.now)

    # Original specifications from user
    specifications: Dict[str, Any] = Field(default_factory=dict)

    # Network configuration
    target_network: str = "ethereum-sepolia"
    rpc_url: Optional[str] = None
    chain_id: Optional[int] = None

    # Generated artifacts by each agent
    contracts: List[ContractArtifact] = Field(default_factory=list)
    backend: Optional[BackendArtifact] = None
    frontend: Optional[FrontendArtifact] = None
    tests: Optional[TestArtifact] = None
    deployment: Optional[DeploymentArtifact] = None

    # Environment variables that will be needed
    environment_variables: Dict[str, str] = Field(default_factory=dict)

    # Generation progress tracking
    stage: str = "initialized"  # initialized, contract_generated, deployed, backend_generated, etc.
    completed_agents: List[str] = Field(default_factory=list)
    progress: int = 0  # 0-100 percentage

    # Tool-based generation metadata
    generation_strategy: str = "llm_only"  # llm_only, tool_based, hybrid
    tools_used: List[str] = Field(default_factory=list)  # List of tool names used
    tool_execution_results: List[ToolExecutionResult] = Field(default_factory=list)
    strategy_reasoning: str = ""  # Why this strategy was chosen
    fallback_occurred: bool = False  # Whether fallback from tool to LLM occurred
    fallback_reason: str = ""  # Reason for fallback if it occurred

    class Config:
        arbitrary_types_allowed = True

    def add_contract_artifact(self, artifact: ContractArtifact) -> None:
        """Add a contract artifact to the context"""
        self.contracts.append(artifact)
        self.completed_agents.append("SmartContractAgent")
        self.stage = "contract_generated"

    def get_primary_contract(self) -> Optional[ContractArtifact]:
        """Get the primary/main contract (first one generated)"""
        return self.contracts[0] if self.contracts else None

    def get_contract_by_name(self, name: str) -> Optional[ContractArtifact]:
        """Get a specific contract by name"""
        for contract in self.contracts:
            if contract.name == name:
                return contract
        return None

    def set_backend_artifact(self, artifact: BackendArtifact) -> None:
        """Set the backend artifact"""
        self.backend = artifact
        self.completed_agents.append("BackendAgent")
        self.stage = "backend_generated"

    def set_frontend_artifact(self, artifact: FrontendArtifact) -> None:
        """Set the frontend artifact"""
        self.frontend = artifact
        self.completed_agents.append("FrontendAgent")
        self.stage = "frontend_generated"

    def set_test_artifact(self, artifact: TestArtifact) -> None:
        """Set the test artifact"""
        self.tests = artifact
        self.completed_agents.append("TestGeneratorAgent")
        self.stage = "tests_generated"

    def set_deployment_artifact(self, artifact: DeploymentArtifact) -> None:
        """Set the deployment artifact"""
        self.deployment = artifact
        self.completed_agents.append("DeploymentAgent")
        self.stage = "deployed"

    def update_contract_deployment(
        self,
        contract_name: str,
        address: str,
        network: str,
        tx_hash: str
    ) -> None:
        """Update a contract with deployment information"""
        contract = self.get_contract_by_name(contract_name)
        if contract:
            contract.deployed_address = address
            contract.deployed_network = network
            contract.deployment_tx_hash = tx_hash

            # Also update deployment artifact
            if not self.deployment:
                self.deployment = DeploymentArtifact()
            self.deployment.deployed_contracts[contract_name] = address

    def add_environment_variable(self, key: str, value: str) -> None:
        """Add an environment variable"""
        self.environment_variables[key] = value

    def set_generation_strategy(
        self,
        strategy: str,
        reasoning: str = ""
    ) -> None:
        """Set the generation strategy being used"""
        self.generation_strategy = strategy
        self.strategy_reasoning = reasoning

    def add_tool_used(self, tool_name: str) -> None:
        """Add a tool to the list of tools used"""
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

    def add_tool_execution_result(self, result: ToolExecutionResult) -> None:
        """Add a tool execution result to the context"""
        self.tool_execution_results.append(result)
        # Also add the tool to tools_used if not already there
        if result.command and result.command not in self.tools_used:
            # Extract tool name from command (e.g., "npx hardhat" -> "hardhat")
            tool_name = result.command.split()[0]
            if tool_name == "npx" and len(result.command.split()) > 1:
                tool_name = result.command.split()[1]
            self.add_tool_used(tool_name)

    def record_fallback(self, reason: str) -> None:
        """Record that a fallback from tool-based to LLM generation occurred"""
        self.fallback_occurred = True
        self.fallback_reason = reason
        # Update strategy to reflect fallback
        if self.generation_strategy == "tool_based":
            self.generation_strategy = "llm_only"
        elif self.generation_strategy == "hybrid":
            # Hybrid stays hybrid but with less tool usage
            pass

    def get_tool_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of tool executions"""
        successful = [r for r in self.tool_execution_results if r.success]
        failed = [r for r in self.tool_execution_results if not r.success]

        return {
            "total_executions": len(self.tool_execution_results),
            "successful": len(successful),
            "failed": len(failed),
            "total_execution_time": sum(r.execution_time for r in self.tool_execution_results),
            "tools_used": list(set(self.tools_used)),
            "strategy": self.generation_strategy,
            "fallback_occurred": self.fallback_occurred,
        }

    def get_contract_abi_json(self, contract_name: Optional[str] = None) -> str:
        """Get contract ABI as JSON string"""
        import json
        contract = (
            self.get_contract_by_name(contract_name)
            if contract_name
            else self.get_primary_contract()
        )
        if contract and contract.abi:
            return json.dumps(contract.abi, indent=2)
        return "[]"

    def get_integration_config(self) -> Dict[str, Any]:
        """
        Get configuration needed for integrating all components.
        This is used by IntegrationAgent to tie everything together.
        """
        primary_contract = self.get_primary_contract()

        config = {
            "project": {
                "name": self.project_name,
                "description": self.project_description,
            },
            "contracts": [
                {
                    "name": c.name,
                    "address": c.deployed_address,
                    "abi": c.abi,
                    "network": c.deployed_network,
                }
                for c in self.contracts
            ],
            "backend": {
                "port": self.backend.port if self.backend else 3001,
                "url": f"http://localhost:{self.backend.port if self.backend else 3001}",
                "endpoints": self.backend.api_endpoints if self.backend else [],
            } if self.backend else None,
            "frontend": {
                "port": self.frontend.port if self.frontend else 3000,
                "url": f"http://localhost:{self.frontend.port if self.frontend else 3000}",
            } if self.frontend else None,
            "network": {
                "name": self.target_network,
                "rpc_url": self.rpc_url,
                "chain_id": self.chain_id,
            },
            "environment": self.environment_variables,
        }

        return config

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert context to a summary dictionary for logging/debugging"""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "stage": self.stage,
            "progress": self.progress,
            "completed_agents": self.completed_agents,
            "contracts_count": len(self.contracts),
            "has_backend": self.backend is not None,
            "has_frontend": self.frontend is not None,
            "has_tests": self.tests is not None,
            "has_deployment": self.deployment is not None,
            "primary_contract": (
                {
                    "name": self.contracts[0].name,
                    "deployed": self.contracts[0].deployed_address is not None,
                    "address": self.contracts[0].deployed_address,
                }
                if self.contracts
                else None
            ),
            "generation_strategy": self.generation_strategy,
            "tools_used": self.tools_used,
            "tool_execution_summary": self.get_tool_execution_summary(),
            "fallback_occurred": self.fallback_occurred,
        }

    def is_ready_for_backend(self) -> bool:
        """Check if context has minimum data needed for backend generation"""
        return len(self.contracts) > 0 and self.contracts[0].abi

    def is_ready_for_frontend(self) -> bool:
        """Check if context has minimum data needed for frontend generation"""
        return self.backend is not None and len(self.contracts) > 0

    def is_ready_for_integration(self) -> bool:
        """Check if context has all components for final integration"""
        return (
            len(self.contracts) > 0
            and self.backend is not None
            and self.frontend is not None
        )


# Helper function to create context from project specifications
def create_context_from_specs(
    project_id: str,
    specs: Dict[str, Any]
) -> DAppGenerationContext:
    """
    Create a DAppGenerationContext from project specifications.

    Args:
        project_id: Unique project identifier
        specs: Project specifications from API request

    Returns:
        DAppGenerationContext initialized with project metadata
    """
    context = DAppGenerationContext(
        project_id=project_id,
        project_name=specs.get("projectName", "DApp"),
        project_description=specs.get("projectDescription", ""),
        specifications=specs,
    )

    # Extract network configuration if available
    deployment_options = specs.get("deploymentOptions", {})
    context.target_network = deployment_options.get("network", "ethereum-sepolia")

    # Add common environment variables
    context.add_environment_variable("PROJECT_NAME", context.project_name)
    context.add_environment_variable("NETWORK", context.target_network)

    return context
