// Interaction script
const hre = require("hardhat");

async function main() {
  const [signer] = await hre.ethers.getSigners();
  console.log("Interacting with contracts using account:", signer.address);

  // Get the contract instance
  const contractAddress = process.env.CONTRACT_ADDRESS;
  if (!contractAddress) {
    throw new Error("CONTRACT_ADDRESS environment variable not set");
  }

  const Contract = await hre.ethers.getContractFactory("MyContract");
  const contract = Contract.attach(contractAddress);

  // Example: Read from contract
  console.log("Reading from contract...");
  // Replace with actual contract method
  // const value = await contract.getValue();
  // console.log("Value:", value.toString());

  // Example: Write to contract
  console.log("Writing to contract...");
  // Replace with actual contract method
  // const tx = await contract.setValue(42);
  // await tx.wait();
  // console.log("Transaction hash:", tx.hash);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
