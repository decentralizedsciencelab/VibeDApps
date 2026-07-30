// Contract ABI
const contractABI = {{CONTRACT_ABI}};

// Contract addresses for different networks
const CONTRACT_ADDRESSES = {
  1: '{{CONTRACT_ADDRESS}}', // Ethereum Mainnet
  11155111: '{{CONTRACT_ADDRESS}}', // Sepolia Testnet
  // Add more networks as needed
};

// Web3 variables
let provider;
let signer;
let contract;
let currentAccount;
let networkId;

// DOM Elements
const connectButton = document.getElementById('connectButton');
const disconnectButton = document.getElementById('disconnectButton');
const accountInfo = document.getElementById('accountInfo');
const accountAddress = document.getElementById('accountAddress');
const connectionStatus = document.getElementById('connectionStatus');
const contractInteraction = document.getElementById('contractInteraction');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');
const currentYear = document.getElementById('currentYear');

// Set current year in footer
currentYear.textContent = new Date().getFullYear();

// Initialize Web3
async function initWeb3() {
  // Check if MetaMask is installed
  if (window.ethereum) {
    try {
      // Initialize provider
      provider = new ethers.providers.Web3Provider(window.ethereum);
      
      // Get network
      const network = await provider.getNetwork();
      networkId = network.chainId;
      
      // Listen for network changes
      window.ethereum.on('chainChanged', () => {
        window.location.reload();
      });
      
      // Listen for account changes
      window.ethereum.on('accountsChanged', (accounts) => {
        if (accounts.length === 0) {
          // User disconnected
          disconnectWallet();
        } else {
          // Account changed
          currentAccount = accounts[0];
          updateUI();
        }
      });
      
      // Check if already connected
      const accounts = await provider.listAccounts();
      if (accounts.length > 0) {
        currentAccount = accounts[0];
        await connectToContract();
        updateUI();
      }
    } catch (error) {
      console.error('Error initializing Web3:', error);
      showError('Error connecting to blockchain');
    }
  } else {
    showError('Please install MetaMask or another Ethereum wallet');
  }
}

// Connect wallet
async function connectWallet() {
  try {
    if (!provider) {
      await initWeb3();
    }
    
    // Request account access
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    currentAccount = accounts[0];
    
    // Get signer
    signer = provider.getSigner();
    
    // Connect to contract
    await connectToContract();
    
    // Update UI
    updateUI();
  } catch (error) {
    console.error('Error connecting wallet:', error);
    showError('Error connecting wallet');
  }
}

// Disconnect wallet
function disconnectWallet() {
  currentAccount = null;
  signer = null;
  contract = null;
  updateUI();
}

// Connect to contract
async function connectToContract() {
  try {
    const contractAddress = CONTRACT_ADDRESSES[networkId];
    if (contractAddress && signer) {
      contract = new ethers.Contract(contractAddress, contractABI, signer);
    } else if (!contractAddress) {
      showError('Contract not deployed on this network');
    }
  } catch (error) {
    console.error('Error connecting to contract:', error);
    showError('Error connecting to contract');
  }
}

// Format address for display
function formatAddress(address) {
  if (!address) return '';
  return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
}

// Show error message
function showError(message) {
  errorText.textContent = message;
  errorMessage.classList.remove('hidden');
}

// Hide error message
function hideError() {
  errorMessage.classList.add('hidden');
}

// Update UI based on connection status
function updateUI() {
  if (currentAccount) {
    // Connected
    connectButton.classList.add('hidden');
    accountInfo.classList.remove('hidden');
    accountAddress.textContent = formatAddress(currentAccount);
    
    // Update connection status
    connectionStatus.innerHTML = `
      <div>
        <p class="text-green-600 font-medium">Connected</p>
        <p class="text-gray-600 mt-2">Account: ${currentAccount}</p>
        <p class="text-gray-600">Network ID: ${networkId}</p>
      </div>
    `;
    
    // Update contract interaction section
    updateContractSection();
  } else {
    // Not connected
    connectButton.classList.remove('hidden');
    accountInfo.classList.add('hidden');
    
    // Update connection status
    connectionStatus.innerHTML = `
      <p class="text-yellow-600">Wallet not connected. Please connect your wallet to use the DApp.</p>
    `;
    
    // Update contract interaction section
    contractInteraction.innerHTML = `
      <p class="text-gray-600">Connect your wallet to interact with the contract.</p>
    `;
  }
}

// Update contract interaction section
async function updateContractSection() {
  if (!contract) {
    contractInteraction.innerHTML = `
      <p class="text-yellow-600">Contract not available on this network.</p>
    `;
    return;
  }
  
  try {
    // Example: Get value from contract
    // Replace with actual contract method
    let value = 'N/A';
    try {
      if (contract.getValue) {
        value = await contract.getValue();
      }
    } catch (error) {
      console.log('getValue method not available or other error:', error);
    }
    
    contractInteraction.innerHTML = `
      <p class="mb-4">Current Value: ${value}</p>
      
      <div class="mt-4">
        <button 
          id="updateValueBtn"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md"
        >
          Update Value
        </button>
      </div>
    `;
    
    // Add event listener to update button
    document.getElementById('updateValueBtn').addEventListener('click', updateContractValue);
  } catch (error) {
    console.error('Error updating contract section:', error);
    contractInteraction.innerHTML = `
      <p class="text-red-600">Error interacting with contract.</p>
    `;
  }
}

// Example function to update contract value
async function updateContractValue() {
  if (!contract) return;
  
  const updateBtn = document.getElementById('updateValueBtn');
  const originalText = updateBtn.textContent;
  updateBtn.textContent = 'Processing...';
  updateBtn.disabled = true;
  
  try {
    // Replace with actual contract method
    if (contract.setValue) {
      const tx = await contract.setValue(42);
      await tx.wait();
    }
    
    // Update UI
    updateContractSection();
  } catch (error) {
    console.error('Error updating contract value:', error);
    showError('Error updating contract value');
  } finally {
    updateBtn.textContent = originalText;
    updateBtn.disabled = false;
  }
}

// Event listeners
connectButton.addEventListener('click', connectWallet);
disconnectButton.addEventListener('click', disconnectWallet);

// Initialize on page load
window.addEventListener('load', initWeb3);
