"""
Base class for all code review agents.

This module provides the foundation for specialized review agents,
including common methods for analysis, pattern matching, and reporting.
"""

import ast
import re
import uuid
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.agents.review_models import (
    Category,
    CodeLocation,
    Finding,
    ReviewConfig,
    ReviewMetrics,
    ReviewReport,
    ReviewSummary,
    Severity,
)
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class BaseReviewAgent(BaseAgent):
    """Base class for all review agents."""

    def __init__(
            self,
            config: AgentConfig,
            review_config: Optional[ReviewConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        super().__init__(config, memory_store or InMemoryStore(), llm_service)
        self.review_config = review_config or ReviewConfig()
        self.findings: List[Finding] = []
        self.metrics: ReviewMetrics = ReviewMetrics()

    async def specialized_capability(self, **kwargs) -> Dict[str, Any]:
        """
        Main entry point for review agents.
        Calls the review method and returns results.
        """
        target = kwargs.get("target")
        context = kwargs.get("context", {})

        if not target:
            return {"error": "No target specified for review"}

        report = await self.review(target, context)
        return {"report": report.to_dict()}

    async def review(self, target: str, context: Dict[str, Any] = None) -> ReviewReport:
        """
        Main review method that orchestrates the review process.

        Args:
            target: File path or directory to review
            context: Additional context for the review

        Returns:
            ReviewReport with all findings
        """
        if context is None:
            context = {}

        start_time = datetime.utcnow()
        self.findings = []

        # Determine if target is file or directory
        target_path = Path(target)
        if target_path.is_file():
            await self._review_file(target, context)
        elif target_path.is_dir():
            await self._review_directory(target, context)
        else:
            raise FileNotFoundError(f"Target not found: {target}")

        # Calculate metrics
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Create summary
        summary = self._create_summary(duration)

        # Generate recommendations
        recommendations = self._generate_recommendations()

        # Create report
        report = ReviewReport(
            id=str(uuid.uuid4()),
            timestamp=end_time,
            target=target,
            target_type="file" if target_path.is_file() else "directory",
            agents_used=[self.id],
            summary=summary,
            findings=self.findings,
            metrics=self.metrics,
            recommendations=recommendations,
            metadata={
                "agent_name": self.config.name,
                "agent_version": "1.0",
                "review_duration": duration
            }
        )

        return report

    async def _review_file(self, file_path: str, context: Dict[str, Any]) -> None:
        """Review a single file."""
        try:
            with open(file_path, encoding='utf-8') as f:
                code = f.read()

            # Run different analysis passes
            await self.static_analysis(file_path, code, context)

            if self.review_config.enable_llm_analysis:
                await self.llm_analysis(file_path, code, context)

            await self.pattern_matching(file_path, code, context)

        except Exception as e:
            # Add finding about review failure
            self.add_finding(
                severity=Severity.INFO,
                category=Category.QUALITY,
                title=f"Unable to review file: {file_path}",
                description=f"Error during review: {str(e)}",
                location=CodeLocation(file_path=file_path),
                recommendation="Check file encoding and syntax"
            )

    async def _review_directory(self, dir_path: str, context: Dict[str, Any]) -> None:
        """Review all files in a directory."""
        directory = Path(dir_path)

        # Get all Python files (can be extended for other languages)
        python_files = list(directory.rglob("*.py"))

        for file_path in python_files:
            # Skip venv and cache directories (match exact path components,
            # not substrings, so '.github' != '.git' and a parent dir merely
            # named '*venv*' doesn't suppress the whole review)
            if {'venv', '__pycache__', '.git', 'node_modules'} & set(file_path.parts):
                continue

            await self._review_file(str(file_path), context)

    @abstractmethod
    async def static_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """
        Perform fast, rule-based static analysis.
        Each review agent must implement this method.
        """
        pass

    async def llm_analysis(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """
        Perform deep analysis using LLM.
        Can be overridden by subclasses for specialized analysis.
        """
        if not self.review_config.enable_llm_analysis:
            return

        # Get existing findings for context
        existing_findings = [f for f in self.findings if f.location.file_path == file_path]
        findings_summary = "\n".join([
            f"- {f.severity.value.upper()}: {f.title}"
            for f in existing_findings[:5]  # Limit to top 5
        ])

        prompt = self._build_llm_prompt(file_path, code, findings_summary)

        try:
            response = await self.llm.generate_completion(
                messages=[
                    {"role": "system", "content": self.config.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model=self.config.model,
                temperature=0.3
            )

            # Parse LLM response and create findings
            await self._parse_llm_findings(file_path, response)

        except Exception as e:
            print(f"LLM analysis error: {e}")

    def _build_llm_prompt(self, file_path: str, code: str, existing_findings: str) -> str:
        """Build prompt for LLM analysis."""
        return f"""Analyze this Python code for {self.config.name} issues.

File: {file_path}

Code:
```python
{code[:3000]}  # Limit code size
```

Existing findings from static analysis:
{existing_findings if existing_findings else "None"}

Please identify any additional issues related to {self.config.description}.
For each issue, provide:
1. Severity (critical/high/medium/low/info)
2. Line number
3. Brief description
4. Recommendation to fix

Format your response as a list of issues, one per line:
[SEVERITY] Line X: Description | Recommendation
"""

    async def _parse_llm_findings(self, file_path: str, llm_response: str) -> None:
        """Parse findings from LLM response."""
        # Simple parsing - can be made more robust
        lines = llm_response.strip().split('\n')

        for line in lines:
            if not line.strip() or not line.startswith('['):
                continue

            try:
                # Parse format: [SEVERITY] Line X: Description | Recommendation
                match = re.match(r'\[(.*?)\]\s*Line\s*(\d+):\s*(.*?)\s*\|\s*(.*)', line)
                if match:
                    severity_str, line_num, description, recommendation = match.groups()

                    severity = self._parse_severity(severity_str.strip().lower())
                    category = self._get_category()  # Implemented by subclass

                    self.add_finding(
                        severity=severity,
                        category=category,
                        title=description.strip()[:100],
                        description=description.strip(),
                        location=CodeLocation(
                            file_path=file_path,
                            line_start=int(line_num)
                        ),
                        recommendation=recommendation.strip(),
                        confidence=0.8  # LLM findings have slightly lower confidence
                    )
            except Exception as e:
                print(f"Error parsing LLM finding: {e}")
                continue

    async def pattern_matching(self, file_path: str, code: str, context: Dict[str, Any]) -> None:
        """
        Perform regex-based pattern matching.
        Can be overridden by subclasses.
        """
        patterns = self._get_patterns()

        for pattern_info in patterns:
            pattern = pattern_info['pattern']
            severity = pattern_info['severity']
            title = pattern_info['title']
            recommendation = pattern_info['recommendation']
            category = pattern_info.get('category', self._get_category())

            matches = re.finditer(pattern, code, re.MULTILINE)

            for match in matches:
                # Calculate line number
                line_num = code[:match.start()].count('\n') + 1

                # Extract code snippet
                lines = code.split('\n')
                snippet = lines[line_num - 1] if line_num <= len(lines) else ""

                self.add_finding(
                    severity=severity,
                    category=category,
                    title=title,
                    description=f"Found pattern: {pattern_info.get('description', title)}",
                    location=CodeLocation(
                        file_path=file_path,
                        line_start=line_num
                    ),
                    recommendation=recommendation,
                    code_snippet=snippet.strip(),
                    confidence=0.95
                )

    def _get_patterns(self) -> List[Dict[str, Any]]:
        """
        Get regex patterns to match.
        Should be overridden by subclasses.
        """
        return []

    @abstractmethod
    def _get_category(self) -> Category:
        """Get the primary category for this review agent."""
        pass

    def add_finding(
            self,
            severity: Severity,
            category: Category,
            title: str,
            description: str,
            location: CodeLocation,
            recommendation: str,
            code_snippet: Optional[str] = None,
            suggested_fix: Optional[str] = None,
            references: Optional[List[str]] = None,
            confidence: float = 1.0,
            tags: Optional[List[str]] = None
    ) -> None:
        """Add a finding to the review results."""
        finding = Finding(
            id=str(uuid.uuid4()),
            agent_id=self.id,
            agent_name=self.config.name,
            severity=severity,
            category=category,
            title=title,
            description=description,
            location=location,
            recommendation=recommendation,
            code_snippet=code_snippet,
            suggested_fix=suggested_fix,
            references=references or [],
            confidence=confidence,
            tags=tags or [],
            metadata={"agent_type": self.__class__.__name__}
        )

        self.findings.append(finding)

    def _create_summary(self, duration: float) -> ReviewSummary:
        """Create summary from findings."""
        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for finding in self.findings:
            severity_key = finding.severity.value
            category_key = finding.category.value

            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1
            by_category[category_key] = by_category.get(category_key, 0) + 1

        summary = ReviewSummary(
            total_findings=len(self.findings),
            by_severity=by_severity,
            by_category=by_category,
            by_agent={self.config.name: len(self.findings)},
            review_duration=duration
        )

        # Calculate risk level and health score
        summary.risk_level = summary.calculate_risk_level()
        summary.overall_score = summary.calculate_health_score()

        return summary

    def _generate_recommendations(self) -> List[str]:
        """Generate top recommendations based on findings."""
        recommendations = []

        # Get critical and high severity findings
        critical_findings = [f for f in self.findings if f.severity == Severity.CRITICAL]
        high_findings = [f for f in self.findings if f.severity == Severity.HIGH]

        if critical_findings:
            recommendations.append(
                f"🔴 CRITICAL: Address {len(critical_findings)} critical issue(s) immediately"
            )

        if high_findings:
            recommendations.append(
                f"🟠 HIGH: Fix {len(high_findings)} high-severity issue(s) as soon as possible"
            )

        # Add category-specific recommendations
        category_counts = {}
        for finding in self.findings:
            if finding.severity in [Severity.CRITICAL, Severity.HIGH]:
                cat = finding.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1

        # Top 3 problematic categories
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        for category, count in sorted_categories:
            emoji = Finding(
                id="", agent_id="", agent_name="", severity=Severity.INFO,
                category=Category(category), title="", description="",
                location=CodeLocation(file_path=""), recommendation=""
            ).get_category_emoji()
            recommendations.append(
                f"{emoji} Focus on {category.replace('_', ' ')}: {count} critical/high issues"
            )

        return recommendations[:5]  # Top 5 recommendations

    def _parse_severity(self, severity_str: str) -> Severity:
        """Parse severity string to Severity enum."""
        severity_map = {
            'critical': Severity.CRITICAL,
            'high': Severity.HIGH,
            'medium': Severity.MEDIUM,
            'low': Severity.LOW,
            'info': Severity.INFO
        }
        return severity_map.get(severity_str.lower(), Severity.INFO)

    def parse_ast(self, code: str) -> Optional[ast.AST]:
        """Parse Python code into AST."""
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    def get_function_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

        return complexity

    def get_function_lines(self, func_node: ast.FunctionDef) -> int:
        """Get number of lines in a function."""
        if hasattr(func_node, 'end_lineno') and hasattr(func_node, 'lineno'):
            return func_node.end_lineno - func_node.lineno + 1
        return 0

    def extract_code_snippet(self, code: str, line_start: int, line_end: Optional[int] = None, context_lines: int = 2) -> str:
        """Extract code snippet with context."""
        lines = code.split('\n')

        start = max(0, line_start - context_lines - 1)
        end = (line_end or line_start) + context_lines

        snippet_lines = lines[start:end]
        return '\n'.join(snippet_lines)
