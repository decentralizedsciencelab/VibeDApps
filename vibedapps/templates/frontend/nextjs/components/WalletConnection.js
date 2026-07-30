import React from 'react';
import { useWeb3 } from '@/contexts/Web3Context';

function WalletConnection() {
  const { account, isConnected, connectWallet, disconnectWallet, networkId, error } = useWeb3();
  
  // Map network IDs to names
  const networkNames = {
    1: 'Ethereum Mainnet',
    5: 'Goerli Testnet',
    11155111: 'Sepolia Testnet',
    137: 'Polygon Mainnet',
    80001: 'Mumbai Testnet',
    // Add more networks as needed
  };
  
  // Format account address for display
  const formatAddress = (address) => {
    if (!address) return '';
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };
  
  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold mb-4">Wallet Connection</h2>
      
      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
          {error}
        </div>
      )}
      
      {isConnected ? (
        <div>
          <div className="mb-4">
            <div className="flex items-center mb-2">
              <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
              <span className="font-medium">Connected</span>
            </div>
            <p className="text-gray-600">
              Account: {formatAddress(account)}
            </p>
            <p className="text-gray-600">
              Network: {networkNames[networkId] || `Chain ID: ${networkId}`}
            </p>
          </div>
          
          <button
            onClick={disconnectWallet}
            className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md"
          >
            Disconnect
          </button>
        </div>
      ) : (
        <div>
          <p className="mb-4 text-gray-600">
            Connect your wallet to interact with this DApp.
          </p>
          
          <button
            onClick={connectWallet}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md"
          >
            Connect Wallet
          </button>
        </div>
      )}
    </div>
  );
}

export default WalletConnection;
