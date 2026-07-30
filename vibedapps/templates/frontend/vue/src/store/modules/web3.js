import { ethers } from 'ethers'

// Contract ABI
const contractABI = {{CONTRACT_ABI}};

// Contract addresses for different networks
const CONTRACT_ADDRESSES = {
  1: '{{CONTRACT_ADDRESS}}', // Ethereum Mainnet
  11155111: '{{CONTRACT_ADDRESS}}', // Sepolia Testnet
  // Add more networks as needed
};

const state = {
  account: null,
  provider: null,
  signer: null,
  contract: null,
  networkId: null,
  isConnected: false,
  error: null
};

const mutations = {
  SET_ACCOUNT(state, account) {
    state.account = account;
  },
  SET_PROVIDER(state, provider) {
    state.provider = provider;
  },
  SET_SIGNER(state, signer) {
    state.signer = signer;
  },
  SET_CONTRACT(state, contract) {
    state.contract = contract;
  },
  SET_NETWORK_ID(state, networkId) {
    state.networkId = networkId;
  },
  SET_CONNECTED(state, isConnected) {
    state.isConnected = isConnected;
  },
  SET_ERROR(state, error) {
    state.error = error;
  }
};

const actions = {
  async initProvider({ commit, dispatch }) {
    try {
      if (window.ethereum) {
        const provider = new ethers.BrowserProvider(window.ethereum);
        commit('SET_PROVIDER', provider);
        
        // Get network
        const network = await provider.getNetwork();
        commit('SET_NETWORK_ID', Number(network.chainId));
        
        // Listen for network changes
        window.ethereum.on('chainChanged', () => {
          window.location.reload();
        });
        
        // Check if already connected
        const accounts = await provider.listAccounts();
        if (accounts.length > 0) {
          dispatch('handleAccountsChanged', accounts);
        }
      } else {
        commit('SET_ERROR', 'Please install MetaMask or another Ethereum wallet');
      }
    } catch (error) {
      console.error('Error initializing provider:', error);
      commit('SET_ERROR', 'Error connecting to blockchain');
    }
  },
  
  async handleAccountsChanged({ commit, dispatch, state }, accounts) {
    if (accounts.length === 0) {
      // User disconnected
      dispatch('disconnectWallet');
    } else if (accounts[0] !== state.account) {
      // Account changed
      commit('SET_ACCOUNT', accounts[0]);
      
      // Get signer
      const signer = await state.provider.getSigner();
      commit('SET_SIGNER', signer);
      
      // Initialize contract
      dispatch('initContract');
      
      commit('SET_CONNECTED', true);
    }
  },
  
  async connectWallet({ commit, dispatch, state }) {
    try {
      if (!state.provider) {
        await dispatch('initProvider');
      }
      
      // Request account access
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      dispatch('handleAccountsChanged', accounts);
    } catch (error) {
      console.error('Error connecting wallet:', error);
      commit('SET_ERROR', 'Error connecting wallet');
    }
  },
  
  disconnectWallet({ commit }) {
    commit('SET_ACCOUNT', null);
    commit('SET_SIGNER', null);
    commit('SET_CONTRACT', null);
    commit('SET_CONNECTED', false);
  },
  
  async initContract({ commit, state }) {
    try {
      const contractAddress = CONTRACT_ADDRESSES[state.networkId];
      if (contractAddress && state.signer) {
        const contract = new ethers.Contract(contractAddress, contractABI, state.signer);
        commit('SET_CONTRACT', contract);
      } else if (!contractAddress) {
        commit('SET_ERROR', 'Contract not deployed on this network');
      }
    } catch (error) {
      console.error('Error initializing contract:', error);
      commit('SET_ERROR', 'Error initializing contract');
    }
  },
  
  async readContract({ state }, { method, args = [] }) {
    try {
      if (!state.contract) {
        throw new Error('Contract not initialized');
      }
      
      return await state.contract[method](...args);
    } catch (error) {
      console.error(`Error calling ${method}:`, error);
      throw error;
    }
  },
  
  async writeContract({ state }, { method, args = [], options = {} }) {
    try {
      if (!state.contract) {
        throw new Error('Contract not initialized');
      }
      
      const tx = await state.contract[method](...args, options);
      return await tx.wait();
    } catch (error) {
      console.error(`Error calling ${method}:`, error);
      throw error;
    }
  }
};

const getters = {
  getAccount: state => state.account,
  isConnected: state => state.isConnected,
  getError: state => state.error,
  getNetworkId: state => state.networkId
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
};
