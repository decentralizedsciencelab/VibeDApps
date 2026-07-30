"""
Security Auditor Agent - Reviews code for security vulnerabilities.

This agent performs comprehensive security analysis including:
- Input validation issues
- Authentication/authorization flaws
- Injection vulnerabilities
- Sensitive data exposure
- Security misconfiguration
- API security issues
"""

import ast
import re
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig
from vibedapps.agents.review_models import Category, CodeLocation, ReviewConfig, Severity
from vibedapps.agents.specialized.base_review_agent import BaseReviewAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class SecurityAuditorAgent(BaseReviewAgent):
    """Agent specialized in security code reviews."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        if not config:
            config = AgentConfig(
                name="Security Auditor",
                description="Identifies security vulnerabilities and unsafe coding practices",
                capabilities=[
                    "injection_detection",
                    "authentication_review",
                    "authorization_check",
                    "data_exposure_scan",
                    "api_security_audit",
                    "secret_detection",
                    "cors_policy_review",
                    "input_validation_check"
                ],
                model="gpt-4o",
                temperature=0.2,  # Low temperature for consistent security analysis
                system_prompt=(
                    "You are a security expert specializing in code review. "
                    "Your task is to identify security vulnerabilities, unsafe coding practices, "
                    "and potential attack vectors in code. Focus on OWASP Top 10 and common "
                    "security issues. Provide specific, actionable recommendations."
                )
            )

        super().__init__(config, review_config, memory_store or InMemoryStore(), llm_service)

    def _get_category(self) -> Category:
        """Return the primary category for this agent."""
        return Category.SECURITY

    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """Perform static security analysis."""

        # Check for hardcoded secrets
        await self._check_hardcoded_secrets(file_path, code)

        # Check for SQL injection vulnerabilities
        await self._check_sql_injection(file_path, code)

        # Check for command injection
        await self._check_command_injection(file_path, code)

        # Check for insecure crypto
        await self._check_insecure_crypto(file_path, code)

        # Check for path traversal
        await self._check_path_traversal(file_path, code)

        # Check for unsafe deserialization
        await self._check_unsafe_deserialization(file_path, code)

        # Check for CORS issues
        await self._check_cors_issues(file_path, code)

        # Check for weak authentication
        await self._check_weak_authentication(file_path, code)

        # Check for missing input validation
        await self._check_input_validation(file_path, code)

        # Check AST for security issues
        tree = self.parse_ast(code)
        if tree:
            await self._check_ast_security(file_path, code, tree)

    async def _check_hardcoded_secrets(self, file_path: str, code: str) -> None:
        """Check for hardcoded secrets and credentials."""
        secret_patterns = [
            {
                'pattern': r'(?i)(password|passwd|pwd)\s*=\s*["\'](?!.*\$\{)[^"\']{8,}["\']',
                'title': "Hardcoded password detected",
                'description': "Password appears to be hardcoded in the source code",
                'severity': Severity.CRITICAL
            },
            {
                'pattern': r'(?i)(api[_-]?key|apikey|secret[_-]?key)\s*=\s*["\'][A-Za-z0-9+/=]{20,}["\']',
                'title': "Hardcoded API key detected",
                'description': "API key or secret key appears to be hardcoded",
                'severity': Severity.CRITICAL
            },
            {
                'pattern': r'(?i)(access[_-]?token|auth[_-]?token)\s*=\s*["\'][^"\']{20,}["\']',
                'title': "Hardcoded auth token detected",
                'description': "Authentication token appears to be hardcoded",
                'severity': Severity.HIGH
            },
            {
                'pattern': r'(?i)(private[_-]?key|secret)\s*=\s*["\'][^"\']{32,}["\']',
                'title': "Hardcoded private key or secret detected",
                'description': "Private key or secret appears to be hardcoded",
                'severity': Severity.CRITICAL
            },
            {
                'pattern': r'aws_secret_access_key\s*=\s*["\'][^"\']+["\']',
                'title': "AWS secret key hardcoded",
                'description': "AWS secret access key is hardcoded",
                'severity': Severity.CRITICAL
            }
        ]

        for pattern_info in secret_patterns:
            matches = re.finditer(pattern_info['pattern'], code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                self.add_finding(
                    severity=pattern_info['severity'],
                    category=Category.SECURITY,
                    title=pattern_info['title'],
                    description=pattern_info['description'],
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use environment variables or a secrets management system. Never commit secrets to version control.",
                    references=[
                        "https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password"
                    ],
                    tags=["secrets", "credentials", "owasp"]
                )

    async def _check_sql_injection(self, file_path: str, code: str) -> None:
        """Check for SQL injection vulnerabilities."""
        sql_patterns = [
            {
                'pattern': r'(execute|executemany)\s*\([^)]*%[sd].*?\)',
                'title': "Potential SQL injection via string formatting",
                'description': "SQL query uses string formatting which can lead to SQL injection"
            },
            {
                'pattern': r'(execute|executemany)\s*\([^)]*\+\s*["\']',
                'title': "Potential SQL injection via string concatenation",
                'description': "SQL query uses string concatenation which can lead to SQL injection"
            },
            {
                'pattern': r'(execute|executemany)\s*\([^)]*f["\']',
                'title': "Potential SQL injection via f-string",
                'description': "SQL query uses f-string which can lead to SQL injection"
            }
        ]

        for pattern_info in sql_patterns:
            matches = re.finditer(pattern_info['pattern'], code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.CRITICAL,
                    category=Category.SECURITY,
                    title=pattern_info['title'],
                    description=pattern_info['description'],
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use parameterized queries or an ORM. Never concatenate user input into SQL queries.",
                    code_snippet=snippet,
                    references=[
                        "https://owasp.org/www-community/attacks/SQL_Injection",
                        "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"
                    ],
                    tags=["injection", "sql", "owasp-top-10"]
                )

    async def _check_command_injection(self, file_path: str, code: str) -> None:
        """Check for command injection vulnerabilities."""
        # Check for dangerous subprocess calls with shell=True
        if 'subprocess' in code and 'shell=True' in code:
            matches = re.finditer(r'subprocess\.(call|run|Popen|check_output)\([^)]*shell\s*=\s*True', code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.CRITICAL,
                    category=Category.SECURITY,
                    title="Command injection via shell=True",
                    description="Using shell=True with subprocess can lead to command injection",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Avoid shell=True. Pass commands as a list and validate all inputs.",
                    code_snippet=snippet,
                    references=[
                        "https://docs.python.org/3/library/subprocess.html#security-considerations"
                    ],
                    tags=["injection", "command-injection", "subprocess"]
                )

        # Check for os.system usage
        if 'os.system' in code:
            matches = re.finditer(r'os\.system\s*\(', code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                self.add_finding(
                    severity=Severity.HIGH,
                    category=Category.SECURITY,
                    title="Dangerous use of os.system",
                    description="os.system is vulnerable to command injection",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Use subprocess module with proper argument handling instead of os.system",
                    tags=["injection", "command-injection"]
                )

    async def _check_insecure_crypto(self, file_path: str, code: str) -> None:
        """Check for insecure cryptographic practices."""
        crypto_issues = [
            {
                'pattern': r'hashlib\.(md5|sha1)\s*\(',
                'title': "Use of weak cryptographic hash function",
                'description': "MD5 and SHA1 are cryptographically broken",
                'recommendation': "Use SHA-256 or stronger hash functions for security purposes",
                'severity': Severity.HIGH
            },
            {
                'pattern': r'random\.(random|randint|choice)',
                'title': "Use of non-cryptographic random function",
                'description': "random module is not suitable for security purposes",
                'recommendation': "Use secrets module for cryptographic randomness",
                'severity': Severity.MEDIUM
            },
            {
                'pattern': r'eval\s*\(',
                'title': "Dangerous use of eval()",
                'description': "eval() can execute arbitrary code and should be avoided",
                'recommendation': "Use ast.literal_eval() for safe evaluation or find alternative solutions",
                'severity': Severity.CRITICAL
            }
        ]

        for issue in crypto_issues:
            matches = re.finditer(issue['pattern'], code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                self.add_finding(
                    severity=issue['severity'],
                    category=Category.SECURITY,
                    title=issue['title'],
                    description=issue['description'],
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation=issue['recommendation'],
                    tags=["cryptography", "weak-crypto"]
                )

    async def _check_path_traversal(self, file_path: str, code: str) -> None:
        """Check for path traversal vulnerabilities."""
        if 'open(' in code or 'os.path.join' in code:
            # Look for file operations without path validation
            pattern = r'(open|os\.path\.join)\s*\([^)]*request\.[^)]*\)'
            matches = re.finditer(pattern, code)

            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                snippet = self.extract_code_snippet(code, line_num)

                self.add_finding(
                    severity=Severity.HIGH,
                    category=Category.SECURITY,
                    title="Potential path traversal vulnerability",
                    description="File path from user input without validation can lead to path traversal",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Validate and sanitize file paths. Use os.path.realpath() and check if path starts with allowed directory.",
                    code_snippet=snippet,
                    references=[
                        "https://owasp.org/www-community/attacks/Path_Traversal"
                    ],
                    tags=["path-traversal", "file-access"]
                )

    async def _check_unsafe_deserialization(self, file_path: str, code: str) -> None:
        """Check for unsafe deserialization."""
        unsafe_patterns = [
            {
                'pattern': r'pickle\.loads?\s*\(',
                'title': "Unsafe use of pickle",
                'description': "Pickle can execute arbitrary code during deserialization",
                'recommendation': "Use JSON or other safe serialization formats for untrusted data"
            },
            {
                'pattern': r'yaml\.load\s*\([^)]*Loader\s*=\s*yaml\.Loader',
                'title': "Unsafe YAML loading",
                'description': "yaml.load with default Loader can execute arbitrary code",
                'recommendation': "Use yaml.safe_load() instead of yaml.load()"
            }
        ]

        for pattern_info in unsafe_patterns:
            matches = re.finditer(pattern_info['pattern'], code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                self.add_finding(
                    severity=Severity.CRITICAL,
                    category=Category.SECURITY,
                    title=pattern_info['title'],
                    description=pattern_info['description'],
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation=pattern_info['recommendation'],
                    tags=["deserialization", "code-execution"]
                )

    async def _check_cors_issues(self, file_path: str, code: str) -> None:
        """Check for CORS misconfigurations."""
        # Check for wildcard CORS
        if 'allow_origins' in code and '*' in code:
            pattern = r'allow_origins\s*=\s*\[[^\]]*["\']\*["\'][^\]]*\]'
            matches = re.finditer(pattern, code)

            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                self.add_finding(
                    severity=Severity.HIGH,
                    category=Category.SECURITY,
                    title="Overly permissive CORS policy",
                    description="CORS allows all origins (*) which can lead to security issues",
                    location=CodeLocation(file_path=file_path, line_start=line_num),
                    recommendation="Restrict CORS to specific trusted origins. Never use '*' in production.",
                    tags=["cors", "api-security"]
                )

    async def _check_weak_authentication(self, file_path: str, code: str) -> None:
        """Check for weak authentication patterns."""
        # Check for missing authentication decorators
        if 'FastAPI' in code or '@app.post' in code or '@app.get' in code:
            # Look for endpoints without authentication
            pattern = r'@app\.(get|post|put|delete|patch)\([^)]*\)\s*\n\s*async\s+def\s+\w+\([^)]*\):'
            matches = re.finditer(pattern, code)

            for match in matches:
                # Check if there's an authentication dependency nearby
                context = code[max(0, match.start()-200):match.end()+200]
                if 'Depends' not in context and 'Authentication' not in context and 'verify' not in context.lower():
                    line_num = code[:match.start()].count('\n') + 1

                    self.add_finding(
                        severity=Severity.MEDIUM,
                        category=Category.SECURITY,
                        title="Endpoint without authentication",
                        description="API endpoint appears to lack authentication mechanism",
                        location=CodeLocation(file_path=file_path, line_start=line_num),
                        recommendation="Add authentication middleware or dependencies to protect sensitive endpoints",
                        tags=["authentication", "api-security"]
                    )

    async def _check_input_validation(self, file_path: str, code: str) -> None:
        """Check for missing input validation."""
        # This is a simplified check - real implementation would be more sophisticated
        if 'request.' in code:
            # Look for direct usage of request data without validation
            pattern = r'request\.(query|form|json|data)\.[a-zA-Z_]+'
            matches = re.finditer(pattern, code)

            # Group by line to avoid duplicates
            lines_with_issues = set()

            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                if line_num in lines_with_issues:
                    continue

                # Check if there's validation nearby
                line_start = code.rfind('\n', 0, match.start()) + 1
                line_end = code.find('\n', match.end())
                line_content = code[line_start:line_end] if line_end != -1 else code[line_start:]

                if 'validate' not in line_content.lower() and 'pydantic' not in line_content.lower():
                    lines_with_issues.add(line_num)

                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.SECURITY,
                        title="Direct use of request data without validation",
                        description="Request data used without explicit validation",
                        location=CodeLocation(file_path=file_path, line_start=line_num),
                        recommendation="Use Pydantic models or explicit validation for all user inputs",
                        tags=["input-validation", "api-security"]
                    )

    async def _check_ast_security(self, file_path: str, code: str, tree: ast.AST) -> None:
        """Perform AST-based security checks."""
        for node in ast.walk(tree):
            # Check for assert statements (shouldn't be used for validation)
            if isinstance(node, ast.Assert):
                if hasattr(node, 'lineno'):
                    self.add_finding(
                        severity=Severity.LOW,
                        category=Category.SECURITY,
                        title="Assert used for validation",
                        description="Assert statements can be disabled with -O flag and shouldn't be used for security checks",
                        location=CodeLocation(file_path=file_path, line_start=node.lineno),
                        recommendation="Use explicit if statements and raise exceptions for validation",
                        tags=["assert", "validation"]
                    )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """Get security-specific patterns for matching."""
        return [
            {
                'pattern': r'\.save\([^)]*safe\s*=\s*False',
                'severity': Severity.MEDIUM,
                'category': Category.SECURITY,
                'title': "Unsafe save operation",
                'description': "Save operation with safe=False can be dangerous",
                'recommendation': "Remove safe=False or ensure data is validated"
            }
        ]
