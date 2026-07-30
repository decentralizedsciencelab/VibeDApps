"""
Error Handling Analyzer Agent - Reviews error handling patterns.

This agent performs comprehensive error handling analysis including:
- Exception handling patterns
- Error propagation
- Logging practices
- Retry logic
- Resource cleanup
- Timeout handling
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class ErrorHandlingAgent(BaseReviewAgent):
    """Agent specialized in error handling reviews."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Error Handling Analyzer",
                description="Analyzes error handling patterns and exception management",
                capabilities=[
                    "exception_analysis",
                    "error_propagation_check",
                    "logging_review",
                    "retry_logic_check",
                    "timeout_analysis",
                    "resource_cleanup"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are an expert in error handling and exception management. "
                    "Analyze code for proper exception handling, error propagation, logging, "
                    "and resource cleanup. Focus on resilience and failure recovery patterns."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.ERROR_HANDLING

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static error handling analysis."""

        # Check for bare except clauses
        await self._check_bare_except(file_path, code)

        # Check for empty except blocks
        await self._check_empty_except(file_path, code)

        # Check for missing error logging
        await self._check_missing_logging(file_path, code)

        # Check for swallowed exceptions
        await self._check_swallowed_exceptions(file_path, code)

        # Check for missing finally blocks
        await self._check_missing_cleanup(file_path, code)

        # Check for improper exception raising
        await self._check_exception_raising(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_exception_types(file_path, code, tree)
            await self._check_resource_management(file_path, code, tree)
            await self._check_async_error_handling(file_path, code, tree)

    async def _check_bare_except(self, file_path: str, code: str) -> None:
        """Check for bare except clauses."""
        pattern = r'except\s*:'
        matches = re.finditer(pattern, code)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            snippet = self.extract_code_snippet(code, line_num)

            # Check if it's followed by proper handling
            lines = code.split('\n')
            except_line_idx = line_num - 1

            # Look at the next few lines to see if there's proper handling
            has_logging = False
            has_reraise = False
            for i in range(except_line_idx + 1, min(except_line_idx + 5, len(lines))):
                if 'logging' in lines[i] or 'logger' in lines[i] or 'log.' in lines[i]:
                    has_logging = True
                if 'raise' in lines[i]:
                    has_reraise = True

            severity = Severity.MEDIUM if (has_logging or has_reraise) else Severity.HIGH

            self.add_finding(
                severity=severity,
                category=Category.ERROR_HANDLING,
                title="Bare except clause",
                description="Catching all exceptions without specifying exception type",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Catch specific exception types (e.g., except ValueError:) or at minimum except Exception:",
                code_snippet=snippet,
                references=[
                    "https://docs.python.org/3/tutorial/errors.html#handling-exceptions"
                ],
                tags=["exceptions", "error-handling", "best-practices"]
            )

    async def _check_empty_except(self, file_path: str, code: str) -> None:
        """Check for empty except blocks (silent failures)."""
        # Pattern to match except blocks with only pass
        pattern = r'except[^:]*:\s*\n\s*pass'
        matches = re.finditer(pattern, code, re.MULTILINE)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            snippet = self.extract_code_snippet(code, line_num)

            self.add_finding(
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                title="Silent exception handling",
                description="Exception is caught but not handled or logged (pass statement only)",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Add error logging, re-raise the exception, or provide proper error handling",
                code_snippet=snippet,
                tags=["silent-failure", "exceptions", "logging"]
            )

    async def _check_missing_logging(self, file_path: str, code: str) -> None:
        """Check for exception handling without logging."""
        # Find exception handlers
        except_pattern = r'except\s+(\w+(?:\s*,\s*\w+)*)\s*(?:as\s+\w+)?\s*:'
        matches = list(re.finditer(except_pattern, code))

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1

            # Get the except block content (simplified)
            lines = code.split('\n')
            except_line_idx = line_num - 1

            # Check next 10 lines for logging
            has_logging = False
            block_end = min(except_line_idx + 10, len(lines))

            for i in range(except_line_idx, block_end):
                line = lines[i]
                if any(keyword in line for keyword in ['logging.', 'logger.', 'log.', 'print(']):
                    has_logging = True
                    break
                # Stop at next except/finally/else at same indentation
                if i > except_line_idx and re.match(r'^\s*(except|finally|else|def|class)\s', line):
                    break

            if not has_logging:
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.ERROR_HANDLING,
                    title="Exception caught without logging",
                    description="Exception is handled but not logged, making debugging difficult",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Add logging to record exception details: logger.exception() or logger.error()",
                    code_snippet=snippet,
                    tags=["logging", "exceptions", "observability"]
                )

    async def _check_swallowed_exceptions(self, file_path: str, code: str) -> None:
        """Check for exceptions that are caught and ignored."""
        # Pattern: except with only pass or continue
        patterns = [
            (r'except[^:]*:\s*\n\s*continue', "Exception swallowed with continue"),
            (r'except[^:]*:\s*\n\s*return\s+None', "Exception swallowed with return None"),
        ]

        for pattern, description in patterns:
            matches = re.finditer(pattern, code, re.MULTILINE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.ERROR_HANDLING,
                    title="Swallowed exception",
                    description=description,
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Log the exception before suppressing it, or re-raise if appropriate",
                    code_snippet=snippet,
                    tags=["swallowed-exception", "error-handling"]
                )

    async def _check_missing_cleanup(self, file_path: str, code: str) -> None:
        """Check for missing finally blocks where cleanup is needed."""
        # Look for try blocks that open files without using context managers
        pattern = r'try:\s*\n\s*.*open\('
        matches = re.finditer(pattern, code, re.MULTILINE)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1

            # Check if there's a finally block
            lines = code.split('\n')
            try_idx = line_num - 1

            has_finally = False
            for i in range(try_idx, min(try_idx + 20, len(lines))):
                if 'finally:' in lines[i]:
                    has_finally = True
                    break
                if re.match(r'^(def|class)\s', lines[i]) and i > try_idx:
                    break

            if not has_finally:
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.ERROR_HANDLING,
                    title="Missing finally block for resource cleanup",
                    description="File opened in try block without finally for cleanup",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use context manager (with statement) or add finally block to ensure cleanup",
                    code_snippet=snippet,
                    suggested_fix="with open(...) as f:\n    # your code here",
                    tags=["resource-management", "cleanup", "finally"]
                )

    async def _check_exception_raising(self, file_path: str, code: str) -> None:
        """Check for improper exception raising."""
        # Check for raising generic Exception
        pattern = r'raise\s+Exception\s*\('
        matches = re.finditer(pattern, code)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            snippet = self.extract_code_snippet(code, line_num)

            self.add_finding(
                severity=Severity.LOW,
                category=Category.BEST_PRACTICES,
                title="Raising generic Exception",
                description="Raising generic Exception makes error handling difficult for callers",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Raise specific exception types (ValueError, TypeError, etc.) or create custom exceptions",
                code_snippet=snippet,
                tags=["exceptions", "error-types"]
            )

        # Check for bare raise outside except block
        bare_raise_pattern = r'^(?!.*except).*\s+raise\s*$'
        matches = re.finditer(bare_raise_pattern, code, re.MULTILINE)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1

            # Verify it's actually outside an except block
            lines = code.split('\n')
            in_except = False
            for i in range(max(0, line_num - 10), line_num):
                if 'except' in lines[i]:
                    in_except = True
                    break

            if not in_except:
                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.ERROR_HANDLING,
                    title="Bare raise outside except block",
                    description="Bare 'raise' statement used outside exception handler",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Specify exception to raise or use bare raise only in except blocks",
                    tags=["exceptions", "raise"]
                )

    async def _check_exception_types(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for catching wrong exception types."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type:
                    # Check for catching Exception when more specific would be better
                    if isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                        # This is acceptable in some cases, make it INFO
                        self.add_finding(
                            severity=Severity.INFO,
                            category=Category.ERROR_HANDLING,
                            title="Catching broad Exception type",
                            description="Catching generic Exception - consider if more specific exception types would be better",
                            location=CodeLocation(file_path=file_path, line_start=node.lineno),
                            recommendation="Consider catching specific exceptions like ValueError, TypeError, KeyError, etc.",
                            tags=["exceptions", "exception-types"]
                        )

    async def _check_resource_management(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for proper resource management."""
        for node in ast.walk(tree):
            # Check for file.open() not in context manager
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    # Check if it's inside a 'with' statement
                    # This is a simplified check
                    if hasattr(node, 'lineno'):
                        lines = code.split('\n')
                        line_idx = node.lineno - 1

                        # Look backwards for 'with' statement
                        in_with = False
                        for i in range(max(0, line_idx - 3), line_idx + 1):
                            if 'with' in lines[i] and 'open(' in lines[i]:
                                in_with = True
                                break

                        if not in_with:
                            self.add_finding(
                                severity=Severity.MEDIUM,
                                category=Category.ERROR_HANDLING,
                                title="File opened without context manager",
                                description="File opened without 'with' statement, may not be properly closed",
                                location=CodeLocation(file_path=file_path, line_start=node.lineno),
                                recommendation="Use 'with open(...) as f:' to ensure file is properly closed",
                                suggested_fix="with open(filename) as f:\n    # your code",
                                tags=["resource-management", "context-manager"]
                            )

    async def _check_async_error_handling(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for async error handling issues."""
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check if async function has try/except
                has_try = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Try):
                        has_try = True
                        break

                # Check if function makes external calls (HTTP, DB, etc.)
                has_external_calls = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            # Look for common async operations
                            if any(name in ast.unparse(child.func) for name in ['request', 'fetch', 'query', 'execute']):
                                has_external_calls = True
                                break

                if has_external_calls and not has_try:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.ERROR_HANDLING,
                        title=f"Async function {node.name}() lacks error handling",
                        description="Async function with external calls should have try/except for resilience",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Add try/except blocks around async operations that can fail",
                        tags=["async", "error-handling", "resilience"]
                    )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get error handling patterns for matching."""
        return [
            {
                'pattern': r'except\s+\w+\s*,\s*\w+:',
                'severity': Severity.HIGH,
                'category': Category.ERROR_HANDLING,
                'title': "Old-style exception syntax",
                'description': "Using Python 2 style exception syntax (except E, e:)",
                'recommendation': "Use Python 3 syntax: except ExceptionType as e:"
            },
            {
                'pattern': r'raise\s+\w+\s*,',
                'severity': Severity.HIGH,
                'category': Category.ERROR_HANDLING,
                'title': "Old-style raise syntax",
                'description': "Using Python 2 style raise syntax",
                'recommendation': "Use Python 3 syntax: raise ExceptionType(message)"
            }
        ]
