"""
API Contract Reviewer Agent - Reviews API design and contracts.

This agent performs comprehensive API analysis including:
- Endpoint naming consistency
- HTTP method usage
- Request/response validation
- Versioning strategy
- Breaking change detection
- REST principles adherence
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class APIContractAgent(BaseReviewAgent):
    """Agent specialized in API contract reviews."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="API Contract Reviewer",
                description="Analyzes API design, contracts, and REST principles",
                capabilities=[
                    "endpoint_consistency",
                    "versioning_check",
                    "payload_validation",
                    "response_format_check",
                    "breaking_changes_detection",
                    "rest_principles"
                ],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are an API design expert. Analyze API endpoints for consistency, "
                    "proper HTTP method usage, versioning, validation, and REST principles. "
                    "Focus on API usability, maintainability, and backward compatibility."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

        # Track API endpoints
        self.endpoints: Dict[str, Dict[str, Any]] = {}

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.API_DESIGN

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static API analysis."""

        # Check if this is an API file (FastAPI, Flask, etc.)
        is_api_file = any(framework in code for framework in ['FastAPI', '@app.', '@router.', 'Flask', 'APIRouter'])

        if not is_api_file:
            return  # Skip non-API files

        # Collect endpoints
        await self._collect_endpoints(file_path, code)

        # Check endpoint naming consistency
        await self._check_endpoint_naming(file_path, code)

        # Check HTTP method usage
        await self._check_http_methods(file_path, code)

        # Check for missing versioning
        await self._check_api_versioning(file_path, code)

        # Check request validation
        await self._check_request_validation(file_path, code)

        # Check response models
        await self._check_response_models(file_path, code)

        # AST-based checks
        tree = self.parse_ast(code)
        if tree:
            await self._check_endpoint_consistency(file_path, code, tree)
            await self._check_rest_principles(file_path, code, tree)

    async def _collect_endpoints(self, file_path: str, code: str) -> None:
        """Collect API endpoints from code."""

        # FastAPI/Flask route patterns
        patterns = [
            r'@app\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']\)',
            r'@router\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']\)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                method = match.group(1).upper()
                path = match.group(2)
                line_num = code[:match.start()].count('\n') + 1

                endpoint_key = f"{method} {path}"
                self.endpoints[endpoint_key] = {
                    'method': method,
                    'path': path,
                    'line': line_num,
                    'file': file_path
                }

    async def _check_endpoint_naming(self, file_path: str, code: str) -> None:
        """Check endpoint naming consistency."""

        # Check for inconsistent naming conventions
        paths = [ep['path'] for ep in self.endpoints.values()]

        # Check for mixed naming styles (kebab-case vs snake_case vs camelCase)
        has_kebab = any('-' in path for path in paths)
        has_snake = any('_' in path for path in paths)
        has_camel = any(re.search(r'[a-z][A-Z]', path) for path in paths)

        inconsistencies = sum([has_kebab, has_snake, has_camel])

        if inconsistencies > 1:
            self.add_finding(
                severity=Severity.MEDIUM,
                category=Category.API_DESIGN,
                title="Inconsistent endpoint naming",
                description=f"API uses multiple naming conventions (kebab-case: {has_kebab}, snake_case: {has_snake}, camelCase: {has_camel})",
                location=CodeLocation(file_path=file_path),
                recommendation="Choose one naming convention (preferably kebab-case) and use it consistently",
                tags=["api-design", "naming", "consistency"]
            )

        # Check for non-plural resource names
        for endpoint_key, endpoint in self.endpoints.items():
            path_parts = endpoint['path'].strip('/').split('/')

            # Look for resource names (non-parameter parts)
            for part in path_parts:
                if not part.startswith('{') and not part.endswith('}'):
                    # Check if it looks like a singular noun
                    if not part.endswith('s') and len(part) > 3:
                        # Simple heuristic: if it could be plural but isn't
                        if part.lower() in ['user', 'item', 'product', 'order', 'task', 'file']:
                            self.add_finding(
                                severity=Severity.LOW,
                                category=Category.API_DESIGN,
                                title=f"Singular resource name in {endpoint['path']}",
                                description=f"Resource '{part}' should be plural ('{part}s')",
                                location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                                recommendation="Use plural names for collections (REST best practice)",
                                tags=["rest", "naming", "resources"]
                            )

    async def _check_http_methods(self, file_path: str, code: str) -> None:
        """Check HTTP method usage."""

        # Check for improper method usage
        for endpoint_key, endpoint in self.endpoints.items():
            method = endpoint['method']
            path = endpoint['path']

            # GET shouldn't have request body
            if method == 'GET':
                # Look for Pydantic model or body parameters
                line_num = endpoint['line']
                lines = code.split('\n')

                # Check next few lines for body parameters
                for i in range(line_num, min(line_num + 5, len(lines))):
                    if 'Body(' in lines[i] or ': BaseModel' in lines[i]:
                        self.add_finding(
                            severity=Severity.HIGH,
                            category=Category.API_DESIGN,
                            title=f"GET request with body: {path}",
                            description="GET requests should not have request bodies",
                            location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                            recommendation="Use query parameters or change to POST method",
                            tags=["http-methods", "rest", "api-design"]
                        )
                        break

            # POST/PUT should have request body for data modification
            if method in ['POST', 'PUT'] and '{' not in path:
                # Look for request body
                line_num = endpoint['line']
                lines = code.split('\n')

                has_body = False
                for i in range(line_num, min(line_num + 5, len(lines))):
                    if 'Body(' in lines[i] or ': BaseModel' in lines[i]:
                        has_body = True
                        break

                if not has_body and 'upload' not in path.lower():
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.API_DESIGN,
                        title=f"{method} without request body: {path}",
                        description=f"{method} requests typically should have request bodies",
                        location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                        recommendation="Add request body validation with Pydantic model",
                        tags=["http-methods", "validation"]
                    )

            # DELETE on collections should be avoided
            if method == 'DELETE' and '{' not in path:
                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.API_DESIGN,
                    title=f"DELETE on collection: {path}",
                    description="DELETE on collections is dangerous and should be avoided",
                    location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                    recommendation="DELETE should target specific resources with IDs",
                    tags=["rest", "safety", "api-design"]
                )

    async def _check_api_versioning(self, file_path: str, code: str) -> None:
        """Check for API versioning."""

        if not self.endpoints:
            return

        # Check if any endpoint has versioning
        has_versioning = any(
            re.match(r'/v\d+/', ep['path']) or re.match(r'/api/v\d+/', ep['path'])
            for ep in self.endpoints.values()
        )

        if not has_versioning and len(self.endpoints) > 5:
            self.add_finding(
                severity=Severity.LOW,
                category=Category.API_DESIGN,
                title="Missing API versioning",
                description="API endpoints lack version prefix",
                location=CodeLocation(file_path=file_path),
                recommendation="Add versioning to API paths (e.g., /api/v1/resource) for future compatibility",
                tags=["versioning", "api-design", "compatibility"]
            )

    async def _check_request_validation(self, file_path: str, code: str) -> None:
        """Check for request validation."""

        for endpoint_key, endpoint in self.endpoints.items():
            if endpoint['method'] in ['POST', 'PUT', 'PATCH']:
                line_num = endpoint['line']
                lines = code.split('\n')

                # Look for Pydantic validation
                has_validation = False
                for i in range(line_num, min(line_num + 10, len(lines))):
                    if ': BaseModel' in lines[i] or 'Depends' in lines[i] or 'Body(' in lines[i]:
                        has_validation = True
                        break

                if not has_validation:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.API_DESIGN,
                        title=f"Missing request validation: {endpoint['path']}",
                        description=f"{endpoint['method']} endpoint lacks input validation",
                        location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                        recommendation="Use Pydantic models for request validation",
                        tags=["validation", "security", "api-design"]
                    )

    async def _check_response_models(self, file_path: str, code: str) -> None:
        """Check for response models."""

        for endpoint_key, endpoint in self.endpoints.items():
            line_num = endpoint['line']
            lines = code.split('\n')

            # Look for response_model or return type annotation
            has_response_model = False

            # Check decorator
            if line_num > 0:
                decorator_line = lines[line_num - 1]
                if 'response_model=' in decorator_line:
                    has_response_model = True

            # Check function signature
            for i in range(line_num, min(line_num + 3, len(lines))):
                if '->' in lines[i] and 'None' not in lines[i]:
                    has_response_model = True
                    break

            if not has_response_model:
                self.add_finding(
                    severity=Severity.LOW,
                    category=Category.API_DESIGN,
                    title=f"Missing response model: {endpoint['path']}",
                    description="Endpoint lacks response model definition",
                    location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                    recommendation="Define response_model for automatic validation and documentation",
                    tags=["response-model", "documentation", "validation"]
                )

    async def _check_endpoint_consistency(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check endpoint implementation consistency."""

        # Check for consistent error handling across endpoints
        endpoint_error_patterns = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if this is an endpoint handler
                is_endpoint = any(
                    isinstance(d, ast.Call) and
                    hasattr(d.func, 'attr') and
                    d.func.attr in ['get', 'post', 'put', 'delete', 'patch']
                    for d in node.decorator_list
                )

                if is_endpoint:
                    # Check for try/except
                    has_try_except = any(isinstance(child, ast.Try) for child in ast.walk(node))
                    endpoint_error_patterns[node.name] = has_try_except

        # If some endpoints have error handling but not all
        if endpoint_error_patterns:
            with_error_handling = sum(1 for v in endpoint_error_patterns.values() if v)
            total = len(endpoint_error_patterns)

            if 0 < with_error_handling < total:
                self.add_finding(
                    severity=Severity.MEDIUM,
                    category=Category.API_DESIGN,
                    title="Inconsistent error handling",
                    description=f"{with_error_handling} of {total} endpoints have error handling",
                    location=CodeLocation(file_path=file_path),
                    recommendation="Implement consistent error handling across all endpoints",
                    tags=["error-handling", "consistency"]
                )

    async def _check_rest_principles(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Check adherence to REST principles."""

        # Check for actions in URLs (should use HTTP methods instead)
        action_verbs = ['create', 'update', 'delete', 'add', 'remove', 'get', 'set', 'fetch']

        for endpoint_key, endpoint in self.endpoints.items():
            path = endpoint['path'].lower()

            for verb in action_verbs:
                if verb in path:
                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.API_DESIGN,
                        title=f"Action verb in URL: {endpoint['path']}",
                        description=f"URL contains action verb '{verb}' - not RESTful",
                        location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                        recommendation="Use HTTP methods (GET, POST, PUT, DELETE) instead of action verbs in URLs",
                        tags=["rest", "api-design", "url-design"]
                    )
                    break

        # Check for deeply nested paths
        for endpoint_key, endpoint in self.endpoints.items():
            depth = endpoint['path'].count('/')

            if depth > 4:  # e.g., /api/v1/users/{id}/posts/{post_id}/comments
                self.add_finding(
                    severity=Severity.LOW,
                    category=Category.API_DESIGN,
                    title=f"Deeply nested endpoint: {endpoint['path']}",
                    description=f"URL has {depth} levels of nesting",
                    location=CodeLocation(file_path=file_path, line_start=endpoint['line']),
                    recommendation="Consider flattening the hierarchy or using query parameters",
                    tags=["rest", "url-design", "complexity"]
                )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get API-specific patterns for matching."""
        return [
            {
                'pattern': r'@app\.route\([^)]*methods\s*=\s*\[[^\]]*"GET"[^\]]*,',
                'severity': Severity.LOW,
                'category': Category.API_DESIGN,
                'title': "Multiple HTTP methods on single endpoint",
                'description': "Endpoint handles multiple HTTP methods - consider splitting",
                'recommendation': "Create separate endpoints for each HTTP method"
            },
            {
                'pattern': r'return\s+\{[^}]*"error"',
                'severity': Severity.INFO,
                'category': Category.API_DESIGN,
                'title': "Custom error response format",
                'description': "Returning custom error format - ensure consistency",
                'recommendation': "Use standard error format across all endpoints"
            }
        ]
