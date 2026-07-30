"""
OpenZeppelin Adapter for secure smart contract templates.

OpenZeppelin provides battle-tested contract libraries and a wizard
for generating standard contracts (ERC20, ERC721, ERC1155, Governor).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from vibedapps.tools.adapters.base import ToolAdapter
from vibedapps.tools.executor import ToolExecutor
from vibedapps.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)


class OpenZeppelinAdapter(ToolAdapter):
    """Adapter for OpenZeppelin Contracts and Wizard."""
    
    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """Initialize the OpenZeppelin adapter."""
        super().__init__(tool_executor)
        self._tool_name = "openzeppelin"
    
    def get_cli_command(self) -> str:
        """Get the CLI command for OpenZeppelin."""
        return "npx @openzeppelin/wizard"
    
    def get_capabilities(self) -> List[str]:
        """Get OpenZeppelin capabilities."""
        return [
            "contract_template",
            "erc20_generation",
            "erc721_generation",
            "erc1155_generation",
            "governor_generation",
            "security_patterns"
        ]
    
    async def validate_installation(self) -> bool:
        """
        Check if OpenZeppelin is available.
        
        Returns:
            True if OpenZeppelin is available, False otherwise
        """
        try:
            # Check if we can access npm
            result = await self.tool_executor.execute(
                command="npm",
                args=["list", "-g", "@openzeppelin/contracts"],
                cwd=".",
                timeout=30,
                raise_on_error=False
            )
            
            # OpenZeppelin is available if npm works (we'll install it per-project)
            return True
        
        except Exception as e:
            logger.warning(f"OpenZeppelin validation failed: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """
        Get OpenZeppelin version.
        
        Returns:
            Version string if available, None otherwise
        """
        # OpenZeppelin version is typically per-project
        return "5.0.0"  # Latest stable version
    
    async def initialize_project(
        self,
        project_path: str,
        config: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Initialize OpenZeppelin in a project.
        
        Args:
            project_path: Path to the project
            config: Configuration options:
                - version: str - OpenZeppelin version (default: "5.0.0")
                
        Returns:
            ToolExecutionResult with initialization results
        """
        logger.info(f"Installing OpenZeppelin contracts in {project_path}")
        
        version = config.get("version", "5.0.0")
        
        # Install OpenZeppelin contracts
        result = await self.tool_executor.execute(
            command="npm",
            args=["install", f"@openzeppelin/contracts@{version}"],
            cwd=project_path,
            timeout=300
        )
        
        self.log_execution("installation", result)
        
        return result
    
    async def generate_contract(
        self,
        contract_type: str,
        features: List[str],
        output_path: str,
        config: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Generate a contract using OpenZeppelin patterns.
        
        Args:
            contract_type: Type of contract (erc20, erc721, erc1155, governor)
            features: List of features to include
            output_path: Path where contract should be saved
            config: Optional configuration:
                - name: str - Contract name
                - symbol: str - Token symbol (for tokens)
                - premint: str - Premint amount (for tokens)
                
        Returns:
            ToolExecutionResult with generation results
        """
        logger.info(f"Generating {contract_type} contract with features: {features}")
        
        config = config or {}
        
        # Generate contract code based on type
        contract_code = self.get_contract_template(contract_type, features, config)
        
        if not contract_code:
            return ToolExecutionResult(
                command=f"generate {contract_type}",
                exit_code=1,
                stdout="",
                stderr=f"Failed to generate {contract_type} contract",
                execution_time=0.0,
                success=False,
                error_message="Contract generation failed"
            )
        
        # Write contract to file
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                f.write(contract_code)
            
            logger.info(f"Contract written to {output_path}")
            
            return ToolExecutionResult(
                command=f"generate {contract_type}",
                exit_code=0,
                stdout=f"Contract generated at {output_path}",
                stderr="",
                execution_time=0.1,
                success=True
            )
        
        except Exception as e:
            logger.error(f"Error writing contract: {e}")
            return ToolExecutionResult(
                command=f"generate {contract_type}",
                exit_code=1,
                stdout="",
                stderr=str(e),
                execution_time=0.0,
                success=False,
                error_message=str(e)
            )
    
    def get_contract_template(
        self,
        contract_type: str,
        features: List[str],
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Get contract code from OpenZeppelin templates.
        
        Args:
            contract_type: Type of contract (erc20, erc721, erc1155, governor)
            features: List of features to include
            config: Optional configuration
            
        Returns:
            Contract source code or None
        """
        config = config or {}
        name = config.get("name", "MyToken")
        symbol = config.get("symbol", "MTK")
        
        if contract_type.lower() == "erc20":
            return self._generate_erc20(name, symbol, features, config)
        elif contract_type.lower() == "erc721":
            return self._generate_erc721(name, symbol, features, config)
        elif contract_type.lower() == "erc1155":
            return self._generate_erc1155(name, features, config)
        elif contract_type.lower() == "governor":
            return self._generate_governor(name, features, config)
        else:
            logger.error(f"Unknown contract type: {contract_type}")
            return None
    
    def _generate_erc20(
        self,
        name: str,
        symbol: str,
        features: List[str],
        config: Dict[str, Any]
    ) -> str:
        """Generate ERC20 token contract."""
        
        imports = ["import \"@openzeppelin/contracts/token/ERC20/ERC20.sol\";"]
        inheritance = ["ERC20"]
        constructor_body = []
        additional_functions = []
        
        # Add features
        if "mintable" in features:
            imports.append("import \"@openzeppelin/contracts/access/Ownable.sol\";")
            inheritance.append("Ownable")
            additional_functions.append('''
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }''')
        
        if "burnable" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol\";")
            inheritance.append("ERC20Burnable")
        
        if "pausable" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol\";")
            imports.append("import \"@openzeppelin/contracts/access/Ownable.sol\";")
            inheritance.append("ERC20Pausable")
            if "Ownable" not in inheritance:
                inheritance.append("Ownable")
            additional_functions.append('''
    function pause() public onlyOwner {
        _pause();
    }

    function unpause() public onlyOwner {
        _unpause();
    }''')
        
        if "permit" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol\";")
            inheritance.append("ERC20Permit")
        
        # Premint
        premint = config.get("premint", "")
        if premint:
            constructor_body.append(f'        _mint(msg.sender, {premint} * 10 ** decimals());')
        
        # Build contract
        imports_str = "\n".join(sorted(set(imports)))
        inheritance_str = ", ".join(inheritance)
        constructor_params = 'address initialOwner' if 'Ownable' in inheritance else ''
        constructor_init = '\n        Ownable(initialOwner)' if 'Ownable' in inheritance else ''
        constructor_init += f'\n        ERC20Permit("{name}")' if 'ERC20Permit' in inheritance else ''
        constructor_body_str = "\n".join(constructor_body) if constructor_body else ''
        functions_str = "\n".join(additional_functions)
        
        contract = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

{imports_str}

contract {name} is {inheritance_str} {{
    constructor({constructor_params}){constructor_init}
        ERC20("{name}", "{symbol}")
    {{{constructor_body_str}
    }}
{functions_str}
}}
'''
        return contract
    
    def _generate_erc721(
        self,
        name: str,
        symbol: str,
        features: List[str],
        config: Dict[str, Any]
    ) -> str:
        """Generate ERC721 NFT contract."""
        
        imports = ["import \"@openzeppelin/contracts/token/ERC721/ERC721.sol\";"]
        inheritance = ["ERC721"]
        state_vars = []
        constructor_body = []
        additional_functions = []
        
        # Add features
        if "mintable" in features or "auto_increment" in features:
            imports.append("import \"@openzeppelin/contracts/access/Ownable.sol\";")
            inheritance.append("Ownable")
            state_vars.append("    uint256 private _nextTokenId;")
            additional_functions.append('''
    function safeMint(address to) public onlyOwner {
        uint256 tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
    }''')
        
        if "burnable" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC721/extensions/ERC721Burnable.sol\";")
            inheritance.append("ERC721Burnable")
        
        if "enumerable" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol\";")
            inheritance.append("ERC721Enumerable")
        
        if "uri_storage" in features:
            imports.append("import \"@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol\";")
            inheritance.append("ERC721URIStorage")
        
        # Build contract
        imports_str = "\n".join(sorted(set(imports)))
        inheritance_str = ", ".join(inheritance)
        state_vars_str = "\n".join(state_vars)
        constructor_params = 'address initialOwner' if 'Ownable' in inheritance else ''
        constructor_init = '\n        Ownable(initialOwner)' if 'Ownable' in inheritance else ''
        functions_str = "\n".join(additional_functions)
        
        contract = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

{imports_str}

contract {name} is {inheritance_str} {{
{state_vars_str}

    constructor({constructor_params}){constructor_init}
        ERC721("{name}", "{symbol}")
    {{}}
{functions_str}
}}
'''
        return contract
    
    def _generate_erc1155(
        self,
        name: str,
        features: List[str],
        config: Dict[str, Any]
    ) -> str:
        """Generate ERC1155 multi-token contract."""
        
        contract = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract {name} is ERC1155, Ownable {{
    constructor(address initialOwner)
        ERC1155("https://api.example.com/metadata/{{id}}.json")
        Ownable(initialOwner)
    {{}}

    function mint(address account, uint256 id, uint256 amount, bytes memory data)
        public
        onlyOwner
    {{
        _mint(account, id, amount, data);
    }}

    function mintBatch(address to, uint256[] memory ids, uint256[] memory amounts, bytes memory data)
        public
        onlyOwner
    {{
        _mintBatch(to, ids, amounts, data);
    }}
}}
'''
        return contract
    
    def _generate_governor(
        self,
        name: str,
        features: List[str],
        config: Dict[str, Any]
    ) -> str:
        """Generate Governor (DAO) contract."""
        
        contract = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";

contract {name} is Governor, GovernorSettings, GovernorCountingSimple, GovernorVotes, GovernorVotesQuorumFraction {{
    constructor(IVotes _token)
        Governor("{name}")
        GovernorSettings(1, 50400, 0)
        GovernorVotes(_token)
        GovernorVotesQuorumFraction(4)
    {{}}

    function votingDelay()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {{
        return super.votingDelay();
    }}

    function votingPeriod()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {{
        return super.votingPeriod();
    }}

    function quorum(uint256 blockNumber)
        public
        view
        override(Governor, GovernorVotesQuorumFraction)
        returns (uint256)
    {{
        return super.quorum(blockNumber);
    }}

    function proposalThreshold()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {{
        return super.proposalThreshold();
    }}
}}
'''
        return contract
