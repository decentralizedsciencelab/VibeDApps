require('dotenv').config();
const { ethers } = require('ethers');
const fs = require('fs');

// Contract ABI
const contractAbi = JSON.parse(fs.readFileSync('./contractABI.json', 'utf8'));

// Contract address
const contractAddress = process.env.CONTRACT_ADDRESS;

// Network RPC URL
const rpcUrl = process.env.RPC_URL;

// Provider
const provider = new ethers.JsonRpcProvider(rpcUrl);

// Contract instance
const contract = new ethers.Contract(contractAddress, contractAbi, provider);

// Example: Read from contract
async function readContract() {
  try {
    // Replace with actual contract method
    // const value = await contract.getValue();
    // console.log('Contract value:', value.toString());
    console.log('Reading from contract...');
  } catch (error) {
    console.error('Error reading from contract:', error);
  }
}

// Example: Write to contract
async function writeContract() {
  try {
    // Private key for signing transactions
    const privateKey = process.env.PRIVATE_KEY;
    
    if (!privateKey) {
      throw new Error('PRIVATE_KEY not set in .env file');
    }
    
    // Create wallet
    const wallet = new ethers.Wallet(privateKey, provider);
    
    // Contract with signer
    const contractWithSigner = contract.connect(wallet);
    
    // Replace with actual contract method
    // const tx = await contractWithSigner.setValue(42);
    // console.log('Transaction sent:', tx.hash);
    // 
    // const receipt = await tx.wait();
    // console.log('Transaction confirmed in block:', receipt.blockNumber);
    console.log('Writing to contract...');
  } catch (error) {
    console.error('Error writing to contract:', error);
  }
}

// Example: Listen for events
function listenForEvents() {
  try {
    // Replace with actual contract event
    // contract.on('ValueChanged', (oldValue, newValue, event) => {
    //   console.log(`Value changed from ${oldValue} to ${newValue}`);
    //   console.log('Event:', event);
    // });
    console.log('Listening for events...');
  } catch (error) {
    console.error('Error listening for events:', error);
  }
}

// Main function
async function main() {
  console.log('Starting minimal DApp backend...');
  console.log('Contract address:', contractAddress);
  console.log('Network:', rpcUrl);
  
  // Uncomment to run examples
  // await readContract();
  // await writeContract();
  // listenForEvents();
}

main().catch(console.error);
