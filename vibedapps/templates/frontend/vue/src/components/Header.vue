<template>
  <header class="bg-gray-800 text-white shadow-md">
    <div class="container mx-auto px-4 py-4 flex justify-between items-center">
      <router-link to="/" class="text-xl font-bold">DApp</router-link>
      
      <nav class="hidden md:flex space-x-6">
        <router-link to="/" class="hover:text-blue-400">Home</router-link>
        <router-link to="/about" class="hover:text-blue-400">About</router-link>
        <!-- Add more navigation links as needed -->
      </nav>
      
      <div>
        <template v-if="isConnected">
          <div class="flex items-center space-x-4">
            <span class="hidden md:inline-block px-4 py-2 bg-gray-700 rounded-full">
              {{ formatAddress(account) }}
            </span>
            <button 
              @click="disconnectWallet"
              class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md"
            >
              Disconnect
            </button>
          </div>
        </template>
        <template v-else>
          <button 
            @click="connectWallet"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md"
          >
            Connect Wallet
          </button>
        </template>
      </div>
    </div>
  </header>
</template>

<script>
import { mapState, mapActions } from 'vuex'

export default {
  name: 'Header',
  computed: {
    ...mapState('web3', ['account', 'isConnected'])
  },
  methods: {
    ...mapActions('web3', ['connectWallet', 'disconnectWallet']),
    formatAddress(address) {
      if (!address) return '';
      return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
    }
  }
}
</script>
