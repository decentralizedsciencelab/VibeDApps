// Deploy script
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer.address);

  // ethers v6: signer.getBalance() was removed; query the provider instead
  // (the rest of this script already targets v6: formatEther/waitForDeployment).
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", hre.ethers.formatEther(balance));

  // Deploy the contract
  const ContractFactory = await hre.ethers.getContractFactory("MyContract");
  const contract = await ContractFactory.deploy();

  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();

  console.log("Contract deployed to:", contractAddress);
  
  // Verify the contract on Etherscan if not on local network
  const network = hre.network.name;
  if (network !== 'hardhat' && network !== 'localhost') {
    console.log('Waiting for block confirmations...');
    // Wait for 6 block confirmations
    await contract.deploymentTransaction().wait(6);
    console.log('Verifying contract...');
    
    try {
      await hre.run('verify:verify', {
        address: contractAddress,
        constructorArguments: [],
      });
      console.log('Contract verified on Etherscan');
    } catch (error) {
      console.error('Error verifying contract:', error);
    }
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
