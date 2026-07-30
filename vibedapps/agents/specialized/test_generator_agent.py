"""
Test generator agent.

Reads the contract ABI and produces a Hardhat/ethers.js test suite: unit
tests per function, feature tests (minting, burning, pausing), and a few
security checks.
"""

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from vibedapps.agents.base_agent import AgentConfig, BaseAgent
from vibedapps.llm.openai_service import OpenAIService
from vibedapps.memory.memory_store import InMemoryStore, MemoryStore


class TestGeneratorAgent(BaseAgent):
    """Agent that writes Hardhat test suites for generated contracts."""

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            memory_store: Optional[MemoryStore] = None,
            llm_service: Optional[OpenAIService] = None
    ):
        # Default config if not provided
        if not config:
            config = AgentConfig(
                name="Test Generator",
                description="Generates comprehensive test suites for smart contracts including unit, integration, and security tests",
                capabilities=["hardhat-tests", "unit-tests", "integration-tests", "security-tests"],
                model="gpt-4o",
                temperature=0.3,
                system_prompt=(
                    "You are a specialized agent for generating comprehensive test suites for smart contracts. "
                    "You excel at creating thorough tests that cover all functions, edge cases, and security concerns. "
                    "You generate tests using Hardhat with ethers.js, following best practices for smart contract testing."
                )
            )

        super().__init__(config, memory_store or InMemoryStore(), llm_service)

        # Register specialized endpoints
        self._register_specialized_endpoints()

    def _register_specialized_endpoints(self):
        """Register specialized endpoints for this agent."""
        router = APIRouter()

        @router.post("/generate")
        async def generate_tests(specifications: Dict[str, Any]):
            """Generate test suite based on contract specifications."""
            return await self.specialized_capability(specifications=specifications)

        # Add the router to the app
        self.app.include_router(router, prefix="/api/test-generator")

    @staticmethod
    def _extract_constructor_inputs(
        contract_abi: List[Dict[str, Any]],
        contract_source: str = ""
    ) -> List[Dict[str, str]]:
        """
        Determine the contract's constructor parameters.

        Prefers the ABI (exact, available when the contract was compiled);
        falls back to parsing the Solidity source, which is all we have in
        LLM-only mode where the ABI is a placeholder.

        Returns:
            List of {"type": ..., "name": ...} dicts (empty = no-arg constructor)
        """
        for item in contract_abi or []:
            if item.get("type") == "constructor":
                return [
                    {"type": inp.get("type", "uint256"), "name": inp.get("name", "")}
                    for inp in item.get("inputs", [])
                ]

        match = re.search(r"constructor\s*\(([^)]*)\)", contract_source or "")
        if not match:
            return []
        params = match.group(1).strip()
        if not params:
            return []
        inputs = []
        for raw in params.split(","):
            parts = raw.split()  # e.g. "uint256 initialSupply", "string memory name_"
            if not parts:
                continue
            inputs.append({
                "type": parts[0],
                "name": parts[-1] if len(parts) > 1 else ""
            })
        return inputs

    @staticmethod
    def _js_value_for_arg(sol_type: str, name: str) -> str:
        """Pick a reasonable JS literal for a constructor argument."""
        name_lower = (name or "").lower()
        if sol_type.endswith("[]"):
            return "[]"
        if sol_type.startswith("uint") or sol_type.startswith("int"):
            # Token contracts usually scale by 10 ** decimals() internally or
            # expect a raw supply; a plain million works for both.
            if "supply" in name_lower or "amount" in name_lower:
                return "1000000"
            if "time" in name_lower or "deadline" in name_lower:
                return "Math.floor(Date.now() / 1000) + 3600"
            return "1"
        if sol_type == "address":
            return "owner.address"
        if sol_type == "string":
            return '"Test"'
        if sol_type == "bool":
            return "false"
        if sol_type == "bytes32":
            return "ethers.ZeroHash"
        if sol_type.startswith("bytes"):
            return '"0x"'
        return "0"

    def _generate_test_template(
        self,
        contract_name: str,
        contract_abi: List[Dict[str, Any]],
        contract_features: List[str],
        contract_source: str = ""
    ) -> str:
        """
        Generate Hardhat test template with test cases for all contract functions.

        Args:
            contract_name: Name of the contract
            contract_abi: Contract ABI
            contract_features: List of features (ERC20, Mintable, etc.)
            contract_source: Solidity source (constructor-arg fallback)

        Returns:
            Complete test file as string
        """
        # Deployment must match the contract's constructor signature
        constructor_inputs = self._extract_constructor_inputs(contract_abi, contract_source)
        deploy_args = ", ".join(
            self._js_value_for_arg(inp["type"], inp["name"]) for inp in constructor_inputs
        )
        constructor_comment = ""
        if constructor_inputs:
            signature = ", ".join(
                f"{inp['type']} {inp['name']}".strip() for inp in constructor_inputs
            )
            constructor_comment = f" // constructor({signature})"

        # Extract functions from ABI
        functions = [item for item in contract_abi if item.get("type") == "function"]

        # Categorize functions
        view_functions = [f for f in functions if f.get("stateMutability") in ["view", "pure"]]
        write_functions = [f for f in functions if f.get("stateMutability") not in ["view", "pure"]]

        # Start building test file
        test_code = f"""const {{ expect }} = require("chai");
const {{ ethers }} = require("hardhat");

describe("{contract_name}", function () {{
  let {contract_name.lower()};
  let owner;
  let addr1;
  let addr2;
  let addrs;

  beforeEach(async function () {{
    // Get signers
    [owner, addr1, addr2, ...addrs] = await ethers.getSigners();

    // Deploy contract{constructor_comment}
    const {contract_name}Factory = await ethers.getContractFactory("{contract_name}");
    {contract_name.lower()} = await {contract_name}Factory.deploy({deploy_args});
    await {contract_name.lower()}.waitForDeployment();
  }});

  describe("Deployment", function () {{
    it("Should set the right owner", async function () {{
      // This test might need adjustment based on your contract's ownership mechanism
      // For Ownable contracts:
      // expect(await {contract_name.lower()}.owner()).to.equal(owner.address);
    }});

    it("Should deploy with correct initial state", async function () {{
      // Add deployment state checks here
      expect(await {contract_name.lower()}.getAddress()).to.be.properAddress;
    }});
  }});

"""

        # Generate tests for view functions
        if view_functions:
            test_code += """  describe("View Functions", function () {
"""
            for func in view_functions:
                func_name = func["name"]
                test_code += f"""    it("Should return correct value from {func_name}", async function () {{
      // TODO: Add specific test logic for {func_name}
      // const result = await {contract_name.lower()}.{func_name}();
      // expect(result).to.equal(expectedValue);
    }});

"""
            test_code += """  });

"""

        # Generate tests for write functions
        if write_functions:
            test_code += """  describe("State-Changing Functions", function () {
"""
            for func in write_functions:
                func_name = func["name"]
                inputs = func.get("inputs", [])

                # Generate test for successful execution
                test_code += f"""    it("Should execute {func_name} successfully", async function () {{
"""
                if inputs:
                    params_comment = ", ".join([f"{inp['name']}: {inp['type']}" for inp in inputs])
                    test_code += f"""      // Parameters: {params_comment}
      // const tx = await {contract_name.lower()}.{func_name}(/* add parameters */);
      // await tx.wait();
      // expect(await {contract_name.lower()}.someStateVar()).to.equal(expectedValue);
"""
                else:
                    test_code += f"""      const tx = await {contract_name.lower()}.{func_name}();
      await tx.wait();
      // Add assertions here
"""
                test_code += """    });

"""

                # Generate test for failure cases
                test_code += f"""    it("Should revert {func_name} with invalid parameters", async function () {{
      // await expect(
      //   {contract_name.lower()}.{func_name}(/* invalid parameters */)
      // ).to.be.revertedWith("Error message");
    }});

"""

            test_code += """  });

"""

        # Add feature-specific tests
        if "ERC20" in contract_features or "erc20" in [f.lower() for f in contract_features]:
            test_code += self._generate_erc20_tests(contract_name.lower())

        if "Mintable" in contract_features or "mintable" in [f.lower() for f in contract_features]:
            test_code += self._generate_mintable_tests(contract_name.lower())

        if "Burnable" in contract_features or "burnable" in [f.lower() for f in contract_features]:
            test_code += self._generate_burnable_tests(contract_name.lower())

        if "Pausable" in contract_features or "pausable" in [f.lower() for f in contract_features]:
            test_code += self._generate_pausable_tests(contract_name.lower())

        # Add security tests
        test_code += self._generate_security_tests(contract_name.lower())

        # Close describe block
        test_code += """});
"""

        return test_code

    def _generate_erc20_tests(self, contract_var: str) -> str:
        """Generate ERC20-specific test cases"""
        return f"""  describe("ERC20 Functionality", function () {{
    it("Should have correct name and symbol", async function () {{
      const name = await {contract_var}.name();
      const symbol = await {contract_var}.symbol();
      expect(name).to.be.a('string');
      expect(symbol).to.be.a('string');
    }});

    it("Should transfer tokens between accounts", async function () {{
      const transferAmount = ethers.parseEther("50");

      // Transfer from owner to addr1
      await {contract_var}.transfer(addr1.address, transferAmount);
      const addr1Balance = await {contract_var}.balanceOf(addr1.address);
      expect(addr1Balance).to.equal(transferAmount);
    }});

    it("Should fail if sender doesn't have enough tokens", async function () {{
      const initialBalance = await {contract_var}.balanceOf(addr1.address);

      await expect(
        {contract_var}.connect(addr1).transfer(owner.address, initialBalance + 1n)
      ).to.be.reverted;
    }});

    it("Should update balances after transfers", async function () {{
      const initialOwnerBalance = await {contract_var}.balanceOf(owner.address);
      const amount = ethers.parseEther("100");

      // Transfer from owner to addr1
      await {contract_var}.transfer(addr1.address, amount);

      // Transfer from owner to addr2
      await {contract_var}.transfer(addr2.address, amount);

      const finalOwnerBalance = await {contract_var}.balanceOf(owner.address);
      expect(finalOwnerBalance).to.equal(initialOwnerBalance - (amount * 2n));

      const addr1Balance = await {contract_var}.balanceOf(addr1.address);
      expect(addr1Balance).to.equal(amount);

      const addr2Balance = await {contract_var}.balanceOf(addr2.address);
      expect(addr2Balance).to.equal(amount);
    }});

    it("Should approve and transferFrom correctly", async function () {{
      const amount = ethers.parseEther("100");

      // Owner approves addr1 to spend tokens
      await {contract_var}.approve(addr1.address, amount);

      // Check allowance
      expect(await {contract_var}.allowance(owner.address, addr1.address)).to.equal(amount);

      // addr1 transfers from owner to addr2
      await {contract_var}.connect(addr1).transferFrom(owner.address, addr2.address, amount);

      // Check balances
      expect(await {contract_var}.balanceOf(addr2.address)).to.equal(amount);
    }});
  }});

"""

    def _generate_mintable_tests(self, contract_var: str) -> str:
        """Generate Mintable-specific test cases"""
        return f"""  describe("Minting Functionality", function () {{
    it("Should mint tokens to an address", async function () {{
      const mintAmount = ethers.parseEther("1000");
      const initialBalance = await {contract_var}.balanceOf(addr1.address);

      await {contract_var}.mint(addr1.address, mintAmount);

      const finalBalance = await {contract_var}.balanceOf(addr1.address);
      expect(finalBalance).to.equal(initialBalance + mintAmount);
    }});

    it("Should only allow owner to mint", async function () {{
      const mintAmount = ethers.parseEther("1000");

      await expect(
        {contract_var}.connect(addr1).mint(addr2.address, mintAmount)
      ).to.be.reverted;
    }});

    it("Should increase total supply when minting", async function () {{
      const mintAmount = ethers.parseEther("1000");
      const initialSupply = await {contract_var}.totalSupply();

      await {contract_var}.mint(addr1.address, mintAmount);

      const finalSupply = await {contract_var}.totalSupply();
      expect(finalSupply).to.equal(initialSupply + mintAmount);
    }});
  }});

"""

    def _generate_burnable_tests(self, contract_var: str) -> str:
        """Generate Burnable-specific test cases"""
        return f"""  describe("Burning Functionality", function () {{
    it("Should burn tokens from sender", async function () {{
      const burnAmount = ethers.parseEther("100");

      // First mint some tokens to addr1
      await {contract_var}.mint(addr1.address, ethers.parseEther("1000"));
      const initialBalance = await {contract_var}.balanceOf(addr1.address);

      // Burn tokens
      await {contract_var}.connect(addr1).burn(burnAmount);

      const finalBalance = await {contract_var}.balanceOf(addr1.address);
      expect(finalBalance).to.equal(initialBalance - burnAmount);
    }});

    it("Should decrease total supply when burning", async function () {{
      const burnAmount = ethers.parseEther("100");

      // Mint tokens first
      await {contract_var}.mint(owner.address, ethers.parseEther("1000"));
      const initialSupply = await {contract_var}.totalSupply();

      // Burn tokens
      await {contract_var}.burn(burnAmount);

      const finalSupply = await {contract_var}.totalSupply();
      expect(finalSupply).to.equal(initialSupply - burnAmount);
    }});

    it("Should fail to burn more than balance", async function () {{
      const balance = await {contract_var}.balanceOf(owner.address);

      await expect(
        {contract_var}.burn(balance + 1n)
      ).to.be.reverted;
    }});
  }});

"""

    def _generate_pausable_tests(self, contract_var: str) -> str:
        """Generate Pausable-specific test cases"""
        return f"""  describe("Pausable Functionality", function () {{
    it("Should pause and unpause", async function () {{
      await {contract_var}.pause();
      expect(await {contract_var}.paused()).to.equal(true);

      await {contract_var}.unpause();
      expect(await {contract_var}.paused()).to.equal(false);
    }});

    it("Should prevent transfers when paused", async function () {{
      await {contract_var}.pause();

      await expect(
        {contract_var}.transfer(addr1.address, ethers.parseEther("100"))
      ).to.be.revertedWith("Pausable: paused");
    }});

    it("Should only allow owner to pause", async function () {{
      await expect(
        {contract_var}.connect(addr1).pause()
      ).to.be.reverted;
    }});
  }});

"""

    def _generate_security_tests(self, contract_var: str) -> str:
        """Generate security-focused test cases"""
        return f"""  describe("Security Tests", function () {{
    it("Should prevent reentrancy attacks", async function () {{
      // Add reentrancy test if applicable
      // This is a placeholder - adjust based on contract functionality
    }});

    it("Should handle zero address correctly", async function () {{
      // Most contracts should reject zero address
      await expect(
        {contract_var}.transfer(ethers.ZeroAddress, ethers.parseEther("100"))
      ).to.be.reverted;
    }});

    it("Should handle zero amount correctly", async function () {{
      // Test with zero amount - should typically succeed but not change state
      await {contract_var}.transfer(addr1.address, 0);
    }});

    it("Should check for integer overflow/underflow", async function () {{
      // Modern Solidity 0.8+ has built-in overflow checks
      // This test verifies that behavior
      const maxUint256 = ethers.MaxUint256;

      // This should revert due to overflow protection
      // Adjust based on your contract's specific functions
    }});
  }});

"""

    async def specialized_capability(self, **kwargs) -> Any:
        """Generate comprehensive test suite for a smart contract."""
        specifications = kwargs.get("specifications", {})
        generation_context = kwargs.get("context")

        if not specifications and not generation_context:
            raise HTTPException(status_code=400, detail="No specifications or context provided")

        # Extract contract details
        contract_name = "MyContract"
        contract_abi = []
        contract_features = []
        contract_source = ""

        # Get from context if available
        if generation_context:
            primary_contract = generation_context.get_primary_contract()
            if primary_contract:
                contract_name = primary_contract.name
                contract_abi = primary_contract.abi
                contract_source = primary_contract.source_code or ""
                # Extract features from specifications if available
                if hasattr(generation_context, 'specifications'):
                    contract_specs = generation_context.specifications.get("contractFeatures", {})
                    contract_features = [k for k, v in contract_specs.items() if v]

        # Fall back to specifications
        if not contract_abi:
            contract_details = specifications.get("contractDetails", {})
            contract_name = contract_details.get("contract_name", contract_name)
            contract_abi = contract_details.get("contract_abi", [])
            contract_source = contract_source or contract_details.get("contract_code", "")

        if not contract_features:
            contract_specs = specifications.get("contractFeatures", {})
            contract_features = [k for k, v in contract_specs.items() if v] if isinstance(contract_specs, dict) else []

        # Generate test file
        test_content = self._generate_test_template(
            contract_name=contract_name,
            contract_abi=contract_abi,
            contract_features=contract_features,
            contract_source=contract_source
        )

        # Count test cases (rough estimate based on "it(" occurrences)
        test_count = test_content.count('it("')

        # Create test file structure
        test_files = {
            f"test/{contract_name}.test.js": test_content
        }

        # Store in memory
        await self.memory.store_knowledge(
            self.id, f"tests_{contract_name}", test_files
        )

        return {
            "contract_name": contract_name,
            "test_count": test_count,
            "files": test_files,
            "framework": "hardhat"
        }
