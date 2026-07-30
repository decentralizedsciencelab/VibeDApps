"""
Tool Registry for managing available development tools.
"""

import inspect
import logging
from typing import Dict, List, Optional

from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolInfo

logger = logging.getLogger(__name__)


class ToolNotAvailableError(Exception):
    """Raised when a required tool is not available."""
    
    def __init__(self, tool_name: str, message: Optional[str] = None):
        self.tool_name = tool_name
        default_message = f"Tool '{tool_name}' is not available"
        super().__init__(message or default_message)


class ToolRegistry:
    """Registry for managing available development tools."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """
        Initialize the tool registry.
        
        Args:
            tool_executor: ToolExecutor instance for running detection commands
        """
        self.tool_executor = tool_executor or ToolExecutor()
        self._tools: Dict[str, ToolInfo] = {}
        self._detection_cache: Dict[str, bool] = {}

    def register_default_tools(self) -> None:
        """Register the built-in adapters (Hardhat, OpenZeppelin, Foundry).

        Registration only declares the tools; detect_tools() decides which
        are actually available on this machine.
        """
        from vibedapps.tools.adapters.foundry import FoundryAdapter
        from vibedapps.tools.adapters.hardhat import HardhatAdapter
        from vibedapps.tools.adapters.openzeppelin import OpenZeppelinAdapter

        for adapter_cls, cli_command in (
            (HardhatAdapter, "npx hardhat"),
            (OpenZeppelinAdapter, "npx @openzeppelin/wizard"),
            (FoundryAdapter, "forge"),
        ):
            adapter = adapter_cls(self.tool_executor)
            name = adapter.tool_name
            if name in self._tools:
                continue
            self.register_tool(
                name=name,
                adapter=adapter,
                capabilities=adapter.get_capabilities(),
                cli_command=cli_command,
            )
    
    def register_tool(
        self,
        name: str,
        adapter: any,
        capabilities: List[str],
        cli_command: str,
        required_version: Optional[str] = None
    ) -> None:
        """
        Register a tool with its adapter and capabilities.
        
        Args:
            name: Tool name (e.g., 'hardhat', 'foundry')
            adapter: ToolAdapter instance
            capabilities: List of capabilities (e.g., ['contract_init', 'compile'])
            cli_command: CLI command to execute the tool (e.g., 'npx hardhat')
            required_version: Optional required version
        """
        tool_info = ToolInfo(
            name=name,
            version=None,  # Will be detected
            capabilities=capabilities,
            cli_command=cli_command,
            is_available=False,  # Will be detected
            adapter=adapter,
            metadata={"required_version": required_version} if required_version else {}
        )
        
        if not tool_info.validate():
            raise ValueError(f"Invalid tool information for {name}")
        
        self._tools[name] = tool_info
        logger.info(f"Registered tool: {name} with capabilities: {capabilities}")
    
    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            ToolInfo if found, None otherwise
        """
        return self._tools.get(name)
    
    def get_tool_adapter(self, name: str) -> Optional[any]:
        """
        Get a tool's adapter by name.
        
        Args:
            name: Tool name
            
        Returns:
            ToolAdapter instance if found, None otherwise
        """
        tool = self.get_tool(name)
        return tool.adapter if tool else None
    
    def is_available(self, name: str) -> bool:
        """
        Check if a tool is available.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool is available, False otherwise
        """
        tool = self.get_tool(name)
        return tool.is_available if tool else False
    
    def get_tools_by_capability(self, capability: str) -> List[ToolInfo]:
        """
        Get all tools that support a specific capability.
        
        Args:
            capability: Capability name (e.g., 'contract_init')
            
        Returns:
            List of ToolInfo objects with the capability
        """
        return [
            tool for tool in self._tools.values()
            if tool.has_capability(capability) and tool.is_available
        ]
    
    def get_all_tools(self) -> List[ToolInfo]:
        """
        Get all registered tools.
        
        Returns:
            List of all ToolInfo objects
        """
        return list(self._tools.values())
    
    def get_available_tools(self) -> List[ToolInfo]:
        """
        Get all available tools.
        
        Returns:
            List of available ToolInfo objects
        """
        return [tool for tool in self._tools.values() if tool.is_available]
    
    async def detect_tools(self) -> Dict[str, bool]:
        """
        Detect which tools are available in the environment.
        
        Returns:
            Dictionary mapping tool names to availability status
        """
        logger.info("Detecting available tools...")
        
        detection_results = {}
        
        for name, tool in self._tools.items():
            is_available = await self._detect_tool(name, tool)
            detection_results[name] = is_available
            
            # Update tool info
            tool.is_available = is_available
            
            if is_available:
                # Try to get version
                version = await self._get_tool_version(name, tool)
                tool.version = version
                logger.info(f"Tool '{name}' is available (version: {version or 'unknown'})")
            else:
                logger.warning(f"Tool '{name}' is not available")
        
        return detection_results
    
    async def _detect_tool(self, name: str, tool: ToolInfo) -> bool:
        """
        Detect if a specific tool is available.
        
        Args:
            name: Tool name
            tool: ToolInfo object
            
        Returns:
            True if tool is available, False otherwise
        """
        # Check cache first
        if name in self._detection_cache:
            return self._detection_cache[name]
        
        # Use tool adapter's validation if available
        if tool.adapter and hasattr(tool.adapter, 'validate_installation'):
            try:
                is_available = await tool.adapter.validate_installation()
                self._detection_cache[name] = is_available
                return is_available
            except Exception as e:
                logger.warning(f"Tool validation failed for {name}: {e}")
                self._detection_cache[name] = False
                return False
        
        # Fallback: try to execute the command with --version or --help
        try:
            # Parse the CLI command
            parts = tool.cli_command.split()
            command = parts[0]
            base_args = parts[1:] if len(parts) > 1 else []
            
            # Try --version first
            result = await self.tool_executor.execute(
                command=command,
                args=base_args + ['--version'],
                cwd='.',
                timeout=10,
                raise_on_error=False
            )
            
            if result.is_success:
                self._detection_cache[name] = True
                return True
            
            # Try --help as fallback
            result = await self.tool_executor.execute(
                command=command,
                args=base_args + ['--help'],
                cwd='.',
                timeout=10,
                raise_on_error=False
            )
            
            is_available = result.is_success
            self._detection_cache[name] = is_available
            return is_available
            
        except Exception as e:
            logger.warning(f"Tool detection failed for {name}: {e}")
            self._detection_cache[name] = False
            return False
    
    async def _get_tool_version(self, name: str, tool: ToolInfo) -> Optional[str]:
        """
        Get the version of a tool.
        
        Args:
            name: Tool name
            tool: ToolInfo object
            
        Returns:
            Version string if available, None otherwise
        """
        # Use tool adapter's get_version if available.
        # Some adapters (e.g. Hardhat) implement get_version as a coroutine
        # while others are plain sync methods — support both.
        if tool.adapter and hasattr(tool.adapter, 'get_version'):
            try:
                version = tool.adapter.get_version()
                if inspect.isawaitable(version):
                    version = await version
                return version
            except Exception as e:
                logger.warning(f"Failed to get version for {name}: {e}")
        
        # Fallback: try to parse --version output
        try:
            parts = tool.cli_command.split()
            command = parts[0]
            base_args = parts[1:] if len(parts) > 1 else []
            
            result = await self.tool_executor.execute(
                command=command,
                args=base_args + ['--version'],
                cwd='.',
                timeout=10,
                raise_on_error=False
            )
            
            if result.is_success:
                # Try to extract version from output
                output = result.stdout.strip()
                # Simple version extraction (first line, first number-like string)
                lines = output.split('\n')
                if lines:
                    first_line = lines[0]
                    # Look for version pattern (e.g., "1.2.3", "v1.2.3")
                    import re
                    version_match = re.search(r'v?(\d+\.\d+\.\d+)', first_line)
                    if version_match:
                        return version_match.group(1)
                    return first_line[:50]  # Return first 50 chars as version info
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get version for {name}: {e}")
            return None
    
    def require_tool(self, name: str) -> ToolInfo:
        """
        Get a tool and raise an error if it's not available.
        
        Args:
            name: Tool name
            
        Returns:
            ToolInfo object
            
        Raises:
            ToolNotAvailableError: If tool is not available
        """
        tool = self.get_tool(name)
        
        if not tool:
            raise ToolNotAvailableError(
                name,
                f"Tool '{name}' is not registered"
            )
        
        if not tool.is_available:
            raise ToolNotAvailableError(
                name,
                f"Tool '{name}' is registered but not available in the environment"
            )
        
        return tool
    
    def clear_cache(self) -> None:
        """Clear the detection cache."""
        self._detection_cache.clear()
        logger.info("Tool detection cache cleared")
    
    def to_dict(self) -> Dict[str, any]:
        """
        Convert registry to dictionary for serialization.
        
        Returns:
            Dictionary representation of the registry
        """
        return {
            "tools": {
                name: tool.to_dict()
                for name, tool in self._tools.items()
            },
            "available_count": len(self.get_available_tools()),
            "total_count": len(self._tools)
        }
