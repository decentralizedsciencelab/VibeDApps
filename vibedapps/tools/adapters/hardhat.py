"""
Hardhat Adapter for smart contract development.

Hardhat is a popular Ethereum development environment for compiling,
deploying, testing, and debugging smart contracts.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.adapters.base import ContractToolAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class HardhatAdapter(ContractToolAdapter):
    """Adapter for Hardhat smart contract development framework."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """Initialize the Hardhat adapter."""
        super().__init__(tool_executor)
        self._tool_name = "hardhat"
    
    def get_cli_command(self) -> str:
        """Get the CLI command for Hardhat."""
        return "npx hardhat"
    
    def get_capabilities(self) -> List[str]:
        """Get Hardhat capabilities."""
        return [
            "contract_init",
            "contract_compile",
            "contract_test",
            "contract_deploy",
            "contract_verify",
            "local_network",
            "task_runner"
        ]
    
    async def validate_installation(self) -> bool:
        """
        Check if Hardhat is available.
        
        Returns:
            True if Hardhat is available, False otherwise
        """
        try:
            result = await self.tool_executor.execute(
                command="npx",
                args=["hardhat", "--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            )
            
            return result.is_success
        
        except Exception as e:
            logger.warning(f"Hardhat validation failed: {e}")
            return False
    
    async def get_version(self) -> Optional[str]:
        """
        Get Hardhat version.

        Returns:
            Version string if available, None otherwise
        """
        try:
            result = await self.tool_executor.execute(
                command="npx",
                args=["hardhat", "--version"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            )

            if result.is_success:
                # Parse version from output (e.g., "2.19.0")
                import re
                version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    return version_match.group(1)
                return result.stdout.strip().split('\n')[0][:50]
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to get Hardhat version: {e}")
            return None
    
    async def initialize_project(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Initialize a Hardhat project.
        
        Args:
            project_path: Path where the project should be initialized
            config: Configuration with options:
                - project_type: "javascript" or "typescript" (default: "javascript")
                - install_dependencies: bool (default: True)
                - sample_project: bool (default: True)
                
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info(f"Initializing Hardhat project at {project_path}")
        
        # Create project directory
        project_dir = Path(project_path)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Get configuration
        project_type = config.get("project_type", "javascript")
        install_deps = config.get("install_dependencies", True)
        sample_project = config.get("sample_project", True)
        
        # Initialize npm project first
        logger.info("Initializing npm project...")
        npm_init_result = await self.tool_executor.execute(
            command="npm",
            args=["init", "-y"],
            cwd=project_path,
            timeout=60
        )
        
        if not npm_init_result.is_success:
            logger.error("Failed to initialize npm project")
            return npm_init_result
        
        # Install Hardhat
        logger.info("Installing Hardhat...")
        install_result = await self.tool_executor.execute(
            command="npm",
            # Pin to Hardhat 2.x: the generated hardhat.config.js is CommonJS
            # (require("@nomicfoundation/hardhat-toolbox")), which Hardhat 3 rejects.
            args=["install", "--save-dev", "hardhat@^2.26.0", "@nomicfoundation/hardhat-toolbox@^5.0.0"],
            cwd=project_path,
            timeout=300  # 5 minutes for installation
        )
        
        if not install_result.is_success:
            logger.error("Failed to install Hardhat")
            return install_result
        
        # Create hardhat.config.js
        logger.info("Creating Hardhat configuration...")
        config_content = self._generate_hardhat_config(config)
        config_file = project_dir / "hardhat.config.js"
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Create project structure
        await self._create_project_structure(project_path, sample_project)
        
        # Verify project structure
        required_files = [
            "hardhat.config.js",
            "contracts",
            "scripts",
            "test"
        ]
        
        structure_valid = await self.verify_project_structure(project_path, required_files)
        
        if not structure_valid:
            return ToolExecutionResult(
                command="hardhat init",
                exit_code=1,
                stdout="",
                stderr="Project structure validation failed",
                execution_time=0.0,
                success=False,
                error_message="Required files/directories missing"
            )
        
        logger.info("Hardhat project initialized successfully")
        
        return ToolExecutionResult(
            command="hardhat init",
            exit_code=0,
            stdout=f"Hardhat project initialized at {project_path}",
            stderr="",
            execution_time=install_result.execution_time,
            success=True
        )
    
    async def compile_contracts(
        self,
        project_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Compile smart contracts using Hardhat.
        
        Args:
            project_path: Path to the Hardhat project
            options: Optional compilation options:
                - force: bool - Force recompilation
                - quiet: bool - Suppress output
                
        Returns:
            ToolExecutionResult with compilation results
        """
        logger.info(f"Compiling contracts in {project_path}")
        
        options = options or {}
        args = ["hardhat", "compile"]
        
        if options.get("force"):
            args.append("--force")
        
        if options.get("quiet"):
            args.append("--quiet")
        
        result = await self.tool_executor.execute(
            command="npx",
            args=args,
            cwd=project_path,
            timeout=300  # 5 minutes for compilation
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
        Run contract tests using Hardhat.
        
        Args:
            project_path: Path to the Hardhat project
            test_file: Optional specific test file to run
            options: Optional test options:
                - parallel: bool - Run tests in parallel
                - bail: bool - Stop on first failure
                
        Returns:
            ToolExecutionResult with test results
        """
        logger.info(f"Running tests in {project_path}")
        
        options = options or {}
        args = ["hardhat", "test"]
        
        if test_file:
            args.append(test_file)
        
        if options.get("parallel"):
            args.append("--parallel")
        
        if options.get("bail"):
            args.append("--bail")
        
        result = await self.tool_executor.execute(
            command="npx",
            args=args,
            cwd=project_path,
            timeout=600  # 10 minutes for tests
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
        Deploy contracts using Hardhat.
        
        Args:
            project_path: Path to the Hardhat project
            network: Network to deploy to (localhost, sepolia, mainnet, etc.)
            options: Optional deployment options:
                - script: str - Deployment script path (default: "scripts/deploy.js")
                
        Returns:
            ToolExecutionResult with deployment results
        """
        logger.info(f"Deploying contracts to {network}")
        
        options = options or {}
        script = options.get("script", "scripts/deploy.js")
        
        args = ["hardhat", "run", script, "--network", network]
        
        result = await self.tool_executor.execute(
            command="npx",
            args=args,
            cwd=project_path,
            timeout=300  # 5 minutes for deployment
        )
        
        self.log_execution("deployment", result)
        
        return result
    
    async def start_local_node(
        self,
        project_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Start a local Hardhat node.
        
        Args:
            project_path: Path to the Hardhat project
            options: Optional node options:
                - port: int - Port to run on (default: 8545)
                - fork: str - Fork from a network
                
        Returns:
            ToolExecutionResult with node startup results
        """
        logger.info("Starting Hardhat local node")
        
        options = options or {}
        args = ["hardhat", "node"]
        
        if options.get("port"):
            args.extend(["--port", str(options["port"])])
        
        if options.get("fork"):
            args.extend(["--fork", options["fork"]])
        
        # Note: This starts a long-running process
        # In practice, this should be run in the background
        result = await self.tool_executor.execute(
            command="npx",
            args=args,
            cwd=project_path,
            timeout=30  # Just check if it starts
        )
        
        return result
    
    async def get_contract_artifacts(
        self,
        project_path: str,
        contract_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get compiled contract artifacts.
        
        Args:
            project_path: Path to the Hardhat project
            contract_name: Name of the contract
            
        Returns:
            Contract artifacts (ABI, bytecode, etc.) or None
        """
        try:
            artifacts_path = Path(project_path) / "artifacts" / "contracts" / f"{contract_name}.sol" / f"{contract_name}.json"
            
            if not artifacts_path.exists():
                logger.warning(f"Artifacts not found for {contract_name}")
                return None
            
            with open(artifacts_path) as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error reading contract artifacts: {e}")
            return None
    
    def _generate_hardhat_config(self, config: Dict[str, Any]) -> str:
        """
        Generate hardhat.config.js content.
        
        Args:
            config: Configuration options
            
        Returns:
            Configuration file content
        """
        solidity_version = config.get("solidity_version", "0.8.20")
        
        config_content = f'''require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {{
  solidity: "{solidity_version}",
  networks: {{
    hardhat: {{
      chainId: 1337
    }},
    localhost: {{
      url: "http://127.0.0.1:8545"
    }}
  }},
  paths: {{
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }}
}};
'''
        return config_content
    
    async def _create_project_structure(
        self,
        project_path: str,
        sample_project: bool = True
    ) -> None:
        """
        Create Hardhat project directory structure.
        
        Args:
            project_path: Path to the project
            sample_project: Whether to create sample files
        """
        project_dir = Path(project_path)
        
        # Create directories
        (project_dir / "contracts").mkdir(exist_ok=True)
        (project_dir / "scripts").mkdir(exist_ok=True)
        (project_dir / "test").mkdir(exist_ok=True)
        
        if sample_project:
            # Create sample contract
            sample_contract = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Lock {
    uint public unlockTime;
    address payable public owner;

    event Withdrawal(uint amount, uint when);

    constructor(uint _unlockTime) payable {
        require(
            block.timestamp < _unlockTime,
            "Unlock time should be in the future"
        );

        unlockTime = _unlockTime;
        owner = payable(msg.sender);
    }

    function withdraw() public {
        require(block.timestamp >= unlockTime, "You can't withdraw yet");
        require(msg.sender == owner, "You aren't the owner");

        emit Withdrawal(address(this).balance, block.timestamp);

        owner.transfer(address(this).balance);
    }
}
'''
            
            with open(project_dir / "contracts" / "Lock.sol", 'w') as f:
                f.write(sample_contract)
            
            # Create sample deployment script
            deploy_script = '''const hre = require("hardhat");

async function main() {
  const currentTimestampInSeconds = Math.round(Date.now() / 1000);
  const unlockTime = currentTimestampInSeconds + 60;

  const lockedAmount = hre.ethers.parseEther("0.001");

  const lock = await hre.ethers.deployContract("Lock", [unlockTime], {
    value: lockedAmount,
  });

  await lock.waitForDeployment();

  console.log(
    `Lock with ${ethers.formatEther(
      lockedAmount
    )}ETH and unlock timestamp ${unlockTime} deployed to ${lock.target}`
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
'''
            
            with open(project_dir / "scripts" / "deploy.js", 'w') as f:
                f.write(deploy_script)
            
            # Create sample test
            test_file = '''const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Lock", function () {
  it("Should set the right unlockTime", async function () {
    const unlockTime = Math.round(Date.now() / 1000) + 60;
    const Lock = await ethers.getContractFactory("Lock");
    const lock = await Lock.deploy(unlockTime, { value: ethers.parseEther("0.001") });
    
    expect(await lock.unlockTime()).to.equal(unlockTime);
  });

  it("Should set the right owner", async function () {
    const unlockTime = Math.round(Date.now() / 1000) + 60;
    const [owner] = await ethers.getSigners();
    const Lock = await ethers.getContractFactory("Lock");
    const lock = await Lock.deploy(unlockTime, { value: ethers.parseEther("0.001") });
    
    expect(await lock.owner()).to.equal(owner.address);
  });
});
'''
            
            with open(project_dir / "test" / "Lock.js", 'w') as f:
                f.write(test_file)
        
        logger.info("Project structure created")
