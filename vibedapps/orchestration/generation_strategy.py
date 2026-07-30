"""
Generation Strategy Orchestrator

This module provides strategy selection logic for choosing between
LLM-only, tool-based, or hybrid generation approaches based on project
requirements and tool availability.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import structlog

from vibedapps.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class GenerationStrategy(str, Enum):
    """Available generation strategies."""
    LLM_ONLY = "llm_only"
    TOOL_BASED = "tool_based"
    HYBRID = "hybrid"


class ContractComplexity(str, Enum):
    """Contract complexity levels for strategy selection."""
    STANDARD = "standard"  # ERC20, ERC721, ERC1155 with basic features
    MODERATE = "moderate"  # Standard contracts with custom extensions
    COMPLEX = "complex"    # Custom contracts, novel patterns, DeFi protocols


@dataclass
class StrategyRecommendation:
    """Recommendation for which generation strategy to use."""
    strategy: GenerationStrategy
    confidence: float  # 0.0 to 1.0
    reasoning: str
    available_tools: List[str]
    missing_tools: List[str]
    fallback_strategy: Optional[GenerationStrategy] = None


class GenerationStrategyOrchestrator:
    """
    Orchestrates the selection of generation strategies based on:
    - Project specifications (contract type, features, complexity)
    - Available tools (Hardhat, Foundry, OpenZeppelin, etc.)
    - User preferences
    - Security requirements
    """

    # Standard contract types that can be generated efficiently with tools
    STANDARD_CONTRACT_TYPES = {
        "erc20": ["hardhat", "openzeppelin"],
        "erc721": ["hardhat", "openzeppelin"],
        "erc1155": ["hardhat", "openzeppelin"],
    }

    # Contract types that benefit from hybrid approach
    HYBRID_CONTRACT_TYPES = {
        "dao": ["hardhat", "openzeppelin"],
        "defi": ["hardhat", "foundry"],
        "marketplace": ["hardhat", "openzeppelin"],
    }

    # Features that indicate complexity
    COMPLEX_FEATURES = {
        "custom_logic",
        "upgradeable",
        "complex_access_control",
        "cross_chain",
        "oracle_integration",
        "flash_loans",
        "advanced_defi",
    }

    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize the strategy orchestrator.

        Args:
            tool_registry: Registry of available development tools
        """
        self.tool_registry = tool_registry
        self.logger = logger.bind(component="strategy_orchestrator")

    def recommend_strategy(
        self,
        contract_type: str,
        contract_features: Dict[str, bool],
        project_description: str = "",
        user_preference: Optional[GenerationStrategy] = None,
        security_priority: bool = False,
    ) -> StrategyRecommendation:
        """
        Recommend the best generation strategy for the given project.

        Args:
            contract_type: Type of contract (erc20, erc721, dao, etc.)
            contract_features: Dictionary of enabled features
            project_description: Description of the project
            user_preference: User's preferred strategy (if any)
            security_priority: Whether security is a high priority

        Returns:
            StrategyRecommendation with strategy, confidence, and reasoning
        """
        self.logger.info(
            "recommending_strategy",
            contract_type=contract_type,
            features=contract_features,
            user_preference=user_preference,
            security_priority=security_priority,
        )

        # Get available tools
        available_tools = self.tool_registry.get_all_tools()
        available_tool_names = {tool.name for tool in available_tools if tool.is_available}

        # Determine contract complexity
        complexity = self._assess_complexity(
            contract_type, contract_features, project_description
        )

        # Check if user has explicit preference
        if user_preference:
            return self._validate_user_preference(
                user_preference, available_tool_names, complexity
            )

        # Recommend strategy based on complexity and tool availability
        if complexity == ContractComplexity.STANDARD:
            return self._recommend_for_standard(
                contract_type, available_tool_names, security_priority
            )
        elif complexity == ContractComplexity.MODERATE:
            return self._recommend_for_moderate(
                contract_type, available_tool_names, security_priority
            )
        else:  # COMPLEX
            return self._recommend_for_complex(
                contract_type, available_tool_names, security_priority
            )

    def _assess_complexity(
        self,
        contract_type: str,
        contract_features: Dict[str, bool],
        project_description: str,
    ) -> ContractComplexity:
        """Assess the complexity level of the contract."""
        enabled_features = {k for k, v in contract_features.items() if v}

        # Check for complex features
        has_complex_features = bool(enabled_features & self.COMPLEX_FEATURES)

        # Check if it's a standard contract with minimal features
        is_standard_type = contract_type.lower() in self.STANDARD_CONTRACT_TYPES
        has_basic_features_only = enabled_features <= {
            "mintable", "burnable", "pausable", "ownable", "capped", "votes"
        }

        # Keywords indicating complexity in description
        complex_keywords = [
            "custom", "advanced", "novel", "unique", "complex",
            "multi-sig", "governance", "protocol", "mechanism"
        ]
        has_complex_description = any(
            keyword in project_description.lower() for keyword in complex_keywords
        )

        if has_complex_features or has_complex_description:
            return ContractComplexity.COMPLEX
        elif is_standard_type and has_basic_features_only:
            return ContractComplexity.STANDARD
        else:
            return ContractComplexity.MODERATE

    def _recommend_for_standard(
        self,
        contract_type: str,
        available_tools: set,
        security_priority: bool,
    ) -> StrategyRecommendation:
        """Recommend strategy for standard contracts."""
        contract_type_lower = contract_type.lower()
        required_tools = set(self.STANDARD_CONTRACT_TYPES.get(contract_type_lower, []))
        missing_tools = required_tools - available_tools

        if not missing_tools:
            # All tools available, use tool-based generation
            return StrategyRecommendation(
                strategy=GenerationStrategy.TOOL_BASED,
                confidence=0.95,
                reasoning=(
                    f"Standard {contract_type} contract with all required tools available. "
                    "Tool-based generation provides fastest and most reliable results."
                ),
                available_tools=list(available_tools & required_tools),
                missing_tools=[],
                fallback_strategy=GenerationStrategy.LLM_ONLY,
            )
        elif "openzeppelin" in available_tools or "hardhat" in available_tools:
            # Some tools available, use hybrid
            return StrategyRecommendation(
                strategy=GenerationStrategy.HYBRID,
                confidence=0.85,
                reasoning=(
                    f"Standard {contract_type} contract with partial tool availability. "
                    "Hybrid approach combines tool scaffolding with LLM customization."
                ),
                available_tools=list(available_tools & required_tools),
                missing_tools=list(missing_tools),
                fallback_strategy=GenerationStrategy.LLM_ONLY,
            )
        else:
            # No tools available, use LLM-only
            return StrategyRecommendation(
                strategy=GenerationStrategy.LLM_ONLY,
                confidence=0.80,
                reasoning=(
                    f"Required tools not available. Using LLM-only generation "
                    f"for {contract_type} contract."
                ),
                available_tools=[],
                missing_tools=list(required_tools),
                fallback_strategy=None,
            )

    def _recommend_for_moderate(
        self,
        contract_type: str,
        available_tools: set,
        security_priority: bool,
    ) -> StrategyRecommendation:
        """Recommend strategy for moderately complex contracts."""
        has_hardhat = "hardhat" in available_tools
        has_foundry = "foundry" in available_tools
        has_oz = "openzeppelin" in available_tools

        if (has_hardhat or has_foundry) and has_oz:
            # Tools available, use hybrid approach
            available = []
            if has_hardhat:
                available.append("hardhat")
            if has_foundry:
                available.append("foundry")
            if has_oz:
                available.append("openzeppelin")

            return StrategyRecommendation(
                strategy=GenerationStrategy.HYBRID,
                confidence=0.90,
                reasoning=(
                    f"Moderate complexity {contract_type} contract. Hybrid approach "
                    "uses tool scaffolding for standard parts and LLM for custom logic."
                ),
                available_tools=available,
                missing_tools=[],
                fallback_strategy=GenerationStrategy.LLM_ONLY,
            )
        else:
            # Tools not available, use LLM with high temperature for creativity
            return StrategyRecommendation(
                strategy=GenerationStrategy.LLM_ONLY,
                confidence=0.75,
                reasoning=(
                    f"Moderate complexity {contract_type} requires custom logic. "
                    "LLM-only generation provides flexibility for custom features."
                ),
                available_tools=list(available_tools),
                missing_tools=["hardhat", "openzeppelin"],
                fallback_strategy=None,
            )

    def _recommend_for_complex(
        self,
        contract_type: str,
        available_tools: set,
        security_priority: bool,
    ) -> StrategyRecommendation:
        """Recommend strategy for complex contracts."""
        # Complex contracts always use LLM for maximum flexibility
        # Tools can still be used for compilation and testing
        has_tools = bool(available_tools & {"hardhat", "foundry"})

        if has_tools and not security_priority:
            return StrategyRecommendation(
                strategy=GenerationStrategy.HYBRID,
                confidence=0.70,
                reasoning=(
                    f"Complex {contract_type} contract requires custom implementation. "
                    "Hybrid approach uses LLM for contract logic and tools for infrastructure."
                ),
                available_tools=list(available_tools & {"hardhat", "foundry", "openzeppelin"}),
                missing_tools=[],
                fallback_strategy=GenerationStrategy.LLM_ONLY,
            )
        else:
            return StrategyRecommendation(
                strategy=GenerationStrategy.LLM_ONLY,
                confidence=0.85,
                reasoning=(
                    f"Complex {contract_type} with novel requirements. "
                    "LLM-only generation provides maximum flexibility and creativity. "
                    + ("High security priority requires thorough review." if security_priority else "")
                ),
                available_tools=list(available_tools),
                missing_tools=[],
                fallback_strategy=None,
            )

    def _validate_user_preference(
        self,
        preference: GenerationStrategy,
        available_tools: set,
        complexity: ContractComplexity,
    ) -> StrategyRecommendation:
        """Validate and potentially override user preference based on constraints."""
        if preference == GenerationStrategy.TOOL_BASED:
            # Check if tools are available
            if not available_tools:
                self.logger.warning(
                    "user_preference_override",
                    requested=preference,
                    reason="no_tools_available",
                )
                return StrategyRecommendation(
                    strategy=GenerationStrategy.LLM_ONLY,
                    confidence=0.70,
                    reasoning=(
                        "User requested tool-based generation but no tools are available. "
                        "Falling back to LLM-only generation."
                    ),
                    available_tools=[],
                    missing_tools=["hardhat", "openzeppelin"],
                    fallback_strategy=None,
                )

        # User preference is valid
        return StrategyRecommendation(
            strategy=preference,
            confidence=0.80,
            reasoning=f"Using user-requested {preference.value} strategy.",
            available_tools=list(available_tools),
            missing_tools=[],
            fallback_strategy=None if preference == GenerationStrategy.LLM_ONLY
                         else GenerationStrategy.LLM_ONLY,
        )

    def get_fallback_strategy(
        self, failed_strategy: GenerationStrategy
    ) -> Optional[GenerationStrategy]:
        """
        Get fallback strategy when primary strategy fails.

        Args:
            failed_strategy: The strategy that failed

        Returns:
            Fallback strategy or None if no fallback available
        """
        if failed_strategy == GenerationStrategy.TOOL_BASED:
            return GenerationStrategy.HYBRID
        elif failed_strategy == GenerationStrategy.HYBRID:
            return GenerationStrategy.LLM_ONLY
        else:
            return None  # LLM_ONLY has no fallback
