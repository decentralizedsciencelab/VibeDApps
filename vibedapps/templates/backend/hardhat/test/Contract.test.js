const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MyContract", function () {
  let contract;
  let owner;
  let addr1;
  let addr2;

  beforeEach(async function () {
    // Get signers
    [owner, addr1, addr2] = await ethers.getSigners();

    // Deploy contract
    const ContractFactory = await ethers.getContractFactory("MyContract");
    contract = await ContractFactory.deploy();
  });

  describe("Deployment", function () {
    it("Should set the right owner", async function () {
      // Replace with actual contract method
      // expect(await contract.owner()).to.equal(owner.address);
    });

    it("Should have the correct initial state", async function () {
      // Add test for initial state
      // expect(await contract.getValue()).to.equal(0);
    });
  });

  describe("Transactions", function () {
    it("Should allow owner to update state", async function () {
      // Replace with actual contract method
      // await contract.setValue(42);
      // expect(await contract.getValue()).to.equal(42);
    });

    it("Should fail when non-owner tries to update state", async function () {
      // Replace with actual contract method
      // await expect(
      //   contract.connect(addr1).setValue(42)
      // ).to.be.revertedWith("Not owner");
    });
  });
});
