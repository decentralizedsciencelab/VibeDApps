"""
Code Quality Reviewer Agent - Reviews code for maintainability and best practices.

This agent performs comprehensive code quality analysis including:
- Cyclomatic complexity
- Code duplication
- File and function size
- Naming conventions
- Code smells (god classes, long methods, etc.)
- Best practices adherence
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class CodeQualityAgent(BaseReviewAgent):
    """Agent specialized in code quality reviews."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Code Quality Reviewer",
                description="Analyzes code for maintainability, complexity, and best practices",
                capabilities=[
                    "complexity_analysis",
                    "code_smell_detection",
                    "duplication_finder",
                    "naming_conventions",
                    "structure_analysis",
                    "dependency_review"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a code quality expert. Analyze code for maintainability issues, "
                    "code smells, and violations of best practices. Focus on clean code principles, "
                    "SOLID principles, and Pythonic patterns. Provide specific, actionable feedback."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

        # Thresholds for various metrics
        self.thresholds = {
            'max_file_lines': 500,
            'max_function_lines': 50,
            'max_function_params': 5,
            'max_cyclomatic_complexity': 10,
            'max_nesting_depth': 4,
            'max_class_methods': 20,
            'min_function_name_length': 3,
            'max_function_name_length': 50
        }

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.QUALITY

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static code quality analysis."""

        # Check file size
        await self._check_file_size(file_path, code)

        # Check for magic numbers
        await self._check_magic_numbers(file_path, code)

        # Check for commented code
        await self._check_commented_code(file_path, code)

        # Check for TODO/FIXME comments
        await self._check_todo_comments(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_function_complexity(file_path, code, tree)
            await self._check_function_length(file_path, code, tree)
            await self._check_parameter_count(file_path, code, tree)
            await self._check_class_complexity(file_path, code, tree)
            await self._check_naming_conventions(file_path, code, tree)
            await self._check_nesting_depth(file_path, code, tree)
            await self._check_code_duplication(file_path, code, tree)
            await self._check_import_organization(file_path, code, tree)

    async def _check_file_size(self, file_path: str, code: str) -> None:
        """Check if file is too large."""
        lines = code.split('\n')
        line_count = len(lines)

        if line_count > self.thresholds['max_file_lines']:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.MAINTAINABILITY,
                title="File too large",
                description=f"File has {line_count} lines (threshold: {self.thresholds['max_file_lines']})",
                location=CodeLocation(file_path=file_path),
                recommendation="Consider splitting this file into smaller, more focused modules",
                tags=["file-size", "god-class", "maintainability"]
            )

    async def _check_magic_numbers(self, file_path: str, code: str) -> None:
        """Check for magic numbers in code."""
        # Simple regex to find numeric literals (excluding 0, 1, -1 which are often acceptable)
        pattern = r'\b(?<![\w.])-?[2-9]\d{2,}\b(?![\w.])'
        matches = re.finditer(pattern, code)

        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            lines = code.split('\n')
            line_content = lines[line_num - 1] if line_num <= len(lines) else ""

            # Skip if it's in a comment or string
            if '#' in line_content[:line_content.find(match.group())]:
                continue
            if line_content.strip().startswith('#'):
                continue

            self.add_finding(
                severity=Severity.LOW,
                category=Category.BEST_PRACTICES,
                title="Magic number detected",
                description=f"Numeric literal {match.group()} should be a named constant",
                location=CodeLocation(file_path=file_path, line_start=line_num),
                recommendation="Replace magic numbers with named constants or configuration values",
                code_snippet=line_content.strip(),
                tags=["magic-numbers", "readability"]
            )

    async def _check_commented_code(self, file_path: str, code: str) -> None:
        """Check for large blocks of commented code."""
        lines = code.split('\n')
        commented_block_start = None
        commented_lines = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if stripped.startswith('#'):
                # Check if it looks like commented code (has assignments, function calls, etc.)
                if any(indicator in stripped for indicator in ['=', '(', '{', '[', 'def ', 'class ']):
                    if commented_block_start is None:
                        commented_block_start = i
                    commented_lines += 1
            else:
                if commented_lines >= 3:  # Report blocks of 3+ lines
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.MAINTAINABILITY,
                        title="Commented code block",
                        description=f"Found {commented_lines} lines of commented code",
                        location=CodeLocation(file_path=file_path, line_start=commented_block_start),
                        recommendation="Remove commented code. Use version control to track changes instead.",
                        tags=["dead-code", "comments"]
                    )
                commented_block_start = None
                commented_lines = 0

    async def _check_todo_comments(self, file_path: str, code: str) -> None:
        """Check for TODO/FIXME comments."""
        patterns = [
            (r'#.*TODO', Severity.INFO, "TODO comment found"),
            (r'#.*FIXME', Severity.LOW, "FIXME comment found"),
            (r'#.*HACK', Severity.MEDIUM, "HACK comment found"),
            (r'#.*XXX', Severity.LOW, "XXX comment found")
        ]

        for pattern, severity, title in patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                lines = code.split('\n')
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                self.add_finding(
                    severity=severity,
                    category=Category.MAINTAINABILITY,
                    title=title,
                    description="Code contains unresolved comment indicating incomplete work",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Address the TODO/FIXME or create a proper issue in your tracker",
                    code_snippet=line_content.strip(),
                    tags=["technical-debt", "comments"]
                )

    async def _check_function_complexity(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check cyclomatic complexity of functions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self.get_function_complexity(node)

                if complexity > self.thresholds['max_cyclomatic_complexity']:
                    severity = Severity.HIGH if complexity > 15 else Severity.MEDIUM

                    self.add_finding(
                        severity=severity,
                        category=Category.QUALITY,
                        title=f"High cyclomatic complexity in {node.name}()",
                        description=f"Function has complexity of {complexity} (threshold: {self.thresholds['max_cyclomatic_complexity']})",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Refactor into smaller functions or simplify conditional logic",
                        tags=["complexity", "refactoring", "maintainability"],
                        metadata={"complexity": complexity}
                    )

    async def _check_function_length(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check if functions are too long."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lines = self.get_function_lines(node)

                if lines > self.thresholds['max_function_lines']:
                    severity = Severity.MEDIUM if lines > 100 else Severity.LOW

                    self.add_finding(
                        severity=severity,
                        category=Category.MAINTAINABILITY,
                        title=f"Long function: {node.name}()",
                        description=f"Function has {lines} lines (threshold: {self.thresholds['max_function_lines']})",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Break down into smaller, single-responsibility functions",
                        tags=["function-length", "refactoring"]
                    )

    async def _check_parameter_count(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check if functions have too many parameters."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count parameters (excluding self/cls)
                params = [arg.arg for arg in node.args.args if arg.arg not in ['self', 'cls']]
                param_count = len(params)

                if param_count > self.thresholds['max_function_params']:
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.QUALITY,
                        title=f"Too many parameters in {node.name}()",
                        description=f"Function has {param_count} parameters (threshold: {self.thresholds['max_function_params']})",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Consider using a parameter object or configuration dictionary",
                        tags=["parameters", "function-signature"]
                    )

    async def _check_class_complexity(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for complex classes (god classes)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_count = len(methods)

                if method_count > self.thresholds['max_class_methods']:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.ARCHITECTURE,
                        title=f"God class: {node.name}",
                        description=f"Class has {method_count} methods (threshold: {self.thresholds['max_class_methods']})",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Consider splitting into multiple classes following Single Responsibility Principle",
                        tags=["god-class", "solid", "refactoring"]
                    )

    async def _check_naming_conventions(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check Python naming conventions (PEP 8)."""
        for node in ast.walk(tree):
            # Check function names
            if isinstance(node, ast.FunctionDef):
                if not re.match(r'^[a-z_][a-z0-9_]*$', node.name) and not node.name.startswith('_'):
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.BEST_PRACTICES,
                        title=f"Non-PEP8 function name: {node.name}",
                        description="Function names should be lowercase with underscores",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Rename to follow snake_case convention",
                        references=["https://pep8.org/#function-and-variable-names"],
                        tags=["naming", "pep8"]
                    )

            # Check class names
            elif isinstance(node, ast.ClassDef):
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.BEST_PRACTICES,
                        title=f"Non-PEP8 class name: {node.name}",
                        description="Class names should use CapWords convention",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Rename to follow PascalCase convention",
                        references=["https://pep8.org/#class-names"],
                        tags=["naming", "pep8"]
                    )

            # Check constant names
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Check if it's a module-level constant (all uppercase)
                        if hasattr(node, 'col_offset') and node.col_offset == 0:
                            if target.id.isupper() and '_' in target.id and len(target.id) > 1:
                                continue  # Proper constant
                            elif target.id.isupper() or (target.id[0].isupper() and target.id != target.id.lower()):
                                # Looks like a constant but not properly formatted
                                self.add_finding(
                                    severity=Severity.INFO,
                                    category=Category.BEST_PRACTICES,
                                    title=f"Constant naming: {target.id}",
                                    description="Module-level constants should be UPPER_CASE",
                                    location=CodeLocation(
                                        file_path=file_path,
                                        line_start=node.lineno
                                    ),
                                    recommendation="Use UPPER_CASE with underscores for constants",
                                    tags=["naming", "pep8", "constants"]
                                )

    async def _check_nesting_depth(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for excessive nesting depth."""

        def get_max_depth(node, current_depth=0):
            """Recursively calculate maximum nesting depth."""
            max_depth = current_depth

            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    child_depth = get_max_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = get_max_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)

            return max_depth

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                max_depth = get_max_depth(node)

                if max_depth > self.thresholds['max_nesting_depth']:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.QUALITY,
                        title=f"Deep nesting in {node.name}()",
                        description=f"Maximum nesting depth is {max_depth} (threshold: {self.thresholds['max_nesting_depth']})",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Reduce nesting by using early returns, extracting methods, or inverting conditions",
                        tags=["nesting", "complexity", "readability"]
                    )

    async def _check_code_duplication(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for duplicated code blocks."""
        # Simple duplication check based on function bodies
        function_bodies = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get function body as string
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    lines = code.split('\n')
                    body_lines = lines[node.lineno:node.end_lineno]
                    body_str = '\n'.join(body_lines)

                    # Normalize (remove whitespace variations)
                    normalized = re.sub(r'\s+', ' ', body_str)

                    if normalized in function_bodies and len(normalized) > 100:
                        original_func = function_bodies[normalized]
                        self.add_finding(
                            severity=Severity.MEDIUM,
                            category=Category.MAINTAINABILITY,
                            title=f"Duplicate code in {node.name}() and {original_func}()",
                            description="Functions have identical or very similar implementations",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=node.lineno,
                                function_name=node.name
                            ),
                            recommendation="Extract common logic into a shared function",
                            tags=["duplication", "dry", "refactoring"]
                        )
                    else:
                        function_bodies[normalized] = node.name

    async def _check_import_organization(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check import organization (PEP 8)."""
        imports = []
        last_import_line = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append((node.lineno, node))
                last_import_line = max(last_import_line, node.lineno)

        # Check if imports are at the top
        if imports:
            # Look for code before imports
            lines = code.split('\n')
            for i, line in enumerate(lines[:imports[0][0]-1], 1):
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.BEST_PRACTICES,
                        title="Imports not at top of file",
                        description="PEP 8 recommends placing imports at the top of the file",
                        location=CodeLocation(file_path=file_path, line_start=i),
                        recommendation="Move imports to the top of the file (after docstrings)",
                        references=["https://pep8.org/#imports"],
                        tags=["imports", "pep8", "organization"]
                    )
                    break

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get code quality patterns for matching."""
        return [
            {
                'pattern': r'except\s*:',
                'severity': Severity.MEDIUM,
                'category': Category.BEST_PRACTICES,
                'title': "Bare except clause",
                'description': "Catching all exceptions without specifying type",
                'recommendation': "Catch specific exceptions instead of using bare except"
            },
            {
                'pattern': r'lambda\s+[^:]+:\s+lambda',
                'severity': Severity.LOW,
                'category': Category.QUALITY,
                'title': "Nested lambda",
                'description': "Nested lambda functions reduce readability",
                'recommendation': "Use nested functions instead of nested lambdas"
            }
        ]
