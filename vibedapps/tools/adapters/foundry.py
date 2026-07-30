"""
Foundry Adapter for smart contract development.

Foundry is a blazing fast, portable and modular toolkit for Ethereum
application development written in Rust. It includes forge (build/test),
cast (interact with contracts), and anvil (local node).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.adapters.base import ContractToolAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class FoundryAdapter(ContractToolAdapter):
    """Adapter for Foundry smart contract development framework."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """Initialize the Foundry adapter."""
        super().__init__(tool_executor)
        self._tool_name = "foundry"
    
    def get_cli_command(self) -> str:
        """Get the CLI command for Foundry."""
        return "forge"
    
    def get_capabilities(self) -> List[str]:
        """Get Foundry capabilities."""
        return [
            "contract_init",
            "contract_compile",
            "contract_test",
            "contract_deploy",
            "gas_optimization",
            "fuzz_testing",
            "local_network"
        ]
    
    async def validate_installation(self) -> bool:
        """
        Check if Foundry is available.
        
        Returns:
            True if Foundry is available, False otherwise
        """
        try:
            result = await self.tool_executor.execute(
                command="forge",
                args=["--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            )
            
            return result.is_success
        
        except Exception as e:
            logger.warning(f"Foundry validation failed: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """
        Get Foundry version.
        
        Returns:
            Version string if available, None otherwise
        """
        try:
            import asyncio
            
            result = asyncio.run(self.tool_executor.execute(
                command="forge",
                args=["--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            ))
            
            if result.is_success:
                # Parse version from output
                import re
                version_match = re.search(r'forge (\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    return version_match.group(1)
                return result.stdout.strip().split('\n')[0][:50]
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to get Foundry version: {e}")
            return None
    
    async def initialize_project(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Initialize a Foundry project.
        
        Args:
            project_path: Path where the project should be initialized
            config: Configuration with options:
                - template: str - Template to use (default: none)
                - no_commit: bool - Don't create git commit (default: True)
                
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info(f"Initializing Foundry project at {project_path}")
        
        # Create project directory
        project_dir = Path(project_path)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Get configuration
        template = config.get("template")
        no_commit = config.get("no_commit", True)
        
        # Build forge init command
        args = ["init"]
        
        if template:
            args.extend(["--template", template])
        
        if no_commit:
            args.append("--no-commit")
        
        # Force init even if directory is not empty
        args.append("--force")
        
        # Initialize Foundry project
        result = await self.tool_executor.execute(
            command="forge",
            args=args,
            cwd=project_path,
            timeout=120
        )
        
        if result.is_success:
            # Verify project structure
            required_files = [
                "foundry.toml",
                "src",
                "test",
                "script"
            ]
            
            structure_valid = await self.verify_project_structure(project_path, required_files)
            
            if not structure_valid:
                result.success = False
                result.error_message = "Project structure validation failed"
        
        self.log_execution("initialization", result)
        
        return result
    
    async def compile_contracts(
        self,
        project_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Compile smart contracts using Foundry.
        
        Args:
            project_path: Path to the Foundry project
            options: Optional compilation options:
                - optimize: bool - Enable optimization
                - optimizer_runs: int - Number of optimizer runs
                - force: bool - Force recompilation
                
        Returns:
            ToolExecutionResult with compilation results
        """
        logger.info(f"Compiling contracts with Foundry in {project_path}")
        
        options = options or {}
        args = ["build"]
        
        if options.get("force"):
            args.append("--force")
        
        if options.get("optimize"):
            optimizer_runs = options.get("optimizer_runs", 200)
            args.extend(["--optimize", "--optimizer-runs", str(optimizer_runs)])
        
        result = await self.tool_executor.execute(
            command="forge",
            args=args,
            cwd=project_path,
            timeout=300
        )
        
        self.log_execution("compilation", result)
        
        return result
    
    async def run_tests(
        self,
        project_path: str,
        test_file: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Run contract tests using Foundry.
        
        Args:
            project_path: Path to the Foundry project
            test_file: Optional specific test file or contract to run
            options: Optional test options:
                - match_test: str - Run tests matching pattern
                - match_contract: str - Run tests in matching contract
                - gas_report: bool - Show gas report
                - verbosity: int - Verbosity level (0-5)
                
        Returns:
            ToolExecutionResult with test results
        """
        logger.info(f"Running tests with Foundry in {project_path}")
        
        options = options or {}
        args = ["test"]
        
        if test_file:
            args.extend(["--match-path", test_file])
        
        if options.get("match_test"):
            args.extend(["--match-test", options["match_test"]])
        
        if options.get("match_contract"):
            args.extend(["--match-contract", options["match_contract"]])
        
        if options.get("gas_report"):
            args.append("--gas-report")
        
        verbosity = options.get("verbosity", 2)
        args.append("-" + "v" * verbosity)
        
        result = await self.tool_executor.execute(
            command="forge",
            args=args,
            cwd=project_path,
            timeout=600
        )
        
        self.log_execution("testing", result)
        
        return result
    
    async def deploy_contracts(
        self,
        project_path: str,
        network: str = "localhost",
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Deploy contracts using Foundry.
        
        Args:
            project_path: Path to the Foundry project
            network: Network to deploy to
            options: Optional deployment options:
                - script: str - Deployment script path
                - rpc_url: str - RPC URL
                - private_key: str - Private key for deployment
                - broadcast: bool - Broadcast transactions
                
        Returns:
            ToolExecutionResult with deployment results
        """
        logger.info(f"Deploying contracts with Foundry to {network}")
        
        options = options or {}
        script = options.get("script", "script/Deploy.s.sol")
        
        args = ["script", script]
        
        if options.get("rpc_url"):
            args.extend(["--rpc-url", options["rpc_url"]])
        elif network == "localhost":
            args.extend(["--rpc-url", "http://127.0.0.1:8545"])
        
        if options.get("private_key"):
            args.extend(["--private-key", options["private_key"]])
        
        if options.get("broadcast"):
            args.append("--broadcast")
        
        result = await self.tool_executor.execute(
            command="forge",
            args=args,
            cwd=project_path,
            timeout=300
        )
        
        self.log_execution("deployment", result)
        
        return result
    
    async def run_gas_snapshot(
        self,
        project_path: str
    ) -> ToolExecutionResult:
        """
        Generate gas usage snapshot.
        
        Args:
            project_path: Path to the Foundry project
            
        Returns:
            ToolExecutionResult with gas snapshot results
        """
        logger.info("Generating gas snapshot")
        
        result = await self.tool_executor.execute(
            command="forge",
            args=["snapshot"],
            cwd=project_path,
            timeout=300
        )
        
        self.log_execution("gas snapshot", result)
        
        return result
    
    async def format_code(
        self,
        project_path: str
    ) -> ToolExecutionResult:
        """
        Format Solidity code using Foundry's formatter.
        
        Args:
            project_path: Path to the Foundry project
            
        Returns:
            ToolExecutionResult with formatting results
        """
        logger.info("Formatting code with forge fmt")
        
        result = await self.tool_executor.execute(
            command="forge",
            args=["fmt"],
            cwd=project_path,
            timeout=60
        )
        
        self.log_execution("formatting", result)
        
        return result
    
    async def start_local_node(
        self,
        project_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Start a local Anvil node (Foundry's local Ethereum node).
        
        Args:
            project_path: Path to the Foundry project
            options: Optional node options:
                - port: int - Port to run on (default: 8545)
                - accounts: int - Number of accounts (default: 10)
                - fork_url: str - Fork from a network
                
        Returns:
            ToolExecutionResult with node startup results
        """
        logger.info("Starting Anvil local node")
        
        options = options or {}
        args = []
        
        if options.get("port"):
            args.extend(["--port", str(options["port"])])
        
        if options.get("accounts"):
            args.extend(["--accounts", str(options["accounts"])])
        
        if options.get("fork_url"):
            args.extend(["--fork-url", options["fork_url"]])
        
        # Note: This starts a long-running process
        result = await self.tool_executor.execute(
            command="anvil",
            args=args,
            cwd=project_path,
            timeout=30  # Just check if it starts
        )
        
        return result
