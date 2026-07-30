"""
Architecture Reviewer Agent - Reviews system architecture and design patterns.

This agent performs comprehensive architectural analysis including:
- Dependency analysis
- Coupling and cohesion metrics
- SOLID principles validation
- Design pattern recognition
- Circular dependency detection
- Module structure analysis
"""

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class ArchitectureAgent(BaseReviewAgent):
    """Agent specialized in architectural reviews."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Architecture Reviewer",
                description="Analyzes system architecture, design patterns, and SOLID principles",
                capabilities=[
                    "dependency_analysis",
                    "coupling_detection",
                    "cohesion_analysis",
                    "pattern_recognition",
                    "solid_principles_check",
                    "circular_dependency_detection"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are an architecture expert. Analyze code for architectural issues, "
                    "design pattern problems, SOLID principle violations, and structural concerns. "
                    "Focus on maintainability, scalability, and clean architecture."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

        # Track dependencies across files
        self.module_imports: Dict[str, Set[str]] = defaultdict(set)
        self.module_dependencies: Dict[str, Set[str]] = defaultdict(set)

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.ARCHITECTURE

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static architecture analysis."""

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_solid_principles(file_path, code, tree)
            await self._check_coupling(file_path, code, tree)
            await self._check_cohesion(file_path, code, tree)
            await self._collect_dependencies(file_path, tree)
            await self._check_design_patterns(file_path, code, tree)
            await self._check_separation_of_concerns(file_path, code, tree)

    async def _check_solid_principles(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for SOLID principle violations."""

        # Single Responsibility Principle
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has too many responsibilities (simple heuristic)
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_names = [m.name for m in methods if not m.name.startswith('_')]

                # Group methods by purpose (simplified)
                purposes = set()
                for name in method_names:
                    # Extract verb from method name
                    parts = re.findall(r'[A-Z][a-z]*|[a-z]+', name)
                    if parts:
                        purposes.add(parts[0].lower())

                if len(purposes) > 5:  # Class doing many different things
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.ARCHITECTURE,
                        title=f"SRP violation: {node.name}",
                        description=f"Class has {len(purposes)} different types of operations, suggesting multiple responsibilities",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Split class into smaller classes, each with a single responsibility",
                        tags=["solid", "srp", "single-responsibility"]
                    )

        # Interface Segregation Principle (check for fat interfaces)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has ABC methods but too many
                abstract_methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Check for @abstractmethod decorator
                        for decorator in item.decorator_list:
                            if isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod':
                                abstract_methods.append(item.name)

                if len(abstract_methods) > 7:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.ARCHITECTURE,
                        title=f"ISP violation: {node.name}",
                        description=f"Interface has {len(abstract_methods)} abstract methods - may be too fat",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Split into multiple smaller, focused interfaces",
                        tags=["solid", "isp", "interface-segregation"]
                    )

        # Dependency Inversion Principle (check for concrete dependencies)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function parameters are concrete classes (heuristic)
                for arg in node.args.args:
                    if arg.annotation:
                        annotation_str = ast.unparse(arg.annotation)
                        # Check if it looks like a concrete class (PascalCase without Protocol/ABC)
                        if re.match(r'^[A-Z][a-zA-Z0-9]*$', annotation_str):
                            if 'Protocol' not in annotation_str and 'ABC' not in annotation_str:
                                self.add_finding(
                                    severity=Severity.LOW,
                                    category=Category.ARCHITECTURE,
                                    title=f"DIP: Concrete dependency in {node.name}()",
                                    description=f"Parameter '{arg.arg}' depends on concrete type '{annotation_str}'",
                                    location=CodeLocation(
                                        file_path=file_path,
                                        line_start=node.lineno,
                                        function_name=node.name
                                    ),
                                    recommendation="Depend on abstractions (Protocol/ABC) instead of concrete implementations",
                                    tags=["solid", "dip", "dependency-inversion"]
                                )

    async def _check_coupling(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for tight coupling between modules."""

        # Count imports
        import_count = 0
        external_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_count += 1
                    external_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_count += 1
                    external_imports.append(node.module)

        if import_count > 20:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.ARCHITECTURE,
                title="High coupling - too many imports",
                description=f"Module has {import_count} imports, suggesting tight coupling",
                location=CodeLocation(file_path=file_path),
                recommendation="Reduce dependencies by applying dependency inversion and interface segregation",
                tags=["coupling", "dependencies"]
            )

        # Check for circular import risk (importing from same package)
        file_module = Path(file_path).stem
        same_package_imports = [imp for imp in external_imports if file_module in imp or imp in file_module]

        if len(same_package_imports) > 3:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.ARCHITECTURE,
                title="Potential circular dependency risk",
                description=f"Module imports {len(same_package_imports)} items from the same package",
                location=CodeLocation(file_path=file_path),
                recommendation="Consider restructuring to avoid circular dependencies",
                tags=["circular-dependency", "coupling"]
            )

    async def _check_cohesion(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for low cohesion in classes."""

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Track which methods use which attributes
                class_attributes = set()
                method_attribute_usage = {}

                # Collect class attributes
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                class_attributes.add(target.id)

                # Track attribute usage in methods
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('__')]

                for method in methods:
                    used_attributes = set()
                    for child in ast.walk(method):
                        if isinstance(child, ast.Attribute):
                            if isinstance(child.value, ast.Name) and child.value.id == 'self':
                                used_attributes.add(child.attr)

                    method_attribute_usage[method.name] = used_attributes

                # Calculate cohesion (simplified LCOM metric)
                if len(methods) > 3 and class_attributes:
                    # If many methods don't share attributes, cohesion is low
                    methods_using_no_attrs = sum(1 for attrs in method_attribute_usage.values() if not attrs)

                    if methods_using_no_attrs > len(methods) * 0.5:
                        self.add_finding(
                            severity=Severity.MEDIUM,
                            category=Category.ARCHITECTURE,
                            title=f"Low cohesion in class {node.name}",
                            description=f"{methods_using_no_attrs} of {len(methods)} methods don't use class attributes",
                            location=CodeLocation(
                                file_path=file_path,
                                line_start=node.lineno,
                                class_name=node.name
                            ),
                            recommendation="Split into multiple cohesive classes or make methods module-level functions",
                            tags=["cohesion", "solid", "design"]
                        )

    async def _collect_dependencies(self, file_path: str, tree: ast.AST) -> None:
        """Collect module dependencies for circular dependency detection."""
        module_name = Path(file_path).stem

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.module_imports[module_name].add(alias.name)
                elif node.module:
                    self.module_imports[module_name].add(node.module)

    async def _check_design_patterns(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for common design pattern issues."""

        # Check for Singleton anti-pattern (global state)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Look for __instance or _instance class variables
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                if target.id in ['__instance', '_instance', 'instance']:
                                    self.add_finding(
                                        severity=Severity.LOW,
                                        category=Category.ARCHITECTURE,
                                        title=f"Singleton pattern in {node.name}",
                                        description="Singleton pattern detected - may hinder testing and create global state",
                                        location=CodeLocation(
                                            file_path=file_path,
                                            line_start=item.lineno,
                                            class_name=node.name
                                        ),
                                        recommendation="Consider dependency injection instead of Singleton",
                                        tags=["singleton", "global-state", "anti-pattern"]
                                    )

        # Check for God Object pattern (already covered in cohesion)

        # Check for Anemic Domain Model (classes with only getters/setters)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                property_methods = sum(1 for m in methods if m.name.startswith(('get_', 'set_')) or
                                      any(isinstance(d, ast.Name) and d.id == 'property' for d in m.decorator_list))

                if len(methods) > 3 and property_methods / len(methods) > 0.7:
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.ARCHITECTURE,
                        title=f"Anemic domain model: {node.name}",
                        description="Class mostly consists of getters/setters without business logic",
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=node.lineno,
                            class_name=node.name
                        ),
                        recommendation="Add business logic methods to the class or use simple dataclasses",
                        tags=["anemic-model", "design-pattern"]
                    )

    async def _check_separation_of_concerns(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check for separation of concerns violations."""

        # Check if UI logic is mixed with business logic
        has_ui_code = any(keyword in code for keyword in ['print(', 'input(', 'click.', 'tkinter'])
        has_business_logic = any(keyword in code for keyword in ['calculate', 'process', 'validate', 'compute'])

        if has_ui_code and has_business_logic:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.ARCHITECTURE,
                title="Mixed UI and business logic",
                description="File contains both UI code and business logic",
                location=CodeLocation(file_path=file_path),
                recommendation="Separate UI layer from business logic layer",
                tags=["separation-of-concerns", "architecture"]
            )

        # Check if data access is mixed with business logic
        has_db_code = any(keyword in code.lower() for keyword in ['sql', 'query', 'select ', 'insert ', 'update ', 'delete '])
        has_api_endpoints = '@app.' in code or '@router.' in code

        if has_db_code and has_api_endpoints:
            # This is acceptable in small apps, but warn for larger files
            lines = len(code.split('\n'))
            if lines > 200:
                self.add_finding(
                    severity=Severity.LOW,
                    category=Category.ARCHITECTURE,
                    title="Mixed API and data access layers",
                    description="Large file contains both API endpoints and database access",
                    location=CodeLocation(file_path=file_path),
                    recommendation="Consider separating into repository/service/controller layers",
                    tags=["layering", "separation-of-concerns"]
                )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get architecture-specific patterns for matching."""
        return [
            {
                'pattern': r'global\s+\w+',
                'severity': Severity.MEDIUM,
                'category': Category.ARCHITECTURE,
                'title': "Global variable usage",
                'description': "Global variables increase coupling and make testing difficult",
                'recommendation': "Use dependency injection or class attributes instead"
            },
            {
                'pattern': r'from\s+\.\s+import\s+\*',
                'severity': Severity.MEDIUM,
                'category': Category.ARCHITECTURE,
                'title': "Relative wildcard import",
                'description': "Wildcard imports from relative modules create tight coupling",
                'recommendation': "Import specific items explicitly"
            }
        ]
