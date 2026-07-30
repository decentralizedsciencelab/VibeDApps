"""
Performance Analyzer Agent - Reviews code for performance bottlenecks.

This agent performs comprehensive performance analysis including:
- Async/await pattern validation
- Blocking I/O detection
- N+1 query problems
- Caching opportunities
- Memory leak patterns
- Algorithm efficiency
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class PerformanceAgent(BaseReviewAgent):
    """Agent specialized in performance analysis."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Performance Analyzer",
                description="Identifies performance bottlenecks and optimization opportunities",
                capabilities=[
                    "async_pattern_review",
                    "database_query_analysis",
                    "caching_opportunities",
                    "n_plus_one_detection",
                    "memory_leak_scan",
                    "io_optimization",
                    "algorithm_efficiency"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a performance optimization expert. Analyze code for performance "
                    "bottlenecks, inefficient algorithms, blocking operations, and opportunities "
                    "for optimization. Focus on scalability and resource efficiency."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.PERFORMANCE

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static performance analysis."""

        # Check for blocking I/O in async functions
        await self._check_blocking_io_in_async(file_path, code)

        # Check for synchronous HTTP calls
        await self._check_sync_http_calls(file_path, code)

        # Check for missing database connection pooling
        await self._check_db_connection_pooling(file_path, code)

        # Check for N+1 query patterns
        await self._check_n_plus_one_queries(file_path, code)

        # Check for missing caching
        await self._check_missing_caching(file_path, code)

        # Check for inefficient string concatenation
        await self._check_string_concatenation(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_loop_inefficiencies(file_path, code, tree)
            await self._check_unbounded_collections(file_path, code, tree)
            await self._check_repeated_calculations(file_path, code, tree)
            await self._check_async_patterns(file_path, code, tree)

    async def _check_blocking_io_in_async(self, file_path: str, code: str) -> None:
        """Check for blocking I/O operations in async functions."""
        blocking_patterns = [
            (r'async\s+def[^:]+:.*\n(?:.*\n)*?.*time\.sleep\(', "time.sleep() in async function"),
            (r'async\s+def[^:]+:.*\n(?:.*\n)*?.*requests\.', "requests library in async function"),
            (r'async\s+def[^:]+:.*\n(?:.*\n)*?.*urllib\.', "urllib in async function"),
        ]

        for pattern, description in blocking_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1

                self.add_finding(
                    severity=Severity.HIGH,
                    category=Category.PERFORMANCE,
                    title="Blocking I/O in async function",
                    description=f"{description} - blocks the event loop",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use async alternatives: asyncio.sleep(), httpx, or aiohttp",
                    tags=["async", "blocking-io", "performance"]
                )

    async def _check_sync_http_calls(self, file_path: str, code: str) -> None:
        """Check for synchronous HTTP calls."""
        # Check for requests library usage
        if 'import requests' in code or 'from requests' in code:
            pattern = r'requests\.(get|post|put|delete|patch)\('
            matches = re.finditer(pattern, code)

            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                # Check if we're in an async context
                lines = code.split('\n')
                in_async = False
                for i in range(max(0, line_num - 20), line_num):
                    if 'async def' in lines[i]:
                        in_async = True
                        break

                severity = Severity.HIGH if in_async else Severity.MEDIUM

                self.add_finding(
                    severity=severity,
                    category=Category.PERFORMANCE,
                    title="Synchronous HTTP call",
                    description="Using synchronous requests library can block execution",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use httpx.AsyncClient() or aiohttp for async HTTP requests",
                    code_snippet=snippet,
                    suggested_fix="async with httpx.AsyncClient() as client:\n    response = await client.get(url)",
                    tags=["http", "async", "blocking"]
                )

    async def _check_db_connection_pooling(self, file_path: str, code: str) -> None:
        """Check for missing database connection pooling."""
        # Look for database connections without pooling
        db_patterns = [
            (r'sqlite3\.connect\(', "SQLite connection without pooling"),
            (r'psycopg2\.connect\(', "PostgreSQL connection without pooling"),
            (r'pymongo\.MongoClient\(', "MongoDB client without connection pooling configuration"),
        ]

        for pattern, description in db_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1

                # Check if this is inside a function that gets called repeatedly
                lines = code.split('\n')
                in_loop = False
                in_endpoint = False

                for i in range(max(0, line_num - 10), line_num):
                    if any(keyword in lines[i] for keyword in ['for ', 'while ']):
                        in_loop = True
                    if any(keyword in lines[i] for keyword in ['@app.', 'def handle', 'def process']):
                        in_endpoint = True

                if in_loop or in_endpoint:
                    snippet = self.extract_code_snippet(code, line_num)

                    self.add_finding(
                        severity=Severity.HIGH,
                        category=Category.PERFORMANCE,
                        title="Database connection without pooling",
                        description=f"{description} - creates new connection on each call",
                        location=CodeLocation(file_path=file_path, line_start=line_num),
                        recommendation="Use connection pooling to reuse connections",
                        code_snippet=snippet,
                        tags=["database", "connection-pooling", "performance"]
                    )

    async def _check_n_plus_one_queries(self, file_path: str, code: str) -> None:
        """Check for N+1 query patterns."""
        # Look for loops that make database queries
        pattern = r'for\s+\w+\s+in\s+[^:]+:.*\n\s+.*\.(query|filter|get|find)\('
        matches = re.finditer(pattern, code, re.MULTILINE)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            snippet = self.extract_code_snippet(code, line_num, line_num + 2)

            self.add_finding(
                severity=Severity.HIGH,
                category=Category.PERFORMANCE,
                title="Potential N+1 query problem",
                description="Database query inside loop may cause N+1 performance issue",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Use eager loading, joins, or batch queries to fetch related data",
                code_snippet=snippet,
                references=[
                    "https://secure.phabricator.com/book/phabcontrib/article/n_plus_one/"
                ],
                tags=["n-plus-one", "database", "queries"]
            )

    async def _check_missing_caching(self, file_path: str, code: str) -> None:
        """Check for opportunities to add caching."""
        # Look for expensive operations without caching
        expensive_patterns = [
            (r'def\s+\w+\([^)]*\):.*\n(?:.*\n)*?.*requests\.get\(', "HTTP requests"),
            (r'def\s+\w+\([^)]*\):.*\n(?:.*\n)*?.*\.query\(.*\.all\(\)', "Database queries"),
            (r'def\s+\w+\([^)]*\):.*\n(?:.*\n)*?.*json\.loads\(.*open\(', "File I/O with parsing"),
        ]

        for pattern, description in expensive_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1

                # Check if there's @cache or @lru_cache decorator
                lines = code.split('\n')
                has_cache = False
                for i in range(max(0, line_num - 5), line_num):
                    if '@cache' in lines[i] or '@lru_cache' in lines[i] or 'cache' in lines[i].lower():
                        has_cache = True
                        break

                if not has_cache:
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.PERFORMANCE,
                        title="Missing caching for expensive operation",
                        description=f"Function performs {description} without caching",
                        location=CodeLocation(file_path=file_path, line_start=line_num),
                        recommendation="Consider adding @lru_cache decorator or implementing caching layer",
                        suggested_fix="from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef your_function(...):",
                        tags=["caching", "optimization"]
                    )

    async def _check_string_concatenation(self, file_path: str, code: str) -> None:
        """Check for inefficient string concatenation in loops."""
        # Look for += on strings in loops
        pattern = r'for\s+.*:.*\n\s+.*\w+\s*\+=\s*["\']'
        matches = re.finditer(pattern, code, re.MULTILINE)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            snippet = self.extract_code_snippet(code, line_num, line_num + 1)

            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE,
                title="Inefficient string concatenation in loop",
                description="Using += for strings in loop creates new string objects each iteration",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Use list and ''.join() or io.StringIO for better performance",
                code_snippet=snippet,
                suggested_fix="parts = []\nfor item in items:\n    parts.append(str(item))\nresult = ''.join(parts)",
                tags=["string-concatenation", "loops", "performance"]
            )

    async def _check_loop_inefficiencies(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for inefficient loop patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for list comprehension opportunities
                if len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, ast.Call):
                        # Pattern: for x in y: result.append(something)
                        if hasattr(node.body[0].value.func, 'attr') and node.body[0].value.func.attr == 'append':
                            self.add_finding(
                                severity=Severity.LOW,
                                category=Category.PERFORMANCE,
                                title="List comprehension opportunity",
                                description="Loop can be replaced with list comprehension for better performance",
                                location=CodeLocation(file_path=file_path, line_start=node.lineno),
                                recommendation="Use list comprehension: [x for x in items]",
                                tags=["loops", "comprehension", "optimization"]
                            )

                # Check for nested loops (O(n²))
                for child in ast.walk(node):
                    if isinstance(child, ast.For) and child != node:
                        # Nested loop found
                        self.add_finding(
                            severity=Severity.MEDIUM,
                            category=Category.PERFORMANCE,
                            title="Nested loops detected",
                            description="Nested loops can have O(n²) or worse complexity",
                            location=CodeLocation(file_path=file_path, line_start=node.lineno),
                            recommendation="Consider if algorithm can be optimized with sets, dicts, or different data structures",
                            tags=["nested-loops", "complexity", "algorithm"]
                        )
                        break

    async def _check_unbounded_collections(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for unbounded collections that could cause memory leaks."""
        # Look for class-level or global lists/dicts that grow indefinitely
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                # Check if it's a list or dict
                                if isinstance(item.value, (ast.List, ast.Dict)):
                                    self.add_finding(
                                        severity=Severity.MEDIUM,
                                        category=Category.PERFORMANCE,
                                        title="Unbounded collection as class attribute",
                                        description=f"Class attribute '{target.id}' is a collection that may grow unbounded",
                                        location=CodeLocation(
                                            file_path=file_path,
                                            line_start=item.lineno,
                                            class_name=node.name
                                        ),
                                        recommendation="Consider using a bounded cache (LRU) or implementing cleanup logic",
                                        tags=["memory-leak", "unbounded-collection"]
                                    )

    async def _check_repeated_calculations(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for calculations that are repeated unnecessarily."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Look for same expression used multiple times
                expressions = []
                for child in ast.walk(node):
                    if isinstance(child, ast.BinOp):
                        expr_str = ast.unparse(child)
                        expressions.append((expr_str, child.lineno if hasattr(child, 'lineno') else None))

                # Find duplicates
                seen = {}
                for expr, line_num in expressions:
                    if expr in seen and line_num and seen[expr] != line_num:
                        self.add_finding(
                            severity=Severity.LOW,
                            category=Category.PERFORMANCE,
                            title="Repeated calculation",
                            description=f"Expression '{expr}' is calculated multiple times",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=line_num,
                                function_name=node.name
                            ),
                            recommendation="Store the result in a variable and reuse it",
                            tags=["repeated-calculation", "optimization"]
                        )
                        break
                    seen[expr] = line_num

    async def _check_async_patterns(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for async/await pattern issues."""
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check for sequential awaits that could be parallel
                await_count = 0
                sequential_awaits = []

                for i, child in enumerate(node.body):
                    if isinstance(child, ast.Expr) and isinstance(child.value, ast.Await):
                        await_count += 1
                        sequential_awaits.append(child.lineno if hasattr(child, 'lineno') else None)
                    elif isinstance(child, ast.Assign):
                        if isinstance(child.value, ast.Await):
                            await_count += 1
                            sequential_awaits.append(child.lineno if hasattr(child, 'lineno') else None)

                # If there are 2+ sequential awaits, suggest parallel execution
                if await_count >= 2 and len(sequential_awaits) >= 2:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.PERFORMANCE,
                        title="Sequential awaits that could be parallel",
                        description=f"Function has {await_count} sequential await calls that might be parallelizable",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=sequential_awaits[0],
                            function_name=node.name
                        ),
                        recommendation="Use asyncio.gather() to run independent async operations in parallel",
                        suggested_fix="result1, result2 = await asyncio.gather(task1(), task2())",
                        tags=["async", "parallelization", "await"]
                    )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get performance-specific patterns for matching."""
        return [
            {
                'pattern': r'\.+append\(.*\)\s*\n\s*for\s+',
                'severity': Severity.LOW,
                'category': Category.PERFORMANCE,
                'title': "Consider using extend() instead of append() in loop",
                'description': "extend() is more efficient for adding multiple items",
                'recommendation': "Use list.extend(items) instead of looping with append()"
            },
            {
                'pattern': r'global\s+\w+\s*=\s*\[\]',
                'severity': Severity.MEDIUM,
                'category': Category.PERFORMANCE,
                'title': "Global mutable collection",
                'description': "Global list may grow unbounded and cause memory issues",
                'recommendation': "Use bounded cache or implement cleanup logic"
            },
            {
                'pattern': r'import\s+\*',
                'severity': Severity.LOW,
                'category': Category.PERFORMANCE,
                'title': "Wildcard import",
                'description': "Wildcard imports increase module load time and namespace pollution",
                'recommendation': "Import specific items: from module import specific_function"
            }
        ]
