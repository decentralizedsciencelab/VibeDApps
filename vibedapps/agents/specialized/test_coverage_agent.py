"""
Test Coverage Analyzer Agent - Reviews test quality and coverage.

This agent performs comprehensive test analysis including:
- Test coverage calculation
- Missing tests detection
- Test quality review
- Test smell detection
- Assertion analysis
- Test independence checking
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class TestCoverageAgent(BaseReviewAgent):
    """Agent specialized in test coverage and quality analysis."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Test Coverage Analyzer",
                description="Analyzes test coverage, quality, and identifies missing tests",
                capabilities=[
                    "coverage_calculation",
                    "test_quality_review",
                    "missing_tests_detection",
                    "test_smell_detection",
                    "assertion_analysis",
                    "test_independence"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a testing expert. Analyze test coverage and quality. "
                    "Identify missing tests, weak assertions, test smells, and areas "
                    "that need better test coverage. Focus on test effectiveness and maintainability."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

        self.tested_functions: Set[str] = set()
        self.all_functions: Set[str] = set()
        self.test_files: List[str] = []

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.TESTING

    async def review(self, target: str, context: Dict[str, Any] = None) -> Any:
        """
        Override review to handle test coverage across multiple files.
        """
        if context is None:
            context = {}

        # First, collect all functions and test files
        target_path = Path(target)

        if target_path.is_dir():
            # Scan directory for source and test files
            await self._scan_directory(target)

        result = await super().review(target, context)

        # Add coverage metrics to the report
        if self.all_functions:
            coverage_percentage = (len(self.tested_functions) / len(self.all_functions)) * 100
            result.metrics.code_coverage = coverage_percentage

            # Add overall coverage finding
            if coverage_percentage < 80:
                severity = Severity.HIGH if coverage_percentage < 50 else Severity.MEDIUM

                self.add_finding(
                    severity=severity,
                    category=Category.TESTING,
                    title=f"Low test coverage: {coverage_percentage:.1f}%",
                    description=f"Only {len(self.tested_functions)} of {len(self.all_functions)} functions are tested",
                    location=CodeLocation(file_path=target),
                    recommendation="Aim for at least 80% test coverage. Add tests for critical business logic.",
                    tags=["coverage", "testing", "quality"]
                )

        return result

    async def _scan_directory(self, dir_path: str) -> None:
        """Scan directory to collect functions and test information."""
        directory = Path(dir_path)

        # Find test files
        test_files = list(directory.rglob("test_*.py")) + list(directory.rglob("*_test.py"))
        self.test_files = [str(f) for f in test_files]

        # Find source files
        source_files = [f for f in directory.rglob("*.py") if f not in test_files and 'test' not in str(f)]

        # Collect all functions from source files
        for source_file in source_files:
            if 'venv' in str(source_file) or '__pycache__' in str(source_file):
                continue

            try:
                with open(source_file, encoding='utf-8') as f:
                    code = f.read()
                    tree = self.parse_ast(code)
                    if tree:
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if not node.name.startswith('_'):  # Skip private functions
                                    self.all_functions.add(f"{source_file.name}::{node.name}")
            except Exception:
                pass

        # Collect tested functions from test files
        for test_file in self.test_files:
            try:
                with open(test_file, encoding='utf-8') as f:
                    code = f.read()
                    # Look for function calls in tests
                    # Simplified: assumes test calls function directly
                    for func_name in self.all_functions:
                        func = func_name.split('::')[1]
                        if func in code:
                            self.tested_functions.add(func_name)
            except Exception:
                pass

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static test analysis."""

        # Check if this is a test file
        is_test_file = 'test_' in file_path or '_test' in file_path

        if is_test_file:
            await self._analyze_test_file(file_path, code)
        else:
            await self._analyze_source_file(file_path, code)

    async def _analyze_test_file(self, file_path: str, code: str) -> None:
        """Analyze a test file for quality issues."""

        # Check for tests without assertions
        await self._check_missing_assertions(file_path, code)

        # Check for weak assertions
        await self._check_weak_assertions(file_path, code)

        # Check for test independence
        await self._check_test_independence(file_path, code)

        # Check for proper test naming
        await self._check_test_naming(file_path, code)

        # Check for setup/teardown issues
        await self._check_setup_teardown(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_test_structure(file_path, code, tree)
            await self._check_test_smells(file_path, code, tree)

    async def _analyze_source_file(self, file_path: str, code: str) -> None:
        """Analyze source file for missing tests."""

        tree = self.parse_ast(code)
        if not tree:
            return

        # Find all public functions
        public_functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_') and node.name != '__init__':
                    public_functions.append(node)

        # Check if corresponding test file exists
        file_name = Path(file_path).name
        test_file_names = [
            f"test_{file_name}",
            file_name.replace('.py', '_test.py')
        ]

        test_exists = any(Path(file_path).parent / name for name in test_file_names if (Path(file_path).parent / name).exists())

        if not test_exists and public_functions:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.TESTING,
                title="No test file found",
                description=f"Source file has {len(public_functions)} public functions but no corresponding test file",
                location=CodeLocation(file_path=file_path),
                recommendation=f"Create test file: {test_file_names[0]}",
                tags=["missing-tests", "coverage"]
            )

    async def _check_missing_assertions(self, file_path: str, code: str) -> None:
        """Check for test functions without assertions."""
        tree = self.parse_ast(code)
        if not tree:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                # Check if function has any assert statements
                has_assert = False
                for child in ast.walk(node):
                    if isinstance(child, (ast.Assert, ast.Call)):
                        if isinstance(child, ast.Call) and hasattr(child.func, 'attr'):
                            # Check for unittest/pytest assertions
                            if any(child.func.attr.startswith(prefix) for prefix in ['assert', 'assertEqual', 'assertTrue']):
                                has_assert = True
                                break
                        elif isinstance(child, ast.Assert):
                            has_assert = True
                            break

                if not has_assert:
                    self.add_finding(
                        severity=Severity.HIGH,
                        category=Category.TESTING,
                        title=f"Test without assertions: {node.name}()",
                        description="Test function has no assert statements",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Add assertions to verify expected behavior",
                        tags=["test-quality", "assertions"]
                    )

    async def _check_weak_assertions(self, file_path: str, code: str) -> None:
        """Check for weak or non-specific assertions."""
        weak_patterns = [
            (r'assert\s+True', "assert True - always passes"),
            (r'assert\s+\w+\s*is\s*not\s*None', "Weak assertion - only checks not None"),
            (r'self\.assertTrue\(True\)', "assertTrue(True) - always passes"),
        ]

        for pattern, description in weak_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.TESTING,
                    title="Weak assertion",
                    description=description,
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use specific assertions that verify exact expected values",
                    code_snippet=snippet,
                    tags=["test-quality", "weak-assertion"]
                )

    async def _check_test_independence(self, file_path: str, code: str) -> None:
        """Check if tests depend on each other."""
        # Look for shared state between tests
        tree = self.parse_ast(code)
        if not tree:
            return

        # Check for class-level mutable state
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                if isinstance(item.value, (ast.List, ast.Dict)):
                                    self.add_finding(
                                        severity=Severity.MEDIUM,
                                        category=Category.TESTING,
                                        title="Shared mutable state in test class",
                                        description=f"Class variable '{target.id}' may cause test interdependencies",
                                        location=CodeLocation(
                                            file_path=file_path,
                                            line_start=item.lineno,
                                            class_name=node.name
                                        ),
                                        recommendation="Initialize mutable state in setUp() or use fixtures",
                                        tags=["test-independence", "test-smell"]
                                    )

    async def _check_test_naming(self, file_path: str, code: str) -> None:
        """Check test function naming conventions."""
        tree = self.parse_ast(code)
        if not tree:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test'):
                    # Check if name is descriptive (too short)
                    if len(node.name) < 10:
                        self.add_finding(
                            severity=Severity.INFO,
                            category=Category.TESTING,
                            title=f"Short test name: {node.name}()",
                            description="Test name should be descriptive of what is being tested",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=node.lineno,
                                function_name=node.name
                            ),
                            recommendation="Use descriptive names like test_user_login_with_invalid_password",
                            tags=["test-naming", "readability"]
                        )

    async def _check_setup_teardown(self, file_path: str, code: str) -> None:
        """Check for proper setUp/tearDown usage."""
        # Look for repeated setup code in tests
        tree = self.parse_ast(code)
        if not tree:
            return

        test_class_setups = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has setUp method
                has_setup = any(isinstance(n, ast.FunctionDef) and n.name in ['setUp', 'setup_method'] for n in node.body)

                # Count test methods
                test_methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]

                if len(test_methods) > 3 and not has_setup:
                    # Check if tests have similar initialization code
                    first_lines = []
                    for test in test_methods[:3]:
                        if test.body and len(test.body) > 0:
                            first_line = ast.unparse(test.body[0]) if test.body else ""
                            first_lines.append(first_line)

                    # If many tests start similarly, suggest setUp
                    if len(set(first_lines)) < len(first_lines):
                        self.add_finding(
                            severity=Severity.LOW,
                            category=Category.TESTING,
                            title="Missing setUp method",
                            description="Test class has repeated initialization code across tests",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=node.lineno,
                                class_name=node.name
                            ),
                            recommendation="Extract common setup code into setUp() method",
                            tags=["test-structure", "duplication"]
                        )

    async def _check_test_structure(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check test structure and organization."""
        test_classes = []
        standalone_tests = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                test_methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
                if test_methods:
                    test_classes.append((node.name, len(test_methods)))

            elif isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                standalone_tests.append(node.name)

        # If many standalone tests, suggest organizing into classes
        if len(standalone_tests) > 5 and not test_classes:
            self.add_finding(
                severity=Severity.LOW,
                category=Category.TESTING,
                title="Unorganized test functions",
                description=f"{len(standalone_tests)} standalone test functions without test classes",
                location=CodeLocation(file_path=file_path),
                recommendation="Organize related tests into test classes for better structure",
                tags=["test-organization", "structure"]
            )

    async def _check_test_smells(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for common test smells."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                # Check for long test functions
                lines = self.get_function_lines(node)
                if lines > 50:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.TESTING,
                        title=f"Long test function: {node.name}()",
                        description=f"Test has {lines} lines - too long to understand easily",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Split into multiple smaller, focused tests",
                        tags=["test-smell", "function-length"]
                    )

                # Check for multiple assertions (testing multiple things)
                assert_count = sum(1 for n in ast.walk(node) if isinstance(n, ast.Assert))
                if assert_count > 5:
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.TESTING,
                        title=f"Multiple assertions in {node.name}()",
                        description=f"Test has {assert_count} assertions - may be testing too many things",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Follow the single assertion principle - one logical concept per test",
                        tags=["test-smell", "assertions"]
                    )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get testing-specific patterns for matching."""
        return [
            {
                'pattern': r'time\.sleep\(',
                'severity': Severity.MEDIUM,
                'category': Category.TESTING,
                'title': "time.sleep() in test",
                'description': "Using time.sleep() makes tests slow and flaky",
                'recommendation': "Use proper synchronization or mocking instead of sleep"
            },
            {
                'pattern': r'#\s*TODO:.*test',
                'severity': Severity.LOW,
                'category': Category.TESTING,
                'title': "TODO comment for test",
                'description': "Test marked as TODO indicates incomplete coverage",
                'recommendation': "Implement the missing test or create a ticket"
            }
        ]
