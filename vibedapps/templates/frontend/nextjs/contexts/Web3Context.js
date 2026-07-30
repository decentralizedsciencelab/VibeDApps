import { createContext, useContext, useState, useEffect } from 'react';
import { ethers } from 'ethers';

// Create context
const Web3Context = createContext();

// Contract ABI
const contractABI = {{CONTRACT_ABI}};

// Contract addresses for different networks
const CONTRACT_ADDRESSES = {
  1: '{{CONTRACT_ADDRESS}}', // Ethereum Mainnet
  11155111: '{{CONTRACT_ADDRESS}}', // Sepolia Testnet
  // Add more networks as needed
};

export function Web3Provider({ children }) {
  const [account, setAccount] = useState(null);
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [contract, setContract] = useState(null);
  const [networkId, setNetworkId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  // Initialize provider
  useEffect(() => {
    // Need to check for window because of Next.js SSR
    if (typeof window !== 'undefined' && window.ethereum) {
      const initProvider = async () => {
        try {
          const provider = new ethers.BrowserProvider(window.ethereum);
          setProvider(provider);
          
          // Get network
          const network = await provider.getNetwork();
          setNetworkId(Number(network.chainId));
          
          // Listen for network changes
          window.ethereum.on('chainChanged', (chainId) => {
            window.location.reload();
          });
          
          // Listen for account changes
          window.ethereum.on('accountsChanged', (accounts) => {
            if (accounts.length === 0) {
              // User disconnected
              disconnectWallet();
            } else {
              // Account changed
              setAccount(accounts[0]);
            }
          });
          
          // Check if already connected
          const accounts = await provider.listAccounts();
          if (accounts.length > 0) {
            const account = accounts[0];
            setAccount(account.address);
            
            // Get signer
            const signer = await provider.getSigner();
            setSigner(signer);
            
            // Initialize contract
            const contractAddress = CONTRACT_ADDRESSES[Number(network.chainId)];
            if (contractAddress) {
              const contract = new ethers.Contract(contractAddress, contractABI, signer);
              setContract(contract);
              setIsConnected(true);
            } else {
              setError('Contract not deployed on this network');
            }
          }
        } catch (error) {
          console.error('Error initializing provider:', error);
          setError('Error connecting to blockchain');
        }
      };

      initProvider();
    } else if (typeof window !== 'undefined') {
      setError('Please install MetaMask or another Ethereum wallet');
    }
  }, []);

  // Connect wallet
  const connectWallet = async () => {
    try {
      if (!provider) {
        throw new Error('Provider not initialized');
      }
      
      // Request account access
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      const account = accounts[0];
      setAccount(account);
      
      // Get signer
      const signer = await provider.getSigner();
      setSigner(signer);
      
      // Initialize contract
      const contractAddress = CONTRACT_ADDRESSES[networkId];
      if (contractAddress) {
        const contract = new ethers.Contract(contractAddress, contractABI, signer);
        setContract(contract);
      } else {
        setError('Contract not deployed on this network');
      }
      
      setIsConnected(true);
    } catch (error) {
      console.error('Error connecting wallet:', error);
      setError('Error connecting wallet');
    }
  };

  // Disconnect wallet
  const disconnectWallet = () => {
    setAccount(null);
    setSigner(null);
    setContract(null);
    setIsConnected(false);
  };

  // Read from contract
  const readContract = async (method, args = []) => {
    try {
      if (!contract) {
        throw new Error('Contract not initialized');
      }
      
      return await contract[method](...args);
    } catch (error) {
      console.error(`Error calling ${method}:`, error);
      setError(`Error calling ${method}`);
      throw error;
    }
  };

  // Write to contract
  const writeContract = async (method, args = [], options = {}) => {
    try {
      if (!contract) {
        throw new Error('Contract not initialized');
      }
      
      const tx = await contract[method](...args, options);
      return await tx.wait();
    } catch (error) {
      console.error(`Error calling ${method}:`, error);
      setError(`Error calling ${method}`);
      throw error;
    }
  };

  const value = {
    account,
    provider,
    signer,
    contract,
    networkId,
    isConnected,
    error,
    connectWallet,
    disconnectWallet,
    readContract,
    writeContract,
  };

  return (
    <Web3Context.Provider value={value}>
      {children}
    </Web3Context.Provider>
  );
}

// Hook to use Web3 context
export function useWeb3() {
  return useContext(Web3Context);
}
