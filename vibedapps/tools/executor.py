"""
Tool Executor for running external CLI tools.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    
    def __init__(
        self,
        tool_name: str,
        command: str,
        exit_code: int,
        stderr: str
    ):
        self.tool_name = tool_name
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"Tool {tool_name} failed with exit code {exit_code}: {stderr}")


class ToolExecutor:
    """Executes external CLI tools and captures output."""
    
    def __init__(self, default_timeout: int = 300):
        """
        Initialize the tool executor.
        
        Args:
            default_timeout: Default timeout in seconds for tool execution
        """
        self.default_timeout = default_timeout
    
    async def execute(
        self,
        command: str,
        args: List[str],
        cwd: str,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        raise_on_error: bool = False
    ) -> ToolExecutionResult:
        """
        Execute a tool command and return results.
        
        Args:
            command: The command to execute (e.g., 'npx', 'forge')
            args: List of arguments for the command
            cwd: Working directory for command execution
            timeout: Timeout in seconds (uses default if None)
            env: Environment variables to set
            raise_on_error: Whether to raise exception on non-zero exit code
            
        Returns:
            ToolExecutionResult with execution details
            
        Raises:
            ToolExecutionError: If raise_on_error is True and command fails
            asyncio.TimeoutError: If execution exceeds timeout
        """
        timeout = timeout or self.default_timeout
        full_command = f"{command} {' '.join(args)}"
        
        logger.info(f"Executing tool command: {full_command}")
        logger.info(f"Working directory: {cwd}")
        
        # Ensure working directory exists
        Path(cwd).mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Wait for completion with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Kill the process on timeout
                process.kill()
                await process.wait()
                
                execution_time = time.time() - start_time
                error_msg = f"Command timed out after {timeout} seconds"
                
                logger.error(f"Tool execution timed out: {full_command}")
                
                result = ToolExecutionResult(
                    command=full_command,
                    exit_code=-1,
                    stdout="",
                    stderr=error_msg,
                    execution_time=execution_time,
                    success=False,
                    error_message=error_msg
                )
                
                if raise_on_error:
                    raise ToolExecutionError(
                        tool_name=command,
                        command=full_command,
                        exit_code=-1,
                        stderr=error_msg
                    )
                
                return result
            
            # Decode output
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')
            exit_code = process.returncode
            execution_time = time.time() - start_time
            
            success = exit_code == 0
            error_message = stderr if not success else None
            
            logger.info(f"Tool execution completed: exit_code={exit_code}, time={execution_time:.2f}s")
            
            if not success:
                logger.warning(f"Tool execution failed: {stderr[:200]}")
            
            result = ToolExecutionResult(
                command=full_command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                success=success,
                error_message=error_message
            )
            
            if raise_on_error and not success:
                raise ToolExecutionError(
                    tool_name=command,
                    command=full_command,
                    exit_code=exit_code,
                    stderr=stderr
                )
            
            return result
            
        except FileNotFoundError:
            execution_time = time.time() - start_time
            error_msg = f"Command not found: {command}"
            
            logger.error(error_msg)
            
            result = ToolExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            
            if raise_on_error:
                raise ToolExecutionError(
                    tool_name=command,
                    command=full_command,
                    exit_code=-1,
                    stderr=error_msg
                )
            
            return result
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Unexpected error: {str(e)}"
            
            logger.error(f"Tool execution error: {error_msg}", exc_info=True)
            
            result = ToolExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
            
            if raise_on_error:
                raise ToolExecutionError(
                    tool_name=command,
                    command=full_command,
                    exit_code=-1,
                    stderr=error_msg
                )
            
            return result
    
    async def execute_with_streaming(
        self,
        command: str,
        args: List[str],
        cwd: str,
        output_callback: Callable[[str], None],
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None
    ) -> ToolExecutionResult:
        """
        Execute a tool with streaming output.
        
        Args:
            command: The command to execute
            args: List of arguments
            cwd: Working directory
            output_callback: Callback function for streaming output
            timeout: Timeout in seconds
            env: Environment variables
            
        Returns:
            ToolExecutionResult with execution details
        """
        timeout = timeout or self.default_timeout
        full_command = f"{command} {' '.join(args)}"
        
        logger.info(f"Executing tool command with streaming: {full_command}")
        
        # Ensure working directory exists
        Path(cwd).mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        stdout_lines = []
        stderr_lines = []
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Read output streams concurrently
            async def read_stream(stream, lines_list, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    
                    line_str = line.decode('utf-8', errors='replace').rstrip()
                    lines_list.append(line_str)
                    
                    # Call output callback
                    if output_callback:
                        try:
                            output_callback(line_str)
                        except Exception as e:
                            logger.warning(f"Output callback error: {e}")
            
            # Read both streams and wait for exit, all under ONE timeout.
            # (Guarding only process.wait() is not enough: a hung tool that
            # keeps its pipes open blocks readline() forever and the timeout
            # would never fire.)
            async def _consume_and_wait() -> int:
                await asyncio.gather(
                    read_stream(process.stdout, stdout_lines),
                    read_stream(process.stderr, stderr_lines, is_stderr=True)
                )
                return await process.wait()

            exit_code = await asyncio.wait_for(_consume_and_wait(), timeout=timeout)
            
            execution_time = time.time() - start_time
            stdout = '\n'.join(stdout_lines)
            stderr = '\n'.join(stderr_lines)
            success = exit_code == 0
            
            logger.info(f"Streaming execution completed: exit_code={exit_code}, time={execution_time:.2f}s")
            
            return ToolExecutionResult(
                command=full_command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                success=success,
                error_message=stderr if not success else None
            )
            
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            
            execution_time = time.time() - start_time
            error_msg = f"Command timed out after {timeout} seconds"
            
            logger.error(f"Streaming execution timed out: {full_command}")
            
            return ToolExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout='\n'.join(stdout_lines),
                stderr=error_msg,
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Unexpected error: {str(e)}"
            
            logger.error(f"Streaming execution error: {error_msg}", exc_info=True)
            
            return ToolExecutionResult(
                command=full_command,
                exit_code=-1,
                stdout='\n'.join(stdout_lines),
                stderr=error_msg,
                execution_time=execution_time,
                success=False,
                error_message=error_msg
            )
