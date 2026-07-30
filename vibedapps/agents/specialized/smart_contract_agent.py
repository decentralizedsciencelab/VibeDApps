import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore
from vibedapps.orchestration.generation_context import DAppGenerationContext
from vibedapps.tools.adapters.hardhat import HardhatAdapter
from vibedapps.tools.adapters.openzeppelin import OpenZeppelinAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class SmartContractAgent(BaseAgent):
    """Agent specialized for generating smart contract code."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None,
            tool_registry: Optional[ToolRegistry] = None,
            tool_executor: Optional[ToolExecutor] = None
    ):
        # Default config if not provided
        if not config:
            config = AgentConfig(
                name="Smart Contract Generator",
                description="Generates secure and efficient smart contract code based on specifications",
                capabilities=["erc20", "erc721", "erc1155", "dao", "defi", "marketplace", "custom"],
                model="gpt-4o",
                temperature=0.2,  # Lower temperature for more deterministic code generation
                system_prompt=(
                    "You are a specialized agent for generating smart contract code. "
                    "You excel at writing secure, gas-efficient, and well-documented Solidity code. "
                    "Your task is to generate smart contracts based on user specifications, "
                    "following best practices and security standards."
                )
            )

        super().__init__(config, memory_store or InMemoryStore(), llm_service)

        # Tool support for tool-based generation
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor or ToolExecutor()
        self.logger = logger.bind(agent_id=self.id, agent_name=self.config.name)

        # Register specialized endpoints
        self._register_specialized_endpoints()

        # Contract templates
        self.contract_templates = {
            "erc20": self._get_erc20_template,
            "erc721": self._get_erc721_template,
            "erc1155": self._get_erc1155_template,
            "dao": self._get_dao_template,
            "defi": self._get_defi_template,
            "marketplace": self._get_marketplace_template,
            "custom": self._get_custom_template,
        }

    def _register_specialized_endpoints(self):
        """Register specialized endpoints for this agent."""
        router = APIRouter()

        @router.post("/generate")
        async def generate_contract(specifications: Dict[str, Any]):
            """Generate smart contract code based on specifications."""
            return await self.specialized_capability(specifications=specifications)

        @router.post("/validate")
        async def validate_contract(contract_code: str):
            """Validate smart contract code."""
            return await self.validate_contract(contract_code)

        # Add the router to the app
        self.app.include_router(router, prefix="/api/smart-contract")

    async def specialized_capability(self, **kwargs) -> Any:
        """
        Generate smart contract code based on specifications.

        Supports multiple generation strategies:
        - LLM_ONLY: Pure LLM-based generation (default/fallback)
        - TOOL_BASED: Use Hardhat + OpenZeppelin tools
        - HYBRID: Combine tool scaffolding with LLM customization
        """
        specifications = kwargs.get("specifications", {})
        context = kwargs.get("context")  # Optional DAppGenerationContext
        user_strategy = kwargs.get("strategy")  # Optional user-specified strategy

        if not specifications:
            raise HTTPException(status_code=400, detail="No specifications provided")

        # Extract contract details
        contract_type = specifications.get("contractType", "custom")
        contract_features = specifications.get("contractFeatures", {})
        project_name = specifications.get("projectName", "MyToken")
        project_description = specifications.get("projectDescription", "")

        # Determine generation strategy
        strategy = "llm_only"  # Default fallback
        strategy_reasoning = "LLM-only generation (default)"

        if self.tool_registry and not user_strategy:
            # Use strategy orchestrator to recommend best strategy
            from vibedapps.orchestration.generation_strategy import GenerationStrategyOrchestrator

            orchestrator = GenerationStrategyOrchestrator(self.tool_registry)
            recommendation = orchestrator.recommend_strategy(
                contract_type=contract_type,
                contract_features=contract_features,
                project_description=project_description,
                user_preference=None,
                security_priority=specifications.get("securityChecks", {}).get("enabled", False)
            )

            strategy = recommendation.strategy.value
            strategy_reasoning = recommendation.reasoning

            self.logger.info(
                "strategy_selected",
                strategy=strategy,
                confidence=recommendation.confidence,
                reasoning=strategy_reasoning
            )
        elif user_strategy:
            # Use user-specified strategy
            strategy = user_strategy
            strategy_reasoning = f"User-specified strategy: {user_strategy}"

        # Set strategy in context if available
        if context:
            context.set_generation_strategy(strategy, strategy_reasoning)

        # Execute generation based on strategy
        try:
            if strategy == "tool_based" and self.tool_registry:
                # Use tool-based generation
                result = await self._generate_with_tool_based_strategy(
                    specifications, context
                )
            elif strategy == "hybrid" and self.tool_registry:
                # Use hybrid generation
                result = await self._generate_with_hybrid_strategy(
                    specifications, context
                )
            else:
                # Use LLM-only generation
                result = await self._generate_with_llm_only_strategy(
                    specifications, context
                )

            # Store the generated contract in memory
            await self.memory.store_knowledge(
                self.id, f"contract_{project_name}", result.get("contract_code", "")
            )

            return result

        except Exception as e:
            self.logger.error("generation_failed", error=str(e), strategy=strategy)

            # Attempt fallback if tool-based strategy failed
            if strategy in ["tool_based", "hybrid"]:
                self.logger.warning("falling_back_to_llm", reason=str(e))
                if context:
                    context.record_fallback(f"Tool-based generation failed: {str(e)}")

                # Retry with LLM-only
                result = await self._generate_with_llm_only_strategy(
                    specifications, context
                )

                await self.memory.store_knowledge(
                    self.id, f"contract_{project_name}", result.get("contract_code", "")
                )

                return result
            else:
                # No fallback available
                raise

    async def validate_contract(self, contract_code: str) -> Dict[str, Any]:
        """Validate smart contract code for security issues."""
        validation_prompt = (
            "Audit the following Solidity smart contract code for security vulnerabilities "
            "and code quality issues. Focus on:\n"
            "1. Reentrancy vulnerabilities\n"
            "2. Integer overflow/underflow\n"
            "3. Gas optimization\n"
            "4. Best practices compliance\n"
            "5. Logic errors\n\n"
            f"Contract code:\n\n{contract_code}\n\n"
            "Provide a detailed report of any issues found and suggest fixes."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": validation_prompt}
        ]

        validation_result = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=0.2  # Lower temperature for more deterministic validation
        )

        return {
            "validation_result": validation_result,
            "is_valid": "no vulnerabilities" in validation_result.lower(),
        }

    def _get_erc20_template(self, token_name: str) -> str:
        """Get a basic ERC20 token template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title {token_name}
 * @dev Implementation of the {token_name} ERC20 token
 */
contract {token_name} is ERC20, Ownable {{
    // Add token features here

    /**
     * @dev Constructor that gives msg.sender all of existing tokens.
     */
    constructor(uint256 initialSupply) ERC20("{token_name}", "{token_name[0:3]}") Ownable(msg.sender) {{
        _mint(msg.sender, initialSupply * 10 ** decimals());
    }}

    // Add custom functions here
}}"""

    def _get_erc721_template(self, token_name: str) -> str:
        """Get a basic ERC721 NFT template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title {token_name}
 * @dev Implementation of the {token_name} NFT collection
 */
contract {token_name} is ERC721Enumerable, Ownable {{
    using Strings for uint256;
    
    string private _baseTokenURI;
    uint256 private _price = 0.05 ether;
    uint256 private _maxSupply = 10000;
    
    /**
     * @dev Constructor 
     */
    constructor() ERC721("{token_name}", "{token_name[0:3]}") Ownable(msg.sender) {{
        _baseTokenURI = "";
    }}
    
    /**
     * @dev Base URI for computing {{tokenURI}}.
     */
    function _baseURI() internal view override returns (string memory) {{
        return _baseTokenURI;
    }}
    
    /**
     * @dev Sets the base URI for all token IDs.
     */
    function setBaseURI(string memory baseURI) external onlyOwner {{
        _baseTokenURI = baseURI;
    }}
    
    /**
     * @dev Mints a new token.
     */
    function mint() external payable {{
        require(totalSupply() < _maxSupply, "Max supply reached");
        require(msg.value >= _price, "Insufficient payment");
        
        _mint(msg.sender, totalSupply());
    }}
    
    /**
     * @dev Allows the owner to withdraw the contract balance.
     */
    function withdraw() external onlyOwner {{
        (bool success, ) = payable(owner()).call{{value: address(this).balance}}("");
        require(success, "Withdrawal failed");
    }}
}}"""

    def _get_erc1155_template(self, token_name: str) -> str:
        """Get a basic ERC1155 Multi-Token template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title {token_name}
 * @dev Implementation of the {token_name} multi-token collection
 */
contract {token_name} is ERC1155, Ownable {{
    // Token type IDs
    uint256 public constant GOLD = 0;
    uint256 public constant SILVER = 1;
    uint256 public constant BRONZE = 2;
    
    // Token URIs
    mapping(uint256 => string) private _tokenURIs;
    
    /**
     * @dev Constructor 
     */
    constructor() ERC1155("") Ownable(msg.sender) {{
        // Mint some initial tokens to the owner
        _mint(msg.sender, GOLD, 100, "");
        _mint(msg.sender, SILVER, 1000, "");
        _mint(msg.sender, BRONZE, 10000, "");
    }}
    
    /**
     * @dev Sets the URI for a token type.
     */
    function setURI(uint256 tokenId, string memory tokenURI) external onlyOwner {{
        _tokenURIs[tokenId] = tokenURI;
        emit URI(tokenURI, tokenId);
    }}
    
    /**
     * @dev Returns the URI for a given token ID.
     */
    function uri(uint256 tokenId) public view override returns (string memory) {{
        return _tokenURIs[tokenId];
    }}
    
    /**
     * @dev Mints new tokens.
     */
    function mint(address to, uint256 id, uint256 amount) external onlyOwner {{
        _mint(to, id, amount, "");
    }}
    
    /**
     * @dev Batch mints new tokens.
     */
    function mintBatch(address to, uint256[] memory ids, uint256[] memory amounts) external onlyOwner {{
        _mintBatch(to, ids, amounts, "");
    }}
}}"""

    def _get_dao_template(self, dao_name: str) -> str:
        """Get a basic DAO governance template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorTimelockControl.sol";

/**
 * @title {dao_name}
 * @dev Implementation of the {dao_name} DAO governance system
 */
contract {dao_name}Governor is Governor, GovernorSettings, GovernorCountingSimple, GovernorVotes, GovernorVotesQuorumFraction, GovernorTimelockControl {{
    constructor(IVotes _token, TimelockController _timelock)
        Governor("{dao_name}")
        GovernorSettings(1 /* 1 block */, 50400 /* 1 week */, 0)
        GovernorVotes(_token)
        GovernorVotesQuorumFraction(4)
        GovernorTimelockControl(_timelock)
    {{}}

    // The following functions are overrides required by Solidity.

    function votingDelay()
        public
        view
        override(IGovernor, GovernorSettings)
        returns (uint256)
    {{
        return super.votingDelay();
    }}

    function votingPeriod()
        public
        view
        override(IGovernor, GovernorSettings)
        returns (uint256)
    {{
        return super.votingPeriod();
    }}

    function quorum(uint256 blockNumber)
        public
        view
        override(IGovernor, GovernorVotesQuorumFraction)
        returns (uint256)
    {{
        return super.quorum(blockNumber);
    }}

    function state(uint256 proposalId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (ProposalState)
    {{
        return super.state(proposalId);
    }}

    function propose(address[] memory targets, uint256[] memory values, bytes[] memory calldatas, string memory description)
        public
        override(Governor, IGovernor)
        returns (uint256)
    {{
        return super.propose(targets, values, calldatas, description);
    }}

    function _execute(uint256 proposalId, address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash)
        internal
        override(Governor, GovernorTimelockControl)
    {{
        super._execute(proposalId, targets, values, calldatas, descriptionHash);
    }}

    function _cancel(address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash)
        internal
        override(Governor, GovernorTimelockControl)
        returns (uint256)
    {{
        return super._cancel(targets, values, calldatas, descriptionHash);
    }}

    function _executor()
        internal
        view
        override(Governor, GovernorTimelockControl)
        returns (address)
    {{
        return super._executor();
    }}

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (bool)
    {{
        return super.supportsInterface(interfaceId);
    }}
}}"""

    def _get_defi_template(self, protocol_name: str) -> str:
        """Get a basic DeFi protocol template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title {protocol_name}
 * @dev Implementation of a simple DeFi protocol for staking and rewards
 */
contract {protocol_name} is Ownable, ReentrancyGuard {{
    using SafeERC20 for IERC20;

    // The token being staked
    IERC20 public immutable stakingToken;
    
    // The token being paid as rewards
    IERC20 public immutable rewardsToken;
    
    // Duration of rewards to be paid out (in seconds)
    uint256 public duration = 7 days;
    
    // Timestamp of when the rewards finish
    uint256 public finishAt;
    
    // Minimum of last updated time and reward finish time
    uint256 public updatedAt;
    
    // Reward to be paid out per second
    uint256 public rewardRate;
    
    // Sum of (reward rate * dt * 1e18 / total supply)
    uint256 public rewardPerTokenStored;
    
    // User address => rewardPerTokenStored
    mapping(address => uint256) public userRewardPerTokenPaid;
    
    // User address => rewards to be claimed
    mapping(address => uint256) public rewards;
    
    // Total staked
    uint256 public totalSupply;
    
    // User address => staked amount
    mapping(address => uint256) public balanceOf;

    /**
     * @dev Constructor 
     */
    constructor(address _stakingToken, address _rewardsToken) Ownable(msg.sender) {{
        stakingToken = IERC20(_stakingToken);
        rewardsToken = IERC20(_rewardsToken);
    }}
    
    /**
     * @dev Sets the reward rate for the staking contract
     */
    function setRewardsDuration(uint256 _duration) external onlyOwner {{
        require(finishAt < block.timestamp, "Reward duration not finished");
        duration = _duration;
    }}
    
    /**
     * @dev Adds reward to be distributed over the duration
     */
    function notifyRewardAmount(uint256 amount) external onlyOwner {{
        _updateReward(address(0));
        
        if (block.timestamp >= finishAt) {{
            rewardRate = amount / duration;
        }} else {{
            uint256 remainingRewards = (finishAt - block.timestamp) * rewardRate;
            rewardRate = (amount + remainingRewards) / duration;
        }}
        
        require(rewardRate > 0, "Reward rate = 0");
        require(
            rewardRate * duration <= rewardsToken.balanceOf(address(this)),
            "Reward amount > balance"
        );
        
        finishAt = block.timestamp + duration;
        updatedAt = block.timestamp;
    }}
    
    /**
     * @dev Stake tokens to the contract
     */
    function stake(uint256 amount) external nonReentrant {{
        require(amount > 0, "Amount = 0");
        
        _updateReward(msg.sender);
        
        stakingToken.safeTransferFrom(msg.sender, address(this), amount);
        
        balanceOf[msg.sender] += amount;
        totalSupply += amount;
    }}
    
    /**
     * @dev Withdraw staked tokens
     */
    function withdraw(uint256 amount) external nonReentrant {{
        require(amount > 0, "Amount = 0");
        require(balanceOf[msg.sender] >= amount, "Not enough staked");
        
        _updateReward(msg.sender);
        
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
        
        stakingToken.safeTransfer(msg.sender, amount);
    }}
    
    /**
     * @dev Claim rewards
     */
    function claimReward() external nonReentrant {{
        _updateReward(msg.sender);
        
        uint256 reward = rewards[msg.sender];
        if (reward > 0) {{
            rewards[msg.sender] = 0;
            rewardsToken.safeTransfer(msg.sender, reward);
        }}
    }}
    
    /**
     * @dev Returns reward per token
     */
    function rewardPerToken() public view returns (uint256) {{
        if (totalSupply == 0) {{
            return rewardPerTokenStored;
        }}
        
        return rewardPerTokenStored + 
            (((min(block.timestamp, finishAt) - updatedAt) * rewardRate * 1e18) / totalSupply);
    }}
    
    /**
     * @dev Returns the amount of rewards a user can claim
     */
    function earned(address account) public view returns (uint256) {{
        return
            ((balanceOf[account] * 
                (rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18) +
            rewards[account];
    }}
    
    /**
     * @dev Updates the reward for a user
     */
    function _updateReward(address account) private {{
        rewardPerTokenStored = rewardPerToken();
        updatedAt = min(block.timestamp, finishAt);
        
        if (account != address(0)) {{
            rewards[account] = earned(account);
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }}
    }}
    
    /**
     * @dev Returns the minimum of two values
     */
    function min(uint256 a, uint256 b) internal pure returns (uint256) {{
        return a < b ? a : b;
    }}
}}"""

    def _get_marketplace_template(self, marketplace_name: str) -> str:
        """Get a basic NFT marketplace template."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title {marketplace_name}
 * @dev Implementation of an NFT marketplace
 */
contract {marketplace_name} is Ownable, ReentrancyGuard {{
    // Market item struct
    struct MarketItem {{
        uint256 itemId;
        address nftContract;
        uint256 tokenId;
        address seller;
        address owner;
        uint256 price;
        bool sold;
    }}
    
    // Fee variables
    uint256 public marketFee = 250; // 2.5% fee (2.5% = 250 / 10000)
    uint256 private constant DENOMINATOR = 10000;
    
    // Item ID counter
    uint256 private _itemIds;
    uint256 private _itemsSold;
    
    // Mapping to keep track of market items
    mapping(uint256 => MarketItem) private idToMarketItem;
    
    // Events
    event MarketItemCreated(
        uint256 indexed itemId,
        address indexed nftContract,
        uint256 indexed tokenId,
        address seller,
        address owner,
        uint256 price,
        bool sold
    );
    
    event MarketItemSold(
        uint256 indexed itemId,
        address indexed nftContract,
        uint256 indexed tokenId,
        address seller,
        address owner,
        uint256 price
    );
    
    /**
     * @dev Constructor 
     */
    constructor() Ownable(msg.sender) {{}}
    
    /**
     * @dev Sets the marketplace fee
     */
    function setMarketFee(uint256 fee) external onlyOwner {{
        require(fee <= 1000, "Fee too high"); // Max 10%
        marketFee = fee;
    }}
    
    /**
     * @dev Creates a market item for sale
     */
    function createMarketItem(
        address nftContract,
        uint256 tokenId,
        uint256 price
    ) external nonReentrant {{
        require(price > 0, "Price must be greater than 0");
        
        _itemIds++;
        uint256 itemId = _itemIds;
        
        idToMarketItem[itemId] = MarketItem(
            itemId,
            nftContract,
            tokenId,
            msg.sender,
            address(0),
            price,
            false
        );
        
        IERC721(nftContract).transferFrom(msg.sender, address(this), tokenId);
        
        emit MarketItemCreated(
            itemId,
            nftContract,
            tokenId,
            msg.sender,
            address(0),
            price,
            false
        );
    }}
    
    /**
     * @dev Creates a market sale
     */
    function createMarketSale(
        address nftContract,
        uint256 itemId
    ) external payable nonReentrant {{
        uint256 price = idToMarketItem[itemId].price;
        uint256 tokenId = idToMarketItem[itemId].tokenId;
        address seller = idToMarketItem[itemId].seller;
        
        require(msg.value == price, "Please submit the asking price");
        require(!idToMarketItem[itemId].sold, "Item already sold");
        
        // Calculate fee
        uint256 fee = (price * marketFee) / DENOMINATOR;
        uint256 sellerAmount = price - fee;
        
        // Transfer fee to contract owner
        payable(owner()).transfer(fee);
        
        // Transfer remaining to seller
        payable(seller).transfer(sellerAmount);
        
        // Transfer NFT to buyer
        IERC721(nftContract).transferFrom(address(this), msg.sender, tokenId);
        
        // Update item status
        idToMarketItem[itemId].owner = msg.sender;
        idToMarketItem[itemId].sold = true;
        _itemsSold++;
        
        emit MarketItemSold(
            itemId,
            nftContract,
            tokenId,
            seller,
            msg.sender,
            price
        );
    }}
    
    /**
     * @dev Returns all unsold market items
     */
    function fetchMarketItems() external view returns (MarketItem[] memory) {{
        uint256 itemCount = _itemIds;
        uint256 unsoldItemCount = _itemIds - _itemsSold;
        uint256 currentIndex = 0;
        
        MarketItem[] memory items = new MarketItem[](unsoldItemCount);
        for (uint256 i = 1; i <= itemCount; i++) {{
            if (!idToMarketItem[i].sold) {{
                items[currentIndex] = idToMarketItem[i];
                currentIndex++;
            }}
        }}
        
        return items;
    }}
    
    /**
     * @dev Returns only items that a user has purchased
     */
    function fetchMyNFTs() external view returns (MarketItem[] memory) {{
        uint256 totalItemCount = _itemIds;
        uint256 itemCount = 0;
        uint256 currentIndex = 0;
        
        for (uint256 i = 1; i <= totalItemCount; i++) {{
            if (idToMarketItem[i].owner == msg.sender) {{
                itemCount++;
            }}
        }}
        
        MarketItem[] memory items = new MarketItem[](itemCount);
        for (uint256 i = 1; i <= totalItemCount; i++) {{
            if (idToMarketItem[i].owner == msg.sender) {{
                items[currentIndex] = idToMarketItem[i];
                currentIndex++;
            }}
        }}
        
        return items;
    }}
    
    /**
     * @dev Returns only items a user has listed
     */
    function fetchItemsListed() external view returns (MarketItem[] memory) {{
        uint256 totalItemCount = _itemIds;
        uint256 itemCount = 0;
        uint256 currentIndex = 0;
        
        for (uint256 i = 1; i <= totalItemCount; i++) {{
            if (idToMarketItem[i].seller == msg.sender) {{
                itemCount++;
            }}
        }}
        
        MarketItem[] memory items = new MarketItem[](itemCount);
        for (uint256 i = 1; i <= totalItemCount; i++) {{
            if (idToMarketItem[i].seller == msg.sender) {{
                items[currentIndex] = idToMarketItem[i];
                currentIndex++;
            }}
        }}
        
        return items;
    }}
}}"""

    def _get_custom_template(self, contract_name: str) -> str:
        """Get a template for a custom contract."""
        return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title {contract_name}
 * @dev Custom contract for {contract_name}
 */
contract {contract_name} is Ownable, Pausable {{
    // Contract state variables

    // Events

    /**
     * @dev Constructor
     */
    constructor() Ownable(msg.sender) {{
        // Initialization
    }}

    // Contract functions
}}"""

    async def _generate_with_hardhat(
        self,
        specifications: Dict[str, Any],
        project_dir: Path,
        context: Optional[DAppGenerationContext] = None
    ) -> Dict[str, Any]:
        """
        Generate smart contract using Hardhat tool.

        Args:
            specifications: Contract specifications
            project_dir: Directory for the project
            context: Generation context for tracking

        Returns:
            Dictionary with contract artifacts
        """
        self.logger.info("generating_with_hardhat", project_dir=str(project_dir))

        try:
            # Initialize Hardhat adapter
            hardhat = HardhatAdapter(self.tool_executor)

            # Validate Hardhat is available
            if not await hardhat.validate_installation():
                raise Exception("Hardhat is not installed or not available")

            # Initialize Hardhat project
            self.logger.info("initializing_hardhat_project")
            init_result = await hardhat.initialize_project(
                project_path=str(project_dir),
                config={"project_type": "javascript", "sample_project": False}
            )

            if context:
                context.add_tool_execution_result(init_result)

            if not init_result.success:
                raise Exception(f"Failed to initialize Hardhat project: {init_result.error_message}")

            # Install OpenZeppelin contracts: both the OZ templates and the
            # LLM-generated contracts import @openzeppelin/contracts/*.
            oz_install = await OpenZeppelinAdapter(self.tool_executor).initialize_project(
                project_path=str(project_dir),
                config={"version": "5.0.0"}
            )
            if context:
                context.add_tool_execution_result(oz_install)
            if not oz_install.success:
                raise Exception(f"Failed to install OpenZeppelin contracts: {oz_install.error_message}")

            # Generate contract using OpenZeppelin if standard type
            contract_type = specifications.get("contractType", "custom")
            if contract_type in ["erc20", "erc721", "erc1155"]:
                # Use OpenZeppelin for standard contracts
                contract_code = await self._generate_with_openzeppelin(
                    specifications, project_dir, context
                )
            else:
                # Use LLM for custom contracts
                contract_code = await self._generate_contract_with_llm(specifications)

            # Write contract to Hardhat contracts directory
            contracts_dir = project_dir / "contracts"
            contracts_dir.mkdir(exist_ok=True)

            contract_name = specifications.get("projectName", "MyContract")
            contract_file = contracts_dir / f"{contract_name}.sol"
            contract_file.write_text(contract_code)

            self.logger.info("contract_written", file=str(contract_file))

            # Compile with Hardhat
            self.logger.info("compiling_with_hardhat")
            compile_result = await hardhat.compile_contracts(project_dir)

            if context:
                context.add_tool_execution_result(compile_result)

            if not compile_result.success:
                # Try to fix compilation errors with LLM
                self.logger.warning("compilation_failed", error=compile_result.error_message)
                if context:
                    context.record_fallback("Hardhat compilation failed, attempting fixes")

                # TODO: Implement LLM-based error fixing
                raise Exception(f"Compilation failed: {compile_result.error_message}")

            # Extract ABI and bytecode from artifacts
            artifacts_dir = project_dir / "artifacts" / "contracts" / f"{contract_name}.sol"
            artifact_file = artifacts_dir / f"{contract_name}.json"

            if artifact_file.exists():
                artifact_data = json.loads(artifact_file.read_text())
                abi = artifact_data.get("abi", [])
                bytecode = artifact_data.get("bytecode", "")

                return {
                    "contract_name": contract_name,
                    "contract_type": contract_type,
                    "contract_code": contract_code,
                    "abi": abi,
                    "bytecode": bytecode,
                    "compilation_success": True,
                    "tool_used": "hardhat",
                }
            else:
                raise Exception(f"Artifact file not found: {artifact_file}")

        except Exception as e:
            self.logger.error("hardhat_generation_failed", error=str(e))
            if context:
                context.record_fallback(f"Hardhat generation failed: {str(e)}")
            raise

    async def _generate_with_openzeppelin(
        self,
        specifications: Dict[str, Any],
        project_dir: Path,
        context: Optional[DAppGenerationContext] = None
    ) -> str:
        """
        Generate smart contract using OpenZeppelin Wizard.

        Args:
            specifications: Contract specifications
            project_dir: Directory for the project
            context: Generation context for tracking

        Returns:
            Contract source code
        """
        self.logger.info("generating_with_openzeppelin")

        try:
            # Initialize OpenZeppelin adapter
            oz_adapter = OpenZeppelinAdapter(self.tool_executor)

            # Validate OpenZeppelin is available
            if not await oz_adapter.validate_installation():
                raise Exception("OpenZeppelin is not installed")

            # Map specifications to OpenZeppelin parameters
            contract_type = specifications.get("contractType", "erc20")
            features = specifications.get("contractFeatures", {})
            contract_name = specifications.get("projectName", "MyToken")

            # Feature flags arrive as {name: bool}; the adapter expects the
            # enabled feature names.
            features_list = (
                [k for k, v in features.items() if v]
                if isinstance(features, dict) else list(features or [])
            )

            self.logger.info("calling_openzeppelin_wizard", contract_type=contract_type)

            contract_code = oz_adapter.get_contract_template(
                contract_type,
                features_list,
                {
                    "name": contract_name,
                    "symbol": contract_name[:3].upper(),
                    "premint": "1000000",
                },
            )
            if not contract_code:
                raise Exception(f"No OpenZeppelin template for contract type: {contract_type}")

            if context:
                context.add_tool_used("openzeppelin")

            self.logger.info("openzeppelin_generation_complete")
            return contract_code

        except Exception as e:
            self.logger.error("openzeppelin_generation_failed", error=str(e))
            if context:
                context.record_fallback(f"OpenZeppelin generation failed: {str(e)}")
            # Fallback to LLM-based generation
            return await self._generate_contract_with_llm(specifications)

    async def _generate_contract_with_llm(
        self,
        specifications: Dict[str, Any]
    ) -> str:
        """
        Generate contract using LLM (fallback method).

        Args:
            specifications: Contract specifications

        Returns:
            Contract source code
        """
        contract_type = specifications.get("contractType", "custom")
        contract_features = specifications.get("contractFeatures", {})
        project_name = specifications.get("projectName", "MyToken")
        project_description = specifications.get("projectDescription", "")

        # Get contract template function
        template_func = self.contract_templates.get(contract_type, self._get_custom_template)

        # Create base template
        template = template_func(project_name)

        # Use LLM to customize the template
        contract_prompt = (
            f"Generate a Solidity smart contract with the following specifications:\n\n"
            f"Type: {contract_type}\n"
            f"Name: {project_name}\n"
            f"Description: {project_description}\n"
            f"Features: {json.dumps(contract_features, indent=2)}\n\n"
            f"Use the following template as a starting point:\n\n"
            f"{template}\n\n"
            f"Customize this template based on the specifications. "
            f"Make sure the code is secure, follows best practices, and is well-documented. "
            f"Include natspec comments. Output only the Solidity code."
        )

        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": contract_prompt}
        ]

        contract_code = await self.llm.generate_completion(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature
        )

        return self._strip_code_fences(contract_code)

    @staticmethod
    def _strip_code_fences(code: str) -> str:
        """Remove surrounding markdown code fences from LLM output.

        LLMs commonly wrap Solidity in ```solidity ... ``` fences. Left in
        place these break `solc`/Hardhat compilation, so strip a single
        leading/trailing fence pair (and any language tag) if present.
        """
        if not code:
            return code
        text = code.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # drop opening fence line (``` or ```solidity)
            lines = lines[1:]
            # drop closing fence line if present
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    async def _generate_with_tool_based_strategy(
        self,
        specifications: Dict[str, Any],
        context: Optional[DAppGenerationContext] = None
    ) -> Dict[str, Any]:
        """
        Generate contract using pure tool-based approach (Hardhat + OpenZeppelin).

        This strategy is best for standard contracts (ERC20, ERC721, ERC1155)
        where OpenZeppelin provides reliable templates.
        """
        self.logger.info("using_tool_based_strategy")

        # Create temporary project directory
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Generate using Hardhat
            result = await self._generate_with_hardhat(
                specifications, project_dir, context
            )

            return result

    async def _generate_with_hybrid_strategy(
        self,
        specifications: Dict[str, Any],
        context: Optional[DAppGenerationContext] = None
    ) -> Dict[str, Any]:
        """
        Generate contract using hybrid approach (tools + LLM).

        This strategy:
        1. Uses Hardhat for project structure
        2. Uses OpenZeppelin for standard parts (if applicable)
        3. Uses LLM for custom logic and customizations
        """
        self.logger.info("using_hybrid_strategy")

        try:
            # Create temporary project directory
            with tempfile.TemporaryDirectory() as temp_dir:
                project_dir = Path(temp_dir)

                # Start with tool-based generation
                result = await self._generate_with_hardhat(
                    specifications, project_dir, context
                )

                # Use LLM to enhance/customize the generated contract
                contract_code = result.get("contract_code", "")

                # Ask LLM to review and enhance
                enhancement_prompt = (
                    f"Review and enhance the following Solidity contract based on these requirements:\n\n"
                    f"Requirements:\n"
                    f"- Type: {specifications.get('contractType')}\n"
                    f"- Description: {specifications.get('projectDescription')}\n"
                    f"- Features: {json.dumps(specifications.get('contractFeatures', {}), indent=2)}\n\n"
                    f"Current Contract:\n{contract_code}\n\n"
                    f"Tasks:\n"
                    f"1. Add any missing custom features from the requirements\n"
                    f"2. Enhance documentation and natspec comments\n"
                    f"3. Add custom business logic if needed\n"
                    f"4. Ensure security best practices\n\n"
                    f"Output only the improved Solidity code."
                )

                messages = [
                    {"role": "system", "content": self.config.system_prompt},
                    {"role": "user", "content": enhancement_prompt}
                ]

                enhanced_code = await self.llm.generate_completion(
                    messages=messages,
                    model=self.config.model,
                    temperature=0.3  # Slightly higher for customization
                )

                result["contract_code"] = enhanced_code
                result["strategy"] = "hybrid"
                result["enhanced_with_llm"] = True

                return result

        except Exception as e:
            self.logger.error("hybrid_strategy_failed", error=str(e))
            # Fallback to LLM-only
            if context:
                context.record_fallback(f"Hybrid strategy failed: {str(e)}")
            return await self._generate_with_llm_only_strategy(specifications, context)

    async def _generate_with_llm_only_strategy(
        self,
        specifications: Dict[str, Any],
        context: Optional[DAppGenerationContext] = None
    ) -> Dict[str, Any]:
        """
        Generate contract using pure LLM approach (existing method).

        This is the fallback strategy when tools are not available or
        for complex custom contracts that require novel implementations.
        """
        self.logger.info("using_llm_only_strategy")

        contract_type = specifications.get("contractType", "custom")
        contract_features = specifications.get("contractFeatures", {})
        project_name = specifications.get("projectName", "MyToken")

        # Generate contract code using LLM
        contract_code = await self._generate_contract_with_llm(specifications)

        # For LLM-only, we don't have compiled artifacts
        # Return just the source code
        return {
            "contract_name": project_name,
            "contract_type": contract_type,
            "contract_code": contract_code,
            "features": contract_features,
            "abi": [],  # Would need separate compilation
            "bytecode": None,
            "compilation_success": False,
            "tool_used": "llm",
            "strategy": "llm_only"
        }
