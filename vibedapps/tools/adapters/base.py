"""
Base Tool Adapter interface for all tool integrations.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class ToolAdapter(ABC):
    """
    Abstract base class for tool adapters.
    
    Each tool adapter provides a standardized interface for interacting
    with external development tools (Hardhat, OpenZeppelin, Foundry, etc.).
    """
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """
        Initialize the tool adapter.
        
        Args:
            tool_executor: ToolExecutor instance for running commands
        """
        self.tool_executor = tool_executor or ToolExecutor()
        self._tool_name = self.__class__.__name__.replace("Adapter", "").lower()
    
    @property
    def tool_name(self) -> str:
        """Get the tool name."""
        return self._tool_name
    
    @abstractmethod
    async def initialize_project(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Initialize a project using this tool.
        
        Args:
            project_path: Path where the project should be initialized
            config: Configuration dictionary with tool-specific settings
            
        Returns:
            ToolExecutionResult with initialization results
        """
        pass
    
    @abstractmethod
    async def validate_installation(self) -> bool:
        """
        Check if the tool is properly installed and available.
        
        Returns:
            True if tool is available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_version(self) -> Optional[str]:
        """
        Get the installed version of the tool.
        
        Returns:
            Version string if available, None otherwise
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get the capabilities this tool provides.
        
        Returns:
            List of capability strings (e.g., ['contract_init', 'compile', 'test'])
        """
        pass
    
    def get_cli_command(self) -> str:
        """
        Get the CLI command used to invoke this tool.
        
        Returns:
            CLI command string (e.g., 'npx hardhat', 'forge')
        """
        return self._tool_name
    
    async def verify_project_structure(
        self,
        project_path: str,
        required_files: List[str]
    ) -> bool:
        """
        Verify that the project has the expected structure.
        
        Args:
            project_path: Path to the project
            required_files: List of required files/directories
            
        Returns:
            True if all required files exist, False otherwise
        """
        project_dir = Path(project_path)
        
        for required_file in required_files:
            file_path = project_dir / required_file
            if not file_path.exists():
                logger.warning(f"Required file missing: {required_file}")
                return False
        
        return True
    
    async def read_config_file(
        self,
        project_path: str,
        config_file: str
    ) -> Optional[Dict[str, Any]]:
        """
        Read a configuration file from the project.
        
        Args:
            project_path: Path to the project
            config_file: Name of the config file
            
        Returns:
            Configuration dictionary if successful, None otherwise
        """
        try:
            config_path = Path(project_path) / config_file
            
            if not config_path.exists():
                logger.warning(f"Config file not found: {config_file}")
                return None
            
            # Handle different config file types
            if config_file.endswith('.json'):
                import json
                with open(config_path) as f:
                    return json.load(f)
            
            elif config_file.endswith(('.yaml', '.yml')):
                try:
                    import yaml
                    with open(config_path) as f:
                        return yaml.safe_load(f)
                except ImportError:
                    logger.warning("PyYAML not installed, cannot read YAML config")
                    return None
            
            else:
                # Return raw content for other file types
                with open(config_path) as f:
                    return {"content": f.read()}
        
        except Exception as e:
            logger.error(f"Error reading config file {config_file}: {e}")
            return None
    
    async def write_config_file(
        self,
        project_path: str,
        config_file: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Write a configuration file to the project.
        
        Args:
            project_path: Path to the project
            config_file: Name of the config file
            config: Configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_path = Path(project_path) / config_file
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle different config file types
            if config_file.endswith('.json'):
                import json
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            
            elif config_file.endswith(('.yaml', '.yml')):
                try:
                    import yaml
                    with open(config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False)
                except ImportError:
                    logger.warning("PyYAML not installed, cannot write YAML config")
                    return False
            
            else:
                # Write raw content for other file types
                content = config.get("content", str(config))
                with open(config_path, 'w') as f:
                    f.write(content)
            
            return True
        
        except Exception as e:
            logger.error(f"Error writing config file {config_file}: {e}")
            return False
    
    def log_execution(
        self,
        operation: str,
        result: ToolExecutionResult
    ) -> None:
        """
        Log tool execution results.
        
        Args:
            operation: Description of the operation
            result: ToolExecutionResult to log
        """
        if result.is_success:
            logger.info(
                f"{self.tool_name} {operation} succeeded "
                f"(exit_code={result.exit_code}, time={result.execution_time:.2f}s)"
            )
        else:
            logger.error(
                f"{self.tool_name} {operation} failed "
                f"(exit_code={result.exit_code}, error={result.error_message})"
            )
    
    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(tool_name='{self.tool_name}')"


class ContractToolAdapter(ToolAdapter):
    """
    Base class for contract development tool adapters.
    
    Provides common functionality for tools like Hardhat and Foundry.
    """
    
    @abstractmethod
    async def compile_contracts(
        self,
        project_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Compile smart contracts.
        
        Args:
            project_path: Path to the project
            options: Optional compilation options
            
        Returns:
            ToolExecutionResult with compilation results
        """
        pass
    
    @abstractmethod
    async def run_tests(
        self,
        project_path: str,
        test_file: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Run contract tests.
        
        Args:
            project_path: Path to the project
            test_file: Optional specific test file to run
            options: Optional test options
            
        Returns:
            ToolExecutionResult with test results
        """
        pass
    
    async def deploy_contracts(
        self,
        project_path: str,
        network: str = "localhost",
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Deploy contracts to a network.
        
        Args:
            project_path: Path to the project
            network: Network to deploy to
            options: Optional deployment options
            
        Returns:
            ToolExecutionResult with deployment results
        """
        # Default implementation - can be overridden
        logger.warning(f"{self.tool_name} does not implement deploy_contracts")
        return ToolExecutionResult(
            command="deploy",
            exit_code=-1,
            stdout="",
            stderr="Deployment not implemented for this tool",
            execution_time=0.0,
            success=False,
            error_message="Deployment not implemented"
        )


class ScaffoldingToolAdapter(ToolAdapter):
    """
    Base class for project scaffolding tool adapters.
    
    Provides common functionality for tools like create-react-app, Vite, etc.
    """
    
    @abstractmethod
    async def scaffold_project(
        self,
        project_path: str,
        template: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Scaffold a new project.
        
        Args:
            project_path: Path where the project should be created
            template: Optional template name
            options: Optional scaffolding options
            
        Returns:
            ToolExecutionResult with scaffolding results
        """
        pass
    
    async def install_dependencies(
        self,
        project_path: str,
        package_manager: str = "npm"
    ) -> ToolExecutionResult:
        """
        Install project dependencies.
        
        Args:
            project_path: Path to the project
            package_manager: Package manager to use (npm, yarn, pnpm)
            
        Returns:
            ToolExecutionResult with installation results
        """
        logger.info(f"Installing dependencies with {package_manager}...")
        
        return await self.tool_executor.execute(
            command=package_manager,
            args=["install"],
            cwd=project_path,
            timeout=600  # 10 minutes for dependency installation
        )
