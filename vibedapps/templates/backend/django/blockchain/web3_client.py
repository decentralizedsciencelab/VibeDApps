from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import json
import os

class Web3Client:
    """Client for interacting with the blockchain"""
    
    def __init__(self, rpc_url, contract_address, private_key=None):
        """Initialize Web3 client"""
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.private_key = private_key
        
        # Connect to network
        self.w3 = Web3(HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Load contract ABI
        current_dir = os.path.dirname(os.path.abspath(__file__))
        abi_path = os.path.join(current_dir, 'contract_abi.json')
        
        with open(abi_path, 'r') as f:
            self.contract_abi = json.load(f)
        
        # Create contract instance
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=self.contract_abi
        )
        
        # Create account from private key if provided
        self.account = None
        if private_key:
            self.account = self.w3.eth.account.from_key(private_key)
    
    def is_connected(self):
        """Check if connected to the blockchain"""
        return self.w3.is_connected()
    
    def get_address(self):
        """Get the address of the account"""
        if self.account:
            return self.account.address
        return None
    
    def get_contract_info(self):
        """Get contract information"""
        return {
            'address': self.contract_address,
            'network': {
                'chain_id': self.w3.eth.chain_id,
                'current_block': self.w3.eth.block_number,
                'connected': self.is_connected()
            }
        }
    
    def read_contract(self, method, args=None):
        """Read data from the contract"""
        if args is None:
            args = []
        
        # Check if method exists
        if not hasattr(self.contract.functions, method):
            raise ValueError(f"Method {method} does not exist on the contract")
        
        # Call the method
        method_func = getattr(self.contract.functions, method)
        result = method_func(*args).call()
        
        return result
    
    def write_contract(self, method, args=None):
        """Write data to the contract"""
        if args is None:
            args = []
        
        if not self.private_key:
            raise ValueError("Private key not provided")
        
        # Check if method exists
        if not hasattr(self.contract.functions, method):
            raise ValueError(f"Method {method} does not exist on the contract")
        
        # Build transaction
        method_func = getattr(self.contract.functions, method)
        transaction = method_func(*args).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 2000000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })
        
        # Sign and send transaction
        signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Wait for receipt
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)
    
    def get_events(self, event_name, from_block=0, to_block='latest', filters=None):
        """Get contract events"""
        if filters is None:
            filters = {}
        
        # Check if event exists
        if not hasattr(self.contract.events, event_name):
            raise ValueError(f"Event {event_name} does not exist on the contract")
        
        # Create event filter
        event_filter = getattr(self.contract.events, event_name).create_filter(
            fromBlock=from_block,
            toBlock=to_block,
            argument_filters=filters
        )
        
        # Get and format events
        events = []
        for event in event_filter.get_all_entries():
            formatted_event = {
                'transaction_hash': event['transactionHash'].hex(),
                'block_number': event['blockNumber'],
                'args': dict(event['args'])
            }
            events.append(formatted_event)
        
        return events
    
    def get_network_status(self):
        """Get network status"""
        return {
            'chain_id': self.w3.eth.chain_id,
            'current_block': self.w3.eth.block_number,
            'gas_price': str(self.w3.eth.gas_price),
            'is_syncing': self.w3.eth.syncing is not False,
            'is_connected': self.is_connected()
        }
    
    def get_gas_price(self):
        """Get current gas price"""
        gas_price = self.w3.eth.gas_price
        
        # Check if EIP-1559 is supported
        try:
            block = self.w3.eth.get_block('latest')
            base_fee = block.get('baseFeePerGas')
            max_priority_fee = self.w3.eth.max_priority_fee
        except (KeyError, AttributeError):
            base_fee = None
            max_priority_fee = None
        
        return {
            'gas_price_wei': str(gas_price),
            'gas_price_gwei': self.w3.from_wei(gas_price, 'gwei'),
            'base_fee_per_gas': str(base_fee) if base_fee else None,
            'max_priority_fee_per_gas': str(max_priority_fee) if max_priority_fee else None
        }
    
    def get_block_info(self, block_identifier):
        """Get block information"""
        block = self.w3.eth.get_block(block_identifier)
        
        return {
            'block_number': block['number'],
            'block_hash': block['hash'].hex(),
            'timestamp': block['timestamp'],
            'transactions_count': len(block['transactions']),
            'gas_used': block['gasUsed'],
            'gas_limit': block['gasLimit'],
            'parent_hash': block['parentHash'].hex(),
            'miner': block['miner']
        }
