"""
Template Library - OpenZeppelin Verified Patterns

Integrates verified OpenZeppelin patterns for secure smart contract generation.
Requirement 8.1: Integrate template library with verified OpenZeppelin patterns
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class PatternCategory(Enum):
    """Categories of contract patterns"""
    ACCESS_CONTROL = "access_control"
    SECURITY = "security"
    TOKEN = "token"
    GOVERNANCE = "governance"
    UTILITY = "utility"


@dataclass
class Pattern:
    """Represents a verified contract pattern"""
    name: str
    category: PatternCategory
    solidity_code: str
    imports: List[str]
    description: str
    security_properties: List[str]
    gas_cost: Optional[int] = None


class TemplateLibrary:
    """
    Library of verified OpenZeppelin patterns for secure contract generation.
    
    This library provides access to battle-tested contract patterns that have been
    audited and verified by the OpenZeppelin team, reducing vulnerability homogeneity.
    """
    
    def __init__(self):
        self.patterns: Dict[str, Pattern] = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self) -> None:
        """Initialize the library with OpenZeppelin patterns"""
        
        # Access Control Patterns
        self.patterns["ownable"] = Pattern(
            name="ownable",
            category=PatternCategory.ACCESS_CONTROL,
            solidity_code="""
import "@openzeppelin/contracts/access/Ownable.sol";

contract {CONTRACT_NAME} is Ownable {
    constructor() Ownable(msg.sender) {}
    
    // Owner-only functions can be added here
}
""",
            imports=["@openzeppelin/contracts/access/Ownable.sol"],
            description="Basic access control with single owner",
            security_properties=["single_owner", "ownership_transfer", "renounce_ownership"]
        )
        
        self.patterns["access_control"] = Pattern(
            name="access_control",
            category=PatternCategory.ACCESS_CONTROL,
            solidity_code="""
import "@openzeppelin/contracts/access/AccessControl.sol";

contract {CONTRACT_NAME} is AccessControl {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
}
""",
            imports=["@openzeppelin/contracts/access/AccessControl.sol"],
            description="Role-based access control",
            security_properties=["role_based_access", "hierarchical_roles", "role_admin"]
        )
        
        # Security Patterns
        self.patterns["reentrancy_guard"] = Pattern(
            name="reentrancy_guard",
            category=PatternCategory.SECURITY,
            solidity_code="""
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract {CONTRACT_NAME} is ReentrancyGuard {
    // Use nonReentrant modifier on functions that make external calls
}
""",
            imports=["@openzeppelin/contracts/utils/ReentrancyGuard.sol"],
            description="Protection against reentrancy attacks",
            security_properties=["reentrancy_protection", "mutex_lock"]
        )
        
        self.patterns["pausable"] = Pattern(
            name="pausable",
            category=PatternCategory.SECURITY,
            solidity_code="""
import "@openzeppelin/contracts/utils/Pausable.sol";

contract {CONTRACT_NAME} is Pausable {
    function pause() public {
        _pause();
    }
    
    function unpause() public {
        _unpause();
    }
}
""",
            imports=["@openzeppelin/contracts/utils/Pausable.sol"],
            description="Emergency stop mechanism",
            security_properties=["emergency_stop", "pausable_operations"]
        )
        
        # Token Patterns
        self.patterns["erc20"] = Pattern(
            name="erc20",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract {CONTRACT_NAME} is ERC20 {
    constructor(string memory name, string memory symbol) ERC20(name, symbol) {
        _mint(msg.sender, {INITIAL_SUPPLY});
    }
}
""",
            imports=["@openzeppelin/contracts/token/ERC20/ERC20.sol"],
            description="Standard ERC20 token implementation",
            security_properties=["overflow_protection", "standard_compliance"],
            gas_cost=50000
        )
        
        self.patterns["erc20_burnable"] = Pattern(
            name="erc20_burnable",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";

contract {CONTRACT_NAME} is ERC20, ERC20Burnable {
    constructor(string memory name, string memory symbol) ERC20(name, symbol) {
        _mint(msg.sender, {INITIAL_SUPPLY});
    }
}
""",
            imports=[
                "@openzeppelin/contracts/token/ERC20/ERC20.sol",
                "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol"
            ],
            description="ERC20 token with burn capability",
            security_properties=["overflow_protection", "standard_compliance", "burn_mechanism"]
        )
        
        self.patterns["erc20_capped"] = Pattern(
            name="erc20_capped",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Capped.sol";

contract {CONTRACT_NAME} is ERC20, ERC20Capped {
    constructor(
        string memory name,
        string memory symbol,
        uint256 cap
    ) ERC20(name, symbol) ERC20Capped(cap) {
        _mint(msg.sender, {INITIAL_SUPPLY});
    }
    
    function _update(address from, address to, uint256 value) internal virtual override(ERC20, ERC20Capped) {
        super._update(from, to, value);
    }
}
""",
            imports=[
                "@openzeppelin/contracts/token/ERC20/ERC20.sol",
                "@openzeppelin/contracts/token/ERC20/extensions/ERC20Capped.sol"
            ],
            description="ERC20 token with supply cap",
            security_properties=["overflow_protection", "standard_compliance", "supply_cap"]
        )
        
        self.patterns["erc721"] = Pattern(
            name="erc721",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

contract {CONTRACT_NAME} is ERC721 {
    uint256 private _tokenIdCounter;
    
    constructor(string memory name, string memory symbol) ERC721(name, symbol) {}
    
    function mint(address to) public returns (uint256) {
        uint256 tokenId = _tokenIdCounter++;
        _safeMint(to, tokenId);
        return tokenId;
    }
}
""",
            imports=["@openzeppelin/contracts/token/ERC721/ERC721.sol"],
            description="Standard ERC721 NFT implementation",
            security_properties=["overflow_protection", "standard_compliance", "safe_transfer"],
            gas_cost=80000
        )
        
        self.patterns["erc721_enumerable"] = Pattern(
            name="erc721_enumerable",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";

contract {CONTRACT_NAME} is ERC721, ERC721Enumerable {
    uint256 private _tokenIdCounter;
    
    constructor(string memory name, string memory symbol) ERC721(name, symbol) {}
    
    function mint(address to) public returns (uint256) {
        uint256 tokenId = _tokenIdCounter++;
        _safeMint(to, tokenId);
        return tokenId;
    }
    
    function _update(address to, uint256 tokenId, address auth) internal virtual override(ERC721, ERC721Enumerable) returns (address) {
        return super._update(to, tokenId, auth);
    }
    
    function _increaseBalance(address account, uint128 value) internal virtual override(ERC721, ERC721Enumerable) {
        super._increaseBalance(account, value);
    }
    
    function supportsInterface(bytes4 interfaceId) public view virtual override(ERC721, ERC721Enumerable) returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}
""",
            imports=[
                "@openzeppelin/contracts/token/ERC721/ERC721.sol",
                "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol"
            ],
            description="ERC721 with enumeration support",
            security_properties=["overflow_protection", "standard_compliance", "safe_transfer", "enumeration"]
        )
        
        self.patterns["erc1155"] = Pattern(
            name="erc1155",
            category=PatternCategory.TOKEN,
            solidity_code="""
import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";

contract {CONTRACT_NAME} is ERC1155 {
    constructor(string memory uri) ERC1155(uri) {}
    
    function mint(address to, uint256 id, uint256 amount, bytes memory data) public {
        _mint(to, id, amount, data);
    }
    
    function mintBatch(address to, uint256[] memory ids, uint256[] memory amounts, bytes memory data) public {
        _mintBatch(to, ids, amounts, data);
    }
}
""",
            imports=["@openzeppelin/contracts/token/ERC1155/ERC1155.sol"],
            description="Multi-token standard implementation",
            security_properties=["overflow_protection", "standard_compliance", "batch_operations"]
        )
    
    def get_pattern(self, pattern_name: str) -> Optional[Pattern]:
        """
        Retrieve a pattern by name.
        
        Args:
            pattern_name: Name of the pattern to retrieve
            
        Returns:
            Pattern object if found, None otherwise
        """
        return self.patterns.get(pattern_name)
    
    def list_patterns(self, category: Optional[PatternCategory] = None) -> List[Pattern]:
        """
        List all patterns, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of patterns matching the criteria
        """
        if category is None:
            return list(self.patterns.values())
        
        return [p for p in self.patterns.values() if p.category == category]
    
    def get_patterns_by_security_property(self, property_name: str) -> List[Pattern]:
        """
        Find patterns that provide a specific security property.
        
        Args:
            property_name: Security property to search for
            
        Returns:
            List of patterns with the specified security property
        """
        return [
            p for p in self.patterns.values()
            if property_name in p.security_properties
        ]
    
    def get_pattern_names(self) -> List[str]:
        """Get list of all available pattern names"""
        return list(self.patterns.keys())
    
    def add_custom_pattern(self, pattern: Pattern) -> None:
        """
        Add a custom pattern to the library.
        
        Args:
            pattern: Pattern object to add
        """
        self.patterns[pattern.name] = pattern
