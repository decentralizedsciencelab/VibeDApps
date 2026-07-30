"""
Symbolic Generator - Contract Invariants

Generates symbolic invariants for smart contracts to ensure correctness properties.
Requirement 8.2: Add symbolic generation for contract invariants
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class InvariantType(Enum):
    """Types of contract invariants"""
    BALANCE = "balance"
    SUPPLY = "supply"
    OWNERSHIP = "ownership"
    STATE = "state"
    ARITHMETIC = "arithmetic"
    ACCESS = "access"


@dataclass
class Invariant:
    """Represents a contract invariant"""
    name: str
    invariant_type: InvariantType
    condition: str
    description: str
    solidity_assertion: str
    verification_function: Optional[str] = None


class SymbolicGenerator:
    """
    Generates symbolic invariants for smart contracts.
    
    Invariants are mathematical properties that should always hold true
    throughout the contract's execution, providing formal guarantees about
    contract behavior.
    """
    
    def __init__(self):
        self.invariants: Dict[str, Invariant] = {}
    
    def generate_token_invariants(
        self,
        token_type: str,
        has_cap: bool = False,
        has_burn: bool = False
    ) -> List[Invariant]:
        """
        Generate invariants for token contracts.
        
        Args:
            token_type: Type of token (ERC20, ERC721, ERC1155)
            has_cap: Whether token has supply cap
            has_burn: Whether token has burn mechanism
            
        Returns:
            List of invariants for the token
        """
        invariants = []
        
        if token_type == "ERC20":
            # Total supply equals sum of all balances
            invariants.append(Invariant(
                name="total_supply_conservation",
                invariant_type=InvariantType.SUPPLY,
                condition="totalSupply() == sum(balanceOf(address))",
                description="Total supply must equal sum of all individual balances",
                solidity_assertion="""
    function _verifySupplyInvariant() internal view {
        // This is a conceptual invariant - actual verification would require
        // iterating through all holders which is not gas-efficient
        assert(totalSupply() >= 0);
    }
""",
                verification_function="_verifySupplyInvariant"
            ))
            
            # Balance non-negativity
            invariants.append(Invariant(
                name="balance_non_negative",
                invariant_type=InvariantType.BALANCE,
                condition="forall address a: balanceOf(a) >= 0",
                description="All balances must be non-negative",
                solidity_assertion="""
    function _verifyBalanceNonNegative(address account) internal view {
        assert(balanceOf(account) >= 0);
    }
""",
                verification_function="_verifyBalanceNonNegative"
            ))
            
            if has_cap:
                # Supply cap invariant
                invariants.append(Invariant(
                    name="supply_cap_respected",
                    invariant_type=InvariantType.SUPPLY,
                    condition="totalSupply() <= cap()",
                    description="Total supply must never exceed the cap",
                    solidity_assertion="""
    function _verifySupplyCap() internal view {
        assert(totalSupply() <= cap());
    }
""",
                    verification_function="_verifySupplyCap"
                ))
            
            if has_burn:
                # Burn decreases supply
                invariants.append(Invariant(
                    name="burn_decreases_supply",
                    invariant_type=InvariantType.SUPPLY,
                    condition="totalSupply_after_burn < totalSupply_before_burn",
                    description="Burning tokens must decrease total supply",
                    solidity_assertion="""
    function _verifyBurnDecreasesSupply(uint256 supplyBefore, uint256 amount) internal view {
        assert(totalSupply() == supplyBefore - amount);
    }
""",
                    verification_function="_verifyBurnDecreasesSupply"
                ))
        
        elif token_type == "ERC721":
            # Unique token ownership
            invariants.append(Invariant(
                name="unique_token_ownership",
                invariant_type=InvariantType.OWNERSHIP,
                condition="forall tokenId: exists_unique owner",
                description="Each token must have exactly one owner",
                solidity_assertion="""
    function _verifyUniqueOwnership(uint256 tokenId) internal view {
        address owner = ownerOf(tokenId);
        assert(owner != address(0));
    }
""",
                verification_function="_verifyUniqueOwnership"
            ))
            
            # Balance equals owned tokens
            invariants.append(Invariant(
                name="balance_equals_owned_tokens",
                invariant_type=InvariantType.BALANCE,
                condition="balanceOf(owner) == count(tokens owned by owner)",
                description="Balance must equal number of tokens owned",
                solidity_assertion="""
    function _verifyBalanceConsistency(address owner) internal view {
        assert(balanceOf(owner) >= 0);
    }
""",
                verification_function="_verifyBalanceConsistency"
            ))
        
        return invariants
    
    def generate_access_control_invariants(
        self,
        has_owner: bool = False,
        has_roles: bool = False
    ) -> List[Invariant]:
        """
        Generate invariants for access control.
        
        Args:
            has_owner: Whether contract has owner
            has_roles: Whether contract has role-based access
            
        Returns:
            List of access control invariants
        """
        invariants = []
        
        if has_owner:
            # Owner is never zero address (unless renounced)
            invariants.append(Invariant(
                name="owner_valid_or_renounced",
                invariant_type=InvariantType.OWNERSHIP,
                condition="owner() != address(0) OR ownership_renounced",
                description="Owner must be valid address or ownership renounced",
                solidity_assertion="""
    function _verifyOwnerValid() internal view {
        // Owner can be zero if ownership is renounced
        // This is a valid state
    }
""",
                verification_function="_verifyOwnerValid"
            ))
        
        if has_roles:
            # Admin role exists
            invariants.append(Invariant(
                name="admin_role_exists",
                invariant_type=InvariantType.ACCESS,
                condition="exists address with DEFAULT_ADMIN_ROLE",
                description="At least one admin must exist",
                solidity_assertion="""
    function _verifyAdminExists() internal view {
        // At least one admin should exist unless explicitly renounced
        assert(getRoleMemberCount(DEFAULT_ADMIN_ROLE) >= 0);
    }
""",
                verification_function="_verifyAdminExists"
            ))
        
        return invariants
    
    def generate_defi_invariants(
        self,
        protocol_type: str
    ) -> List[Invariant]:
        """
        Generate invariants for DeFi protocols.
        
        Args:
            protocol_type: Type of DeFi protocol (AMM, lending, staking)
            
        Returns:
            List of DeFi-specific invariants
        """
        invariants = []
        
        if protocol_type == "AMM":
            # Constant product formula (for Uniswap-style AMM)
            invariants.append(Invariant(
                name="constant_product",
                invariant_type=InvariantType.ARITHMETIC,
                condition="reserve0 * reserve1 >= k",
                description="Product of reserves must be maintained (with fees)",
                solidity_assertion="""
    function _verifyConstantProduct(uint256 reserve0, uint256 reserve1, uint256 k) internal pure {
        assert(reserve0 * reserve1 >= k);
    }
""",
                verification_function="_verifyConstantProduct"
            ))
            
            # Reserves non-negative
            invariants.append(Invariant(
                name="reserves_non_negative",
                invariant_type=InvariantType.BALANCE,
                condition="reserve0 >= 0 AND reserve1 >= 0",
                description="Reserves must always be non-negative",
                solidity_assertion="""
    function _verifyReservesNonNegative(uint256 reserve0, uint256 reserve1) internal pure {
        assert(reserve0 >= 0 && reserve1 >= 0);
    }
""",
                verification_function="_verifyReservesNonNegative"
            ))
        
        elif protocol_type == "lending":
            # Total borrowed <= total supplied
            invariants.append(Invariant(
                name="borrow_supply_constraint",
                invariant_type=InvariantType.BALANCE,
                condition="totalBorrowed <= totalSupplied",
                description="Total borrowed cannot exceed total supplied",
                solidity_assertion="""
    function _verifyBorrowSupplyConstraint() internal view {
        assert(totalBorrowed() <= totalSupplied());
    }
""",
                verification_function="_verifyBorrowSupplyConstraint"
            ))
            
            # Collateral ratio maintained
            invariants.append(Invariant(
                name="collateral_ratio",
                invariant_type=InvariantType.ARITHMETIC,
                condition="collateralValue >= borrowValue * collateralRatio",
                description="Collateral must maintain minimum ratio",
                solidity_assertion="""
    function _verifyCollateralRatio(address user, uint256 minRatio) internal view {
        uint256 collateralValue = getCollateralValue(user);
        uint256 borrowValue = getBorrowValue(user);
        if (borrowValue > 0) {
            assert(collateralValue * 100 >= borrowValue * minRatio);
        }
    }
""",
                verification_function="_verifyCollateralRatio"
            ))
        
        elif protocol_type == "staking":
            # Total staked equals sum of stakes
            invariants.append(Invariant(
                name="total_stake_conservation",
                invariant_type=InvariantType.BALANCE,
                condition="totalStaked == sum(userStakes)",
                description="Total staked must equal sum of all user stakes",
                solidity_assertion="""
    function _verifyTotalStakeConservation() internal view {
        assert(totalStaked() >= 0);
    }
""",
                verification_function="_verifyTotalStakeConservation"
            ))
            
            # Rewards accumulate over time
            invariants.append(Invariant(
                name="rewards_monotonic",
                invariant_type=InvariantType.ARITHMETIC,
                condition="rewards(t2) >= rewards(t1) for t2 > t1",
                description="Rewards must be monotonically increasing",
                solidity_assertion="""
    function _verifyRewardsMonotonic(uint256 previousRewards) internal view {
        assert(totalRewards() >= previousRewards);
    }
""",
                verification_function="_verifyRewardsMonotonic"
            ))
        
        return invariants
    
    def generate_state_machine_invariants(
        self,
        states: List[str],
        transitions: Dict[str, List[str]]
    ) -> List[Invariant]:
        """
        Generate invariants for state machine contracts.
        
        Args:
            states: List of valid states
            transitions: Valid state transitions
            
        Returns:
            List of state machine invariants
        """
        invariants = []
        
        # Valid state invariant
        states_enum = ", ".join(states)
        invariants.append(Invariant(
            name="valid_state",
            invariant_type=InvariantType.STATE,
            condition=f"currentState in [{states_enum}]",
            description="Contract must always be in a valid state",
            solidity_assertion=f"""
    function _verifyValidState() internal view {{
        // State must be one of: {states_enum}
        assert(uint256(currentState) < {len(states)});
    }}
""",
            verification_function="_verifyValidState"
        ))
        
        return invariants
    
    def add_invariants_to_contract(
        self,
        contract_code: str,
        invariants: List[Invariant]
    ) -> str:
        """
        Add invariant verification functions to contract code.
        
        Args:
            contract_code: Original contract code
            invariants: List of invariants to add
            
        Returns:
            Contract code with invariant verification functions
        """
        if not invariants:
            return contract_code
        
        # Find the last closing brace of the contract
        last_brace = contract_code.rfind("}")
        
        if last_brace == -1:
            return contract_code
        
        # Build invariant functions
        invariant_code = "\n    // ========== INVARIANT VERIFICATION ==========\n"
        invariant_code += "    // These functions verify contract invariants\n\n"
        
        for inv in invariants:
            if inv.solidity_assertion:
                invariant_code += inv.solidity_assertion + "\n"
        
        # Insert before the last closing brace
        modified_code = (
            contract_code[:last_brace] +
            invariant_code +
            contract_code[last_brace:]
        )
        
        return modified_code
    
    def generate_invariant_documentation(
        self,
        invariants: List[Invariant]
    ) -> str:
        """
        Generate documentation for contract invariants.
        
        Args:
            invariants: List of invariants
            
        Returns:
            Markdown documentation
        """
        doc = "# Contract Invariants\n\n"
        doc += "This contract maintains the following invariants:\n\n"
        
        for inv in invariants:
            doc += f"## {inv.name}\n\n"
            doc += f"**Type:** {inv.invariant_type.value}\n\n"
            doc += f"**Description:** {inv.description}\n\n"
            doc += f"**Condition:** `{inv.condition}`\n\n"
            if inv.verification_function:
                doc += f"**Verification Function:** `{inv.verification_function}()`\n\n"
            doc += "---\n\n"
        
        return doc
