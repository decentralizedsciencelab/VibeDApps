"""
Pattern Composer - Combining Verified Components

Composes multiple verified patterns into cohesive contracts.
Requirement 8.3: Implement pattern composition engine for combining components
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .template_library import Pattern, TemplateLibrary


@dataclass
class ComposedContract:
    """Represents a contract composed from multiple patterns"""
    name: str
    base_patterns: List[Pattern]
    solidity_code: str
    imports: Set[str]
    inherited_contracts: List[str]
    security_properties: Set[str]
    composition_strategy: str


class PatternComposer:
    """
    Composes multiple verified patterns into cohesive smart contracts.
    
    This engine combines OpenZeppelin patterns intelligently, handling
    inheritance conflicts, function overrides, and ensuring all security
    properties are maintained.
    """
    
    def __init__(self, template_library: TemplateLibrary):
        self.template_library = template_library
    
    def compose_contract(
        self,
        contract_name: str,
        pattern_names: List[str],
        custom_functions: Optional[str] = None
    ) -> ComposedContract:
        """
        Compose a contract from multiple patterns.
        
        Args:
            contract_name: Name for the composed contract
            pattern_names: List of pattern names to compose
            custom_functions: Optional custom function implementations
            
        Returns:
            ComposedContract with combined patterns
        """
        # Retrieve patterns
        patterns = []
        for name in pattern_names:
            pattern = self.template_library.get_pattern(name)
            if pattern:
                patterns.append(pattern)
        
        if not patterns:
            raise ValueError("No valid patterns provided")
        
        # Collect all imports
        imports = set()
        for pattern in patterns:
            imports.update(pattern.imports)
        
        # Collect all security properties
        security_properties = set()
        for pattern in patterns:
            security_properties.update(pattern.security_properties)
        
        # Determine inheritance order and contracts
        inherited_contracts = self._determine_inheritance_order(patterns)
        
        # Generate composed contract code
        solidity_code = self._generate_composed_code(
            contract_name,
            patterns,
            inherited_contracts,
            imports,
            custom_functions
        )
        
        return ComposedContract(
            name=contract_name,
            base_patterns=patterns,
            solidity_code=solidity_code,
            imports=imports,
            inherited_contracts=inherited_contracts,
            security_properties=security_properties,
            composition_strategy="multiple_inheritance"
        )
    
    def _determine_inheritance_order(self, patterns: List[Pattern]) -> List[str]:
        """
        Determine the correct inheritance order for patterns.
        
        Follows Solidity's C3 linearization rules for multiple inheritance.
        
        Args:
            patterns: List of patterns to compose
            
        Returns:
            Ordered list of contract names to inherit
        """
        inherited = []
        
        # Map pattern names to OpenZeppelin contract names
        pattern_to_contract = {
            "ownable": "Ownable",
            "access_control": "AccessControl",
            "reentrancy_guard": "ReentrancyGuard",
            "pausable": "Pausable",
            "erc20": "ERC20",
            "erc20_burnable": "ERC20Burnable",
            "erc20_capped": "ERC20Capped",
            "erc721": "ERC721",
            "erc721_enumerable": "ERC721Enumerable",
            "erc1155": "ERC1155"
        }
        
        # Priority order for common patterns (base classes first)
        priority_order = [
            "ERC20", "ERC721", "ERC1155",  # Token standards first
            "Ownable", "AccessControl",     # Access control
            "Pausable", "ReentrancyGuard",  # Security features
            "ERC20Burnable", "ERC20Capped", "ERC721Enumerable"  # Extensions last
        ]
        
        # Collect contract names
        contract_names = [
            pattern_to_contract.get(p.name, p.name)
            for p in patterns
        ]
        
        # Sort by priority
        for priority_contract in priority_order:
            if priority_contract in contract_names:
                inherited.append(priority_contract)
        
        # Add any remaining contracts not in priority list
        for contract in contract_names:
            if contract not in inherited:
                inherited.append(contract)
        
        return inherited
    
    def _generate_composed_code(
        self,
        contract_name: str,
        patterns: List[Pattern],
        inherited_contracts: List[str],
        imports: Set[str],
        custom_functions: Optional[str]
    ) -> str:
        """
        Generate the Solidity code for the composed contract.
        
        Args:
            contract_name: Name of the contract
            patterns: List of patterns being composed
            inherited_contracts: Ordered list of contracts to inherit
            imports: Set of import statements
            custom_functions: Optional custom functions
            
        Returns:
            Complete Solidity contract code
        """
        code = "// SPDX-License-Identifier: MIT\n"
        code += "pragma solidity ^0.8.20;\n\n"
        
        # Add imports
        for import_stmt in sorted(imports):
            code += f'import "{import_stmt}";\n'
        code += "\n"
        
        # Contract declaration with inheritance
        inheritance = ", ".join(inherited_contracts)
        code += f"contract {contract_name} is {inheritance} {{\n"
        
        # Add constructor
        code += self._generate_constructor(patterns, inherited_contracts)
        
        # Add function overrides if needed
        code += self._generate_overrides(patterns, inherited_contracts)
        
        # Add custom functions if provided
        if custom_functions:
            code += "\n    // ========== CUSTOM FUNCTIONS ==========\n\n"
            code += custom_functions
            code += "\n"
        
        code += "}\n"
        
        return code
    
    def _generate_constructor(
        self,
        patterns: List[Pattern],
        inherited_contracts: List[str]
    ) -> str:
        """Generate constructor with proper initialization"""
        constructor = "    constructor("
        
        # Determine constructor parameters based on patterns
        params = []
        initializers = []
        
        if "ERC20" in inherited_contracts:
            params.append("string memory name")
            params.append("string memory symbol")
            initializers.append("ERC20(name, symbol)")
        
        if "ERC721" in inherited_contracts:
            params.append("string memory name")
            params.append("string memory symbol")
            initializers.append("ERC721(name, symbol)")
        
        if "ERC1155" in inherited_contracts:
            params.append("string memory uri")
            initializers.append("ERC1155(uri)")
        
        if "Ownable" in inherited_contracts:
            initializers.append("Ownable(msg.sender)")
        
        if "ERC20Capped" in inherited_contracts:
            params.append("uint256 cap")
            initializers.append("ERC20Capped(cap)")
        
        constructor += ", ".join(params) + ")"
        
        if initializers:
            constructor += " " + " ".join(initializers)
        
        constructor += " {\n"
        
        # Add initial minting for tokens if applicable.
        # Skip the fixed 1,000,000 premint when the token is capped: the cap is
        # a runtime constructor argument, so a fixed premint reverts on deploy
        # whenever cap < 1,000,000. Capped tokens are minted within the cap later.
        if "ERC20" in inherited_contracts and "ERC20Capped" not in inherited_contracts:
            constructor += "        _mint(msg.sender, 1000000 * 10 ** decimals());\n"
        
        # Grant roles if AccessControl is used
        if "AccessControl" in inherited_contracts:
            constructor += "        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);\n"
        
        constructor += "    }\n\n"
        
        return constructor
    
    def _generate_overrides(
        self,
        patterns: List[Pattern],
        inherited_contracts: List[str]
    ) -> str:
        """
        Generate function overrides for multiple inheritance conflicts.
        
        Args:
            patterns: List of patterns
            inherited_contracts: List of inherited contracts
            
        Returns:
            Override function implementations
        """
        overrides = ""
        
        # Handle ERC20 + ERC20Capped override
        if "ERC20" in inherited_contracts and "ERC20Capped" in inherited_contracts:
            overrides += """    function _update(address from, address to, uint256 value)
        internal
        virtual
        override(ERC20, ERC20Capped)
    {
        super._update(from, to, value);
    }

"""
        
        # Handle ERC721 + ERC721Enumerable overrides
        if "ERC721" in inherited_contracts and "ERC721Enumerable" in inherited_contracts:
            overrides += """    function _update(address to, uint256 tokenId, address auth)
        internal
        virtual
        override(ERC721, ERC721Enumerable)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _increaseBalance(address account, uint128 value)
        internal
        virtual
        override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        virtual
        override(ERC721, ERC721Enumerable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

"""

        # Emit pause()/unpause() when Pausable is inherited. Without these the
        # contract advertises Pausable but can never actually be paused (the
        # inherited _pause/_unpause are internal). Gate them by whatever access
        # control the composition provides.
        if "Pausable" in inherited_contracts:
            if "Ownable" in inherited_contracts:
                guard = " onlyOwner"
            elif "AccessControl" in inherited_contracts:
                guard = " onlyRole(DEFAULT_ADMIN_ROLE)"
            else:
                guard = ""
            overrides += f"""    function pause() public{guard} {{
        _pause();
    }}

    function unpause() public{guard} {{
        _unpause();
    }}

"""

        return overrides
    
    def compose_token_with_features(
        self,
        contract_name: str,
        token_standard: str,
        features: List[str]
    ) -> ComposedContract:
        """
        Compose a token contract with specific features.
        
        Args:
            contract_name: Name of the token contract
            token_standard: Base token standard (erc20, erc721, erc1155)
            features: List of features (burnable, pausable, capped, etc.)
            
        Returns:
            Composed token contract
        """
        pattern_names = [token_standard]
        
        # Map features to patterns
        feature_map = {
            "burnable": f"{token_standard}_burnable",
            "capped": f"{token_standard}_capped",
            "enumerable": f"{token_standard}_enumerable",
            "pausable": "pausable",
            "ownable": "ownable",
            "access_control": "access_control",
            "reentrancy_guard": "reentrancy_guard"
        }
        
        for feature in features:
            if feature in feature_map:
                pattern_name = feature_map[feature]
                # Check if pattern exists
                if self.template_library.get_pattern(pattern_name):
                    pattern_names.append(pattern_name)
                elif feature in ["pausable", "ownable", "access_control", "reentrancy_guard"]:
                    pattern_names.append(feature)
        
        return self.compose_contract(contract_name, pattern_names)
    
    def validate_composition(
        self,
        patterns: List[Pattern]
    ) -> Dict[str, List[str]]:
        """
        Validate that patterns can be composed together.
        
        Args:
            patterns: List of patterns to validate
            
        Returns:
            Dictionary with validation results and any conflicts
        """
        results = {
            "valid": [],
            "conflicts": [],
            "warnings": []
        }
        
        pattern_names = [p.name for p in patterns]
        
        # Check for conflicting access control patterns
        if "ownable" in pattern_names and "access_control" in pattern_names:
            results["conflicts"].append(
                "Cannot use both Ownable and AccessControl - choose one"
            )
        
        # Check for token standard conflicts
        token_standards = ["erc20", "erc721", "erc1155"]
        token_count = sum(1 for p in pattern_names if p in token_standards)
        if token_count > 1:
            results["conflicts"].append(
                "Cannot inherit from multiple token standards"
            )
        
        # Check for extension without base
        if "erc20_burnable" in pattern_names and "erc20" not in pattern_names:
            results["warnings"].append(
                "ERC20Burnable requires ERC20 base - will be added automatically"
            )
        
        if not results["conflicts"]:
            results["valid"].append("Composition is valid")
        
        return results
