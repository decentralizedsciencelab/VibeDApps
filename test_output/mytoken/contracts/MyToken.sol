// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MyToken
 * @dev Implementation of the MyToken ERC20 token with minting and burning capabilities.
 */
contract MyToken is ERC20, ERC20Burnable, Ownable {
    /**
     * @dev Constructor that mints an initial supply of tokens to the deployer.
     * @param initialSupply The initial supply of tokens in whole units (not considering decimals).
     */
    constructor(uint256 initialSupply) ERC20("MyToken", "MyT") {
        _mint(msg.sender, initialSupply * 10 ** decimals());
    }

    /**
     * @dev Mints new tokens and assigns them to the specified account.
     * Can only be called by the contract owner.
     * @param account The account to receive the minted tokens.
     * @param amount The amount of tokens to mint, in whole units (not considering decimals).
     */
    function mint(address account, uint256 amount) external onlyOwner {
        _mint(account, amount * 10 ** decimals());
    }

    /**
     * @dev Burns a specific amount of tokens from the caller's account.
     * @param amount The amount of tokens to burn, in whole units (not considering decimals).
     */
    function burn(uint256 amount) public override {
        super.burn(amount * 10 ** decimals());
    }

    /**
     * @dev Burns a specific amount of tokens from a specified account, deducting from the caller's allowance.
     * Can only be called by the account owner or an approved spender.
     * @param account The account whose tokens will be burned.
     * @param amount The amount of tokens to burn, in whole units (not considering decimals).
     */
    function burnFrom(address account, uint256 amount) public override {
        super.burnFrom(account, amount * 10 ** decimals());
    }
}
```

This smart contract implements an ERC20 token named "MyToken" with minting and burning capabilities. It uses OpenZeppelin's ERC20, ERC20Burnable, and Ownable contracts to ensure security and best practices. The contract includes functions for minting new tokens (restricted to the owner) and burning tokens (available to any token holder).