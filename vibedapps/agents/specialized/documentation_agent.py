"""
Documentation Reviewer Agent - Reviews code documentation quality.

This agent performs comprehensive documentation analysis including:
- Docstring completeness
- Type hint coverage
- API documentation quality
- README review
- Inline comment appropriateness
- Example code presence
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class DocumentationAgent(BaseReviewAgent):
    """Agent specialized in documentation review."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Documentation Reviewer",
                description="Analyzes documentation quality and completeness",
                capabilities=[
                    "docstring_completeness",
                    "api_documentation",
                    "readme_review",
                    "inline_comments_check",
                    "type_hints_review",
                    "example_code_check"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a documentation expert. Analyze code documentation for completeness, "
                    "clarity, and usefulness. Focus on docstrings, type hints, API documentation, "
                    "and inline comments. Ensure documentation helps developers understand and use the code."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.DOCUMENTATION

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static documentation analysis."""

        # Check for missing module docstring
        await self._check_module_docstring(file_path, code)

        # Check for excessive inline comments
        await self._check_excessive_comments(file_path, code)

        # Check for commented-out code vs actual comments
        await self._check_comment_quality(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_function_docstrings(file_path, code, tree)
            await self._check_class_docstrings(file_path, code, tree)
            await self._check_type_hints(file_path, code, tree)
            await self._check_docstring_quality(file_path, code, tree)
            await self._check_public_api_docs(file_path, code, tree)

    async def _check_module_docstring(self, file_path: str, code: str) -> None:
        """Check for module-level docstring."""
        lines = code.split('\n')

        # Skip empty lines and comments at start
        first_content_line = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                first_content_line = i
                break

        # Check if module starts with docstring
        has_module_docstring = False
        if first_content_line < len(lines):
            first_line = lines[first_content_line].strip()
            if first_line.startswith('"""') or first_line.startswith("'''"):
                has_module_docstring = True

        if not has_module_docstring and not ('test_' in file_path or '__init__' in file_path):
            self.add_finding(
                severity=Severity.LOW,
                category=Category.DOCUMENTATION,
                title="Missing module docstring",
                description="Module lacks a docstring describing its purpose",
                location=CodeLocation(file_path=file_path, line_start=1),
                recommendation='Add module docstring at the top: """Module description here."""',
                references=[
                    "https://www.python.org/dev/peps/pep-0257/"
                ],
                tags=["docstring", "module-doc"]
            )

    async def _check_excessive_comments(self, file_path: str, code: str) -> None:
        """Check for overly commented code (may indicate complexity)."""
        lines = code.split('\n')
        total_lines = len([l for l in lines if l.strip()])
        comment_lines = len([l for l in lines if l.strip().startswith('#')])

        if total_lines > 0:
            comment_ratio = comment_lines / total_lines

            if comment_ratio > 0.3:  # More than 30% comments
                self.add_finding(
                    severity=Severity.INFO,
                    category=Category.DOCUMENTATION,
                    title="High comment-to-code ratio",
                    description=f"{comment_ratio*100:.1f}% of code is comments - may indicate complex code",
                    location=CodeLocation(file_path=file_path),
                    recommendation="Consider refactoring complex code to be more self-documenting",
                    tags=["comments", "complexity"]
                )

    async def _check_comment_quality(self, file_path: str, code: str) -> None:
        """Check inline comment quality."""
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Check for obvious/redundant comments
            if '#' in line and not stripped.startswith('#'):
                code_part, comment_part = line.split('#', 1)
                comment = comment_part.strip()

                # Check for redundant comments that just repeat the code
                code_words = set(re.findall(r'\w+', code_part.lower()))
                comment_words = set(re.findall(r'\w+', comment.lower()))

                if len(code_words & comment_words) / max(len(comment_words), 1) > 0.7:
                    self.add_finding(
                        severity=Severity.INFO,
                        category=Category.DOCUMENTATION,
                        title="Redundant comment",
                        description="Comment mostly repeats what the code already says",
                        location=CodeLocation(file_path=file_path, line_start=i),
                        recommendation="Remove obvious comments or make them explain 'why', not 'what'",
                        code_snippet=line.strip(),
                        tags=["comments", "redundant"]
                    )

    async def _check_function_docstrings(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for missing or incomplete function docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions and very short functions
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue

                lines = self.get_function_lines(node)
                if lines < 3:  # Very short functions don't need docstrings
                    continue

                # Check if function has docstring
                has_docstring = (
                    node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)
                )

                if not has_docstring:
                    # Determine severity based on function visibility
                    if node.name.startswith('__') and node.name.endswith('__'):
                        severity = Severity.LOW  # Dunder methods
                    elif len(node.args.args) == 0 and lines < 10:
                        severity = Severity.INFO  # Simple functions
                    else:
                        severity = Severity.MEDIUM

                    self.add_finding(
                        severity=severity,
                        category=Category.DOCUMENTATION,
                        title=f"Missing docstring: {node.name}()",
                        description="Function lacks documentation",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Add docstring describing purpose, parameters, and return value",
                        suggested_fix='"""Function description.\n\nArgs:\n    param: Description\n\nReturns:\n    Description\n"""',
                        tags=["docstring", "function-doc"]
                    )
                else:
                    # Check docstring quality
                    docstring = node.body[0].value.value
                    await self._validate_function_docstring(file_path, node, docstring)

    async def _check_class_docstrings(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for missing or incomplete class docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has docstring
                has_docstring = (
                    node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)
                )

                if not has_docstring:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.DOCUMENTATION,
                        title=f"Missing class docstring: {node.name}",
                        description="Class lacks documentation",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Add docstring describing class purpose and usage",
                        suggested_fix='"""Class description.\n\nAttributes:\n    attr: Description\n"""',
                        tags=["docstring", "class-doc"]
                    )

    async def _validate_function_docstring(self, file_path: str, node: ast.FunctionDef, docstring: str) -> None:
        """Validate function docstring completeness."""
        # Get function parameters
        params = [arg.arg for arg in node.args.args if arg.arg not in ['self', 'cls']]

        # Check if docstring mentions parameters
        if params and len(params) > 0:
            # Check for various docstring styles
            has_param_docs = (
                'Args:' in docstring or
                'Parameters:' in docstring or
                'Params:' in docstring or
                ':param' in docstring
            )

            if not has_param_docs:
                self.add_finding(
                    severity=Severity.LOW,
                    category=Category.DOCUMENTATION,
                    title=f"Incomplete docstring: {node.name}()",
                    description=f"Function has {len(params)} parameters but docstring doesn't document them",
                    location=CodeLocation(
                        file_path=file_path,
                        line_start=node.lineno,
                        function_name=node.name
                    ),
                    recommendation="Document all parameters in docstring",
                    tags=["docstring", "parameters"]
                )

        # Check for return value documentation
        has_return = False
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                has_return = True
                break

        if has_return:
            has_return_docs = (
                'Returns:' in docstring or
                'Return:' in docstring or
                ':returns:' in docstring or
                ':return:' in docstring
            )

            if not has_return_docs:
                self.add_finding(
                    severity=Severity.LOW,
                    category=Category.DOCUMENTATION,
                    title=f"Missing return documentation: {node.name}()",
                    description="Function returns a value but docstring doesn't document it",
                    location=CodeLocation(
                        file_path=file_path,
                        line_start=node.lineno,
                        function_name=node.name
                    ),
                    recommendation="Add Returns section to docstring",
                    tags=["docstring", "return-value"]
                )

    async def _check_type_hints(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for missing type hints."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue

                # Check parameter type hints
                missing_param_hints = []
                for arg in node.args.args:
                    if arg.arg not in ['self', 'cls'] and arg.annotation is None:
                        missing_param_hints.append(arg.arg)

                if missing_param_hints:
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.DOCUMENTATION,
                        title=f"Missing type hints: {node.name}()",
                        description=f"Parameters without type hints: {', '.join(missing_param_hints)}",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            function_name=node.name
                        ),
                        recommendation="Add type hints for better code documentation and IDE support",
                        suggested_fix=f"def {node.name}(param: Type) -> ReturnType:",
                        tags=["type-hints", "annotations"]
                    )

                # Check return type hint
                if node.returns is None:
                    # Check if function actually returns something
                    has_return = any(isinstance(child, ast.Return) and child.value is not None for child in ast.walk(node))

                    if has_return:
                        self.add_finding(
                            severity=Severity.LOW,
                            category=Category.DOCUMENTATION,
                            title=f"Missing return type hint: {node.name}()",
                            description="Function returns a value but lacks return type annotation",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=node.lineno,
                                function_name=node.name
                            ),
                            recommendation="Add return type hint: def func() -> ReturnType:",
                            tags=["type-hints", "return-type"]
                        )

    async def _check_docstring_quality(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check docstring quality and formatting."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.body and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                        docstring = node.body[0].value.value

                        # Check if docstring is too short
                        if len(docstring.strip()) < 10:
                            name = node.name
                            item_type = "function" if isinstance(node, ast.FunctionDef) else "class"

                            self.add_finding(
                                severity=Severity.INFO,
                                category=Category.DOCUMENTATION,
                                title=f"Short docstring: {name}",
                                description=f"{item_type.capitalize()} docstring is very brief",
                                location=CodeLocation(
                                    file_path=file_path,
                                    line_start=node.lineno,
                                    function_name=name if isinstance(node, ast.FunctionDef) else None,
                                    class_name=name if isinstance(node, ast.ClassDef) else None
                                ),
                                recommendation="Provide more detailed documentation",
                                tags=["docstring", "quality"]
                            )

                        # Check for proper formatting (should end with period for sentences)
                        if len(docstring) > 20 and not docstring.rstrip().endswith(('.', '!', '?')):
                            self.add_finding(
                                severity=Severity.INFO,
                                category=Category.DOCUMENTATION,
                                title="Docstring formatting",
                                description="Docstring should end with proper punctuation",
                                location=CodeLocation(file_path=file_path, line_start=node.lineno),
                                recommendation="End docstring sentences with a period",
                                tags=["docstring", "formatting"]
                            )

    async def _check_public_api_docs(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check if public API has proper documentation."""
        # Look for __all__ to identify public API
        has_all = False
        public_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        has_all = True
                        # Extract names from __all__
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    public_names.add(elt.value)

        if has_all and public_names:
            # Check if all public names are documented
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if node.name in public_names:
                        has_docstring = (
                            node.body and
                            isinstance(node.body[0], ast.Expr) and
                            isinstance(node.body[0].value, ast.Constant) and
                            isinstance(node.body[0].value.value, str)
                        )

                        if not has_docstring:
                            self.add_finding(
                                severity=Severity.HIGH,
                                category=Category.DOCUMENTATION,
                                title=f"Public API lacks documentation: {node.name}",
                                description="Item in __all__ must have docstring",
                                location=CodeLocation(file_path=file_path, line_start=node.lineno),
                                recommendation="Add comprehensive docstring for public API",
                                tags=["public-api", "docstring"]
                            )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get documentation-specific patterns for matching."""
        return [
            {
                'pattern': r'#\s*TODO:',
                'severity': Severity.INFO,
                'category': Category.DOCUMENTATION,
                'title': "TODO comment",
                'description': "TODO indicates incomplete work",
                'recommendation': "Complete the TODO or create a proper issue"
            }
        ]
