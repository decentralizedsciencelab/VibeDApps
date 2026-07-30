"""
Heterogeneous Generator - Hybrid Code Generation

Mixes LLM-generated code with verified templates and symbolic invariants.
Requirement 8.4: Create hybrid generator that mixes LLM code with verified templates
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .pattern_composer import PatternComposer
from .symbolic_generator import Invariant, SymbolicGenerator
from .template_library import TemplateLibrary


class GenerationStrategy(Enum):
    """Code generation strategies"""
    PURE_LLM = "pure_llm"              # 100% LLM generated
    TEMPLATE_HEAVY = "template_heavy"  # 70% templates, 30% LLM
    BALANCED = "balanced"              # 50% LLM, 30% templates, 20% symbolic
    LLM_HEAVY = "llm_heavy"           # 70% LLM, 20% templates, 10% symbolic
    SYMBOLIC_HEAVY = "symbolic_heavy"  # 50% templates, 30% symbolic, 20% LLM


@dataclass
class GenerationConfig:
    """Configuration for heterogeneous generation"""
    llm_percentage: float = 0.5      # 50% LLM-generated
    template_percentage: float = 0.3  # 30% verified templates
    symbolic_percentage: float = 0.2  # 20% symbolic invariants
    strategy: GenerationStrategy = GenerationStrategy.BALANCED
    enable_invariants: bool = True
    enable_templates: bool = True
    security_level: str = "high"  # low, medium, high


@dataclass
class GeneratedContract:
    """Result of heterogeneous generation"""
    name: str
    solidity_code: str
    generation_breakdown: Dict[str, float]
    patterns_used: List[str]
    invariants_added: List[str]
    llm_sections: List[str]
    security_properties: List[str]
    composition_method: str


class HeterogeneousGenerator:
    """
    Hybrid generator that mixes LLM-generated code with verified templates
    and symbolic invariants to reduce vulnerability homogeneity.
    
    This approach provides:
    - Diversity in code generation (reduces common vulnerability patterns)
    - Formal guarantees through symbolic invariants
    - Battle-tested security through OpenZeppelin templates
    - Flexibility through LLM-generated custom logic
    """
    
    def __init__(
        self,
        llm_service=None,  # Optional LLM service for code generation
        config: Optional[GenerationConfig] = None
    ):
        self.llm_service = llm_service
        self.config = config or GenerationConfig()
        self.template_library = TemplateLibrary()
        self.symbolic_generator = SymbolicGenerator()
        self.pattern_composer = PatternComposer(self.template_library)
    
    async def generate_contract(
        self,
        contract_spec: Dict,
        strategy: Optional[GenerationStrategy] = None
    ) -> GeneratedContract:
        """
        Generate a contract using heterogeneous code generation.
        
        Args:
            contract_spec: Specification for the contract
            strategy: Optional generation strategy override
            
        Returns:
            GeneratedContract with mixed code sources
        """
        if strategy:
            self.config.strategy = strategy
            self._update_percentages_for_strategy(strategy)
        
        contract_name = contract_spec.get("name", "GeneratedContract")
        contract_type = contract_spec.get("type", "custom")
        features = contract_spec.get("features", [])
        custom_logic = contract_spec.get("custom_logic", "")
        
        # Step 1: Identify applicable templates
        patterns = self._select_patterns(contract_type, features)
        
        # Step 2: Compose base contract from templates
        if patterns and self.config.enable_templates:
            composed = self.pattern_composer.compose_contract(
                contract_name,
                patterns,
                custom_functions=None  # Will add custom logic later
            )
            base_code = composed.solidity_code
            patterns_used = patterns
            security_properties = list(composed.security_properties)
        else:
            # Fallback to pure LLM generation
            base_code = await self._generate_llm_contract(contract_spec)
            patterns_used = []
            security_properties = []
        
        # Step 3: Generate symbolic invariants
        invariants = []
        invariants_added = []
        if self.config.enable_invariants:
            invariants = self._generate_invariants(contract_type, features)
            invariants_added = [inv.name for inv in invariants]
        
        # Step 4: Add custom LLM-generated logic
        llm_sections = []
        if custom_logic or self.config.llm_percentage > 0:
            base_code, llm_sections = await self._add_custom_logic(
                base_code,
                contract_spec,
                custom_logic
            )
        
        # Step 5: Add invariant verification functions
        if invariants:
            base_code = self.symbolic_generator.add_invariants_to_contract(
                base_code,
                invariants
            )
        
        # Calculate actual generation breakdown
        breakdown = self._calculate_breakdown(
            base_code,
            patterns_used,
            invariants_added,
            llm_sections
        )
        
        return GeneratedContract(
            name=contract_name,
            solidity_code=base_code,
            generation_breakdown=breakdown,
            patterns_used=patterns_used,
            invariants_added=invariants_added,
            llm_sections=llm_sections,
            security_properties=security_properties,
            composition_method=self.config.strategy.value
        )
    
    def _update_percentages_for_strategy(self, strategy: GenerationStrategy) -> None:
        """Update generation percentages based on strategy"""
        if strategy == GenerationStrategy.PURE_LLM:
            self.config.llm_percentage = 1.0
            self.config.template_percentage = 0.0
            self.config.symbolic_percentage = 0.0
        elif strategy == GenerationStrategy.TEMPLATE_HEAVY:
            self.config.llm_percentage = 0.3
            self.config.template_percentage = 0.7
            self.config.symbolic_percentage = 0.0
        elif strategy == GenerationStrategy.BALANCED:
            self.config.llm_percentage = 0.5
            self.config.template_percentage = 0.3
            self.config.symbolic_percentage = 0.2
        elif strategy == GenerationStrategy.LLM_HEAVY:
            self.config.llm_percentage = 0.7
            self.config.template_percentage = 0.2
            self.config.symbolic_percentage = 0.1
        elif strategy == GenerationStrategy.SYMBOLIC_HEAVY:
            self.config.llm_percentage = 0.2
            self.config.template_percentage = 0.5
            self.config.symbolic_percentage = 0.3
    
    def _select_patterns(
        self,
        contract_type: str,
        features: List[str]
    ) -> List[str]:
        """
        Select appropriate patterns based on contract type and features.
        
        Args:
            contract_type: Type of contract (token, defi, dao, etc.)
            features: List of desired features
            
        Returns:
            List of pattern names to use
        """
        patterns = []
        
        # Map contract types to base patterns
        type_patterns = {
            "erc20": ["erc20"],
            "erc721": ["erc721"],
            "erc1155": ["erc1155"],
            "token": ["erc20"],  # Default to ERC20
            "nft": ["erc721"],   # Default to ERC721
        }
        
        # Normalize contract type and resolve canonical base standard.
        # "token"/"nft" alias to "erc20"/"erc721", so plain .lower() is not
        # enough — resolve the base once and use it in all raw comparisons.
        contract_type = contract_type.lower()
        base = type_patterns.get(contract_type, [contract_type])[0]

        # Add base pattern
        if contract_type in type_patterns:
            patterns.extend(type_patterns[contract_type])

        # Add feature patterns
        feature_patterns = {
            "burnable": f"{base}_burnable" if base in ["erc20", "erc721"] else None,
            "capped": "erc20_capped" if base == "erc20" else None,
            "enumerable": "erc721_enumerable" if base == "erc721" else None,
            "pausable": "pausable",
            "ownable": "ownable",
            "access_control": "access_control",
            "reentrancy_guard": "reentrancy_guard"
        }
        
        for feature in features:
            feature_lower = feature.lower()
            if feature_lower in feature_patterns:
                pattern = feature_patterns[feature_lower]
                if pattern and pattern not in patterns:
                    # Verify pattern exists
                    if self.template_library.get_pattern(pattern):
                        patterns.append(pattern)
        
        # Add security patterns based on security level
        if self.config.security_level == "high":
            if "reentrancy_guard" not in patterns:
                patterns.append("reentrancy_guard")
            if "pausable" not in patterns and base in ["erc20", "erc721", "defi"]:
                patterns.append("pausable")
        
        # Add access control if not present
        if not any(p in patterns for p in ["ownable", "access_control"]):
            patterns.append("ownable")
        
        return patterns
    
    def _generate_invariants(
        self,
        contract_type: str,
        features: List[str]
    ) -> List[Invariant]:
        """Generate appropriate invariants for the contract"""
        invariants = []

        # Normalize inputs so aliased/upper-case types and features still match
        contract_type = contract_type.lower()
        features = [f.lower() for f in features]

        # Token invariants
        if contract_type in ["erc20", "token"]:
            has_cap = "capped" in features
            has_burn = "burnable" in features
            invariants.extend(
                self.symbolic_generator.generate_token_invariants(
                    "ERC20",
                    has_cap=has_cap,
                    has_burn=has_burn
                )
            )
        elif contract_type in ["erc721", "nft"]:
            invariants.extend(
                self.symbolic_generator.generate_token_invariants("ERC721")
            )
        
        # Access control invariants
        has_owner = "ownable" in features
        has_roles = "access_control" in features
        invariants.extend(
            self.symbolic_generator.generate_access_control_invariants(
                has_owner=has_owner,
                has_roles=has_roles
            )
        )
        
        # DeFi invariants
        if contract_type in ["amm", "lending", "staking", "defi"]:
            invariants.extend(
                self.symbolic_generator.generate_defi_invariants(contract_type)
            )
        
        return invariants
    
    async def _generate_llm_contract(self, contract_spec: Dict) -> str:
        """
        Generate contract using LLM (fallback or custom logic).
        
        Args:
            contract_spec: Contract specification
            
        Returns:
            LLM-generated Solidity code
        """
        # If LLM service is available, use it
        if self.llm_service:
            prompt = self._create_llm_prompt(contract_spec)
            response = await self.llm_service.generate(prompt)
            return response
        
        # Fallback: Generate basic template
        contract_name = contract_spec.get("name", "GeneratedContract")
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract {contract_name} {{
    // Custom contract implementation
    address public owner;
    
    constructor() {{
        owner = msg.sender;
    }}
    
    modifier onlyOwner() {{
        require(msg.sender == owner, "Not owner");
        _;
    }}
}}
"""
    
    async def _add_custom_logic(
        self,
        base_code: str,
        contract_spec: Dict,
        custom_logic: str
    ) -> Tuple[str, List[str]]:
        """
        Add custom LLM-generated logic to the contract.
        
        Args:
            base_code: Base contract code
            contract_spec: Contract specification
            custom_logic: Custom logic to add
            
        Returns:
            Tuple of (modified code, list of LLM sections)
        """
        llm_sections = []
        
        # Find insertion point (before last closing brace)
        last_brace = base_code.rfind("}")
        
        if last_brace == -1:
            return base_code, llm_sections
        
        # Add custom logic section
        custom_section = "\n    // ========== CUSTOM LOGIC ==========\n"
        custom_section += "    // LLM-generated custom functionality\n\n"
        
        if custom_logic:
            custom_section += "    " + custom_logic.replace("\n", "\n    ") + "\n"
            llm_sections.append("custom_logic")
        
        # Generate additional custom functions based on spec
        if "functions" in contract_spec:
            for func_spec in contract_spec["functions"]:
                func_code = await self._generate_custom_function(func_spec)
                custom_section += func_code + "\n"
                llm_sections.append(func_spec.get("name", "custom_function"))
        
        # Insert custom logic
        modified_code = (
            base_code[:last_brace] +
            custom_section +
            base_code[last_brace:]
        )
        
        return modified_code, llm_sections
    
    async def _generate_custom_function(self, func_spec: Dict) -> str:
        """Generate a custom function using LLM or template"""
        func_name = func_spec.get("name", "customFunction")
        params = func_spec.get("parameters", [])
        returns = func_spec.get("returns", "")
        visibility = func_spec.get("visibility", "public")
        
        param_str = ", ".join(params) if params else ""
        return_str = f" returns ({returns})" if returns else ""
        
        function = f"""    function {func_name}({param_str}) {visibility}{return_str} {{
        // TODO: Implement {func_name}
    }}
"""
        return function
    
    def _create_llm_prompt(self, contract_spec: Dict) -> str:
        """Create prompt for LLM contract generation"""
        prompt = "Generate a Solidity smart contract with the following specifications:\n\n"
        prompt += f"Contract Name: {contract_spec.get('name', 'Contract')}\n"
        prompt += f"Type: {contract_spec.get('type', 'custom')}\n"
        
        if "features" in contract_spec:
            prompt += f"Features: {', '.join(contract_spec['features'])}\n"
        
        if "description" in contract_spec:
            prompt += f"Description: {contract_spec['description']}\n"
        
        prompt += "\nGenerate secure, well-documented Solidity code."
        
        return prompt
    
    def _calculate_breakdown(
        self,
        code: str,
        patterns_used: List[str],
        invariants_added: List[str],
        llm_sections: List[str]
    ) -> Dict[str, float]:
        """
        Calculate the actual breakdown of code sources.
        
        Args:
            code: Generated contract code
            patterns_used: List of patterns used
            invariants_added: List of invariants added
            llm_sections: List of LLM-generated sections
            
        Returns:
            Dictionary with percentage breakdown
        """
        # Count lines of code
        lines = [line for line in code.split("\n") if line.strip() and not line.strip().startswith("//")]
        total_lines = len(lines)
        
        if total_lines == 0:
            return {"llm": 0.0, "template": 0.0, "symbolic": 0.0}
        
        # Estimate template lines (imports + inherited functionality)
        template_lines = len(patterns_used) * 10  # Rough estimate
        
        # Estimate invariant lines
        invariant_lines = len(invariants_added) * 5  # Rough estimate
        
        # Remaining lines are LLM-generated
        llm_lines = max(0, total_lines - template_lines - invariant_lines)
        
        # Calculate percentages
        template_pct = min(template_lines / total_lines, 1.0)
        symbolic_pct = min(invariant_lines / total_lines, 1.0)
        llm_pct = max(0.0, 1.0 - template_pct - symbolic_pct)
        
        return {
            "llm": round(llm_pct, 2),
            "template": round(template_pct, 2),
            "symbolic": round(symbolic_pct, 2)
        }
    
    def measure_code_diversity(
        self,
        contracts: List[GeneratedContract]
    ) -> Dict[str, float]:
        """
        Measure diversity across multiple generated contracts.
        
        Args:
            contracts: List of generated contracts
            
        Returns:
            Diversity metrics
        """
        if not contracts:
            return {"diversity_score": 0.0}
        
        # Measure pattern diversity
        all_patterns = set()
        for contract in contracts:
            all_patterns.update(contract.patterns_used)
        
        pattern_diversity = len(all_patterns) / max(len(contracts), 1)
        
        # Measure generation strategy diversity
        strategies = set(c.composition_method for c in contracts)
        strategy_diversity = len(strategies) / max(len(contracts), 1)
        
        # Measure code structure diversity (simplified)
        unique_structures = len(set(
            len(c.solidity_code.split("\n"))
            for c in contracts
        ))
        structure_diversity = unique_structures / max(len(contracts), 1)
        
        # Overall diversity score
        diversity_score = (
            pattern_diversity * 0.4 +
            strategy_diversity * 0.3 +
            structure_diversity * 0.3
        )
        
        return {
            "diversity_score": round(diversity_score, 3),
            "pattern_diversity": round(pattern_diversity, 3),
            "strategy_diversity": round(strategy_diversity, 3),
            "structure_diversity": round(structure_diversity, 3),
            "unique_patterns": len(all_patterns),
            "unique_strategies": len(strategies)
        }
    
    def get_generation_report(
        self,
        contract: GeneratedContract
    ) -> str:
        """
        Generate a report on the heterogeneous generation.
        
        Args:
            contract: Generated contract
            
        Returns:
            Markdown report
        """
        report = f"# Heterogeneous Generation Report: {contract.name}\n\n"
        
        report += "## Generation Breakdown\n\n"
        report += f"- **LLM-Generated:** {contract.generation_breakdown['llm']*100:.1f}%\n"
        report += f"- **Template-Based:** {contract.generation_breakdown['template']*100:.1f}%\n"
        report += f"- **Symbolic Invariants:** {contract.generation_breakdown['symbolic']*100:.1f}%\n\n"
        
        report += f"**Composition Method:** {contract.composition_method}\n\n"
        
        report += "## Patterns Used\n\n"
        if contract.patterns_used:
            for pattern in contract.patterns_used:
                report += f"- {pattern}\n"
        else:
            report += "No patterns used (pure LLM generation)\n"
        report += "\n"
        
        report += "## Invariants Added\n\n"
        if contract.invariants_added:
            for invariant in contract.invariants_added:
                report += f"- {invariant}\n"
        else:
            report += "No invariants added\n"
        report += "\n"
        
        report += "## Security Properties\n\n"
        if contract.security_properties:
            for prop in contract.security_properties:
                report += f"- {prop}\n"
        else:
            report += "No specific security properties identified\n"
        report += "\n"
        
        report += "## LLM-Generated Sections\n\n"
        if contract.llm_sections:
            for section in contract.llm_sections:
                report += f"- {section}\n"
        else:
            report += "No custom LLM sections\n"
        
        return report
