<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-8 text-center">Welcome to Our DApp</h1>
    
    <div v-if="error" class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-8" role="alert">
      <p>{{ error }}</p>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div class="bg-white p-6 rounded-lg shadow-md">
        <h2 class="text-xl font-semibold mb-4">Connection Status</h2>
        <template v-if="isConnected">
          <div>
            <p class="text-green-600 font-medium">Connected</p>
            <p class="text-gray-600 mt-2">Account: {{ account }}</p>
          </div>
        </template>
        <template v-else>
          <p class="text-yellow-600">Wallet not connected. Please connect your wallet to use the DApp.</p>
        </template>
      </div>
      
      <div class="bg-white p-6 rounded-lg shadow-md">
        <h2 class="text-xl font-semibold mb-4">Contract Interaction</h2>
        <template v-if="isConnected">
          <div>
            <p class="mb-4">
              Current Value: {{ loading ? 'Loading...' : contractValue !== null ? contractValue : 'N/A' }}
            </p>
            
            <div class="mt-4">
              <button 
                @click="updateContractValue(42)"
                :disabled="loading"
                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:opacity-50"
              >
                {{ loading ? 'Processing...' : 'Update Value' }}
              </button>
            </div>
          </div>
        </template>
        <template v-else>
          <p class="text-gray-600">Connect your wallet to interact with the contract.</p>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'

export default {
  name: 'HomeView',
  data() {
    return {
      contractValue: null,
      loading: false
    }
  },
  computed: {
    ...mapState('web3', ['account', 'isConnected', 'error'])
  },
  methods: {
    ...mapActions('web3', ['readContract', 'writeContract']),
    async fetchContractValue() {
      this.loading = true;
      try {
        // Replace 'getValue' with actual contract method
        const value = await this.readContract({ method: 'getValue' });
        this.contractValue = value;
      } catch (error) {
        console.error('Error fetching value:', error);
      } finally {
        this.loading = false;
      }
    },
    async updateContractValue(newValue) {
      this.loading = true;
      try {
        // Replace 'setValue' with actual contract method
        await this.writeContract({ method: 'setValue', args: [newValue] });
        await this.fetchContractValue();
      } catch (error) {
        console.error('Error updating value:', error);
      } finally {
        this.loading = false;
      }
    }
  },
  mounted() {
    if (this.isConnected) {
      this.fetchContractValue();
    }
  },
  watch: {
    isConnected(newVal) {
      if (newVal) {
        this.fetchContractValue();
      }
    }
  }
}
</script>
