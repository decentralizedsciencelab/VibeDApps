"""
Data models for the Tool Execution Layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ToolExecutionResult:
    """Result of executing an external tool command."""
    
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float  # seconds
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.success and self.exit_code == 0
    
    @property
    def output(self) -> str:
        """Get combined output (stdout + stderr)."""
        return f"{self.stdout}\n{self.stderr}".strip()


@dataclass
class ToolInfo:
    """Information about an available development tool."""
    
    name: str
    version: Optional[str]
    capabilities: List[str]
    cli_command: str
    is_available: bool
    adapter: Optional[Any] = None  # ToolAdapter instance
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "cli_command": self.cli_command,
            "is_available": self.is_available,
            "metadata": self.metadata,
        }
    
    def has_capability(self, capability: str) -> bool:
        """Check if tool has a specific capability."""
        return capability in self.capabilities
    
    def validate(self) -> bool:
        """Validate tool information."""
        if not self.name or not self.cli_command:
            return False
        if not self.capabilities:
            return False
        return True


@dataclass
class GenerationResult:
    """Result of a DApp generation process."""
    
    success: bool
    files_generated: List[str]
    errors: List[str]
    strategy_used: str
    tools_used: List[str]
    tool_execution_results: List[ToolExecutionResult]
    llm_customizations: List[str]  # Files customized by LLM
    generation_time: float  # seconds
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "files_generated": self.files_generated,
            "errors": self.errors,
            "strategy_used": self.strategy_used,
            "tools_used": self.tools_used,
            "tool_execution_results": [r.to_dict() for r in self.tool_execution_results],
            "llm_customizations": self.llm_customizations,
            "generation_time": self.generation_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
    
    @property
    def total_files(self) -> int:
        """Get total number of files generated."""
        return len(self.files_generated)
    
    @property
    def has_errors(self) -> bool:
        """Check if there were any errors."""
        return len(self.errors) > 0
    
    @property
    def tool_execution_count(self) -> int:
        """Get number of tool executions."""
        return len(self.tool_execution_results)
