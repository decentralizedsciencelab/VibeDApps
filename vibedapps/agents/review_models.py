"""
Data models for the code review system.

This module defines the core data structures used by review agents
to report findings, track issues, and generate review reports.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for review findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    """Categories for review findings."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    API_DESIGN = "api_design"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICES = "best_practices"


class RiskLevel(str, Enum):
    """Overall risk levels for review reports."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class CodeLocation(BaseModel):
    """Represents a location in the codebase."""
    file_path: str = Field(..., description="Path to the file")
    line_start: Optional[int] = Field(None, description="Starting line number")
    line_end: Optional[int] = Field(None, description="Ending line number")
    column_start: Optional[int] = Field(None, description="Starting column")
    column_end: Optional[int] = Field(None, description="Ending column")
    function_name: Optional[str] = Field(None, description="Function or method name")
    class_name: Optional[str] = Field(None, description="Class name if applicable")

    def __str__(self) -> str:
        """String representation of the code location."""
        location = self.file_path
        if self.line_start:
            location += f":{self.line_start}"
            if self.line_end and self.line_end != self.line_start:
                location += f"-{self.line_end}"
        if self.function_name:
            location += f" in {self.function_name}()"
        if self.class_name:
            location += f" ({self.class_name})"
        return location


class Finding(BaseModel):
    """Represents a single finding from a code review."""
    id: str = Field(..., description="Unique identifier for the finding")
    agent_id: str = Field(..., description="ID of the agent that found this issue")
    agent_name: str = Field(..., description="Name of the review agent")
    severity: Severity = Field(..., description="Severity level of the finding")
    category: Category = Field(..., description="Category of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the issue")
    location: CodeLocation = Field(..., description="Location in the codebase")
    recommendation: str = Field(..., description="How to fix the issue")
    code_snippet: Optional[str] = Field(None, description="Relevant code snippet")
    suggested_fix: Optional[str] = Field(None, description="Suggested code fix")
    references: List[str] = Field(default_factory=list, description="Links to documentation/resources")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence level (0-1)")
    tags: List[str] = Field(default_factory=list, description="Additional tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the finding was detected")

    def get_severity_emoji(self) -> str:
        """Get emoji representation of severity."""
        emoji_map = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🔵",
            Severity.INFO: "⚪"
        }
        return emoji_map.get(self.severity, "")

    def get_category_emoji(self) -> str:
        """Get emoji representation of category."""
        emoji_map = {
            Category.SECURITY: "🔒",
            Category.PERFORMANCE: "⚡",
            Category.QUALITY: "✨",
            Category.ERROR_HANDLING: "❌",
            Category.TESTING: "🧪",
            Category.DOCUMENTATION: "📝",
            Category.ARCHITECTURE: "🏗️",
            Category.API_DESIGN: "🔌",
            Category.MAINTAINABILITY: "🔧",
            Category.BEST_PRACTICES: "💎"
        }
        return emoji_map.get(self.category, "")


class ReviewSummary(BaseModel):
    """Summary statistics for a review report."""
    total_findings: int = Field(0, description="Total number of findings")
    by_severity: Dict[str, int] = Field(default_factory=dict, description="Findings grouped by severity")
    by_category: Dict[str, int] = Field(default_factory=dict, description="Findings grouped by category")
    by_agent: Dict[str, int] = Field(default_factory=dict, description="Findings per agent")
    files_reviewed: int = Field(0, description="Number of files reviewed")
    lines_reviewed: int = Field(0, description="Total lines of code reviewed")
    overall_score: float = Field(100.0, ge=0.0, le=100.0, description="Overall health score (0-100)")
    risk_level: RiskLevel = Field(RiskLevel.MINIMAL, description="Overall risk assessment")
    review_duration: float = Field(0.0, description="Review duration in seconds")

    def calculate_risk_level(self) -> RiskLevel:
        """Calculate overall risk level based on findings."""
        if self.by_severity.get(Severity.CRITICAL, 0) > 0:
            return RiskLevel.CRITICAL
        elif self.by_severity.get(Severity.HIGH, 0) >= 5:
            return RiskLevel.HIGH
        elif self.by_severity.get(Severity.HIGH, 0) > 0 or self.by_severity.get(Severity.MEDIUM, 0) >= 10:
            return RiskLevel.MEDIUM
        elif self.by_severity.get(Severity.MEDIUM, 0) > 0 or self.by_severity.get(Severity.LOW, 0) >= 10:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def calculate_health_score(self) -> float:
        """Calculate health score based on findings (0-100, higher is better)."""
        # Base score
        score = 100.0

        # Deduct points based on severity
        score -= self.by_severity.get(Severity.CRITICAL, 0) * 10
        score -= self.by_severity.get(Severity.HIGH, 0) * 5
        score -= self.by_severity.get(Severity.MEDIUM, 0) * 2
        score -= self.by_severity.get(Severity.LOW, 0) * 0.5

        # Ensure score doesn't go below 0
        return max(0.0, min(100.0, score))


class ReviewMetrics(BaseModel):
    """Detailed metrics from a code review."""
    cyclomatic_complexity: Dict[str, float] = Field(default_factory=dict, description="Complexity metrics")
    code_coverage: Optional[float] = Field(None, description="Test coverage percentage")
    duplication_percentage: Optional[float] = Field(None, description="Code duplication percentage")
    maintainability_index: Optional[float] = Field(None, description="Maintainability index (0-100)")
    technical_debt_ratio: Optional[float] = Field(None, description="Technical debt ratio")
    dependency_count: Optional[int] = Field(None, description="Number of dependencies")
    security_score: Optional[float] = Field(None, description="Security score (0-100)")
    performance_score: Optional[float] = Field(None, description="Performance score (0-100)")
    custom_metrics: Dict[str, Any] = Field(default_factory=dict, description="Custom agent-specific metrics")


class ReviewReport(BaseModel):
    """Complete review report with findings and analysis."""
    id: str = Field(..., description="Unique identifier for the report")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the review was completed")
    target: str = Field(..., description="Target of the review (file/directory/project)")
    target_type: str = Field("file", description="Type of target (file, directory, project)")
    agents_used: List[str] = Field(default_factory=list, description="List of agent IDs used")
    summary: ReviewSummary = Field(..., description="Summary of findings")
    findings: List[Finding] = Field(default_factory=list, description="All findings")
    metrics: ReviewMetrics = Field(default_factory=ReviewMetrics, description="Detailed metrics")
    recommendations: List[str] = Field(default_factory=list, description="Top recommendations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_findings_by_severity(self, severity: Severity) -> List[Finding]:
        """Get all findings of a specific severity."""
        return [f for f in self.findings if f.severity == severity]

    def get_findings_by_category(self, category: Category) -> List[Finding]:
        """Get all findings of a specific category."""
        return [f for f in self.findings if f.category == category]

    def get_findings_by_file(self, file_path: str) -> List[Finding]:
        """Get all findings for a specific file."""
        return [f for f in self.findings if f.location.file_path == file_path]

    def get_critical_findings(self) -> List[Finding]:
        """Get all critical and high severity findings."""
        return [f for f in self.findings if f.severity in [Severity.CRITICAL, Severity.HIGH]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return self.model_dump()

    def to_json(self, **kwargs) -> str:
        """Convert report to JSON string."""
        return self.model_dump_json(**kwargs)


class ReviewRequest(BaseModel):
    """Request to perform a code review."""
    target: str = Field(..., description="Path to file/directory to review")
    target_type: str = Field("file", description="Type of target")
    agents: Optional[List[str]] = Field(None, description="Specific agents to use (None = all)")
    severity_threshold: Severity = Field(Severity.INFO, description="Minimum severity to report")
    include_suggestions: bool = Field(True, description="Include code fix suggestions")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ReviewConfig(BaseModel):
    """Configuration for review agents."""
    enabled_categories: List[Category] = Field(
        default_factory=lambda: list(Category),
        description="Categories to check"
    )
    severity_weights: Dict[Severity, float] = Field(
        default_factory=lambda: {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 5.0,
            Severity.MEDIUM: 2.0,
            Severity.LOW: 0.5,
            Severity.INFO: 0.1
        },
        description="Weights for calculating scores"
    )
    max_findings_per_agent: int = Field(100, description="Maximum findings per agent")
    enable_llm_analysis: bool = Field(True, description="Enable LLM-based deep analysis")
    enable_auto_fix: bool = Field(False, description="Enable automatic fix suggestions")
    parallel_execution: bool = Field(True, description="Run agents in parallel")
    timeout_seconds: int = Field(300, description="Timeout for review process")
