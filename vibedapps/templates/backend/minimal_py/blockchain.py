from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
RPC_URL = os.getenv('RPC_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

# Load ABI from file
def load_contract_abi():
    """Load contract ABI from file"""
    try:
        with open('contract_abi.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: contract_abi.json not found")
        return []

# Initialize Web3
def initialize_web3():
    """Initialize Web3 connection"""
    w3 = Web3(HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    if not w3.is_connected():
        raise Exception("Not connected to Ethereum node")
    
    print(f"Connected to network. Chain ID: {w3.eth.chain_id}")
    return w3

# Get contract instance
def get_contract(w3):
    """Get contract instance"""
    contract_abi = load_contract_abi()
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
    return contract

# Read from contract
def read_contract(contract, method_name, args=None):
    """Read data from contract"""
    if args is None:
        args = []
    
    if not hasattr(contract.functions, method_name):
        raise ValueError(f"Method {method_name} does not exist on the contract")
    
    method = getattr(contract.functions, method_name)
    result = method(*args).call()
    return result

# Write to contract
def write_contract(w3, contract, method_name, args=None):
    """Write data to contract"""
    if args is None:
        args = []
    
    if not PRIVATE_KEY:
        raise ValueError("Private key not provided in .env file")
    
    if not hasattr(contract.functions, method_name):
        raise ValueError(f"Method {method_name} does not exist on the contract")
    
    # Get account from private key
    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"Using account: {account.address}")
    
    # Build transaction
    method = getattr(contract.functions, method_name)
    transaction = method(*args).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    
    # Sign and send transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"Transaction sent: {tx_hash.hex()}")
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Transaction confirmed in block: {receipt['blockNumber']}")
    return receipt

# Listen for events
def listen_for_events(contract, event_name):
    """Listen for contract events"""
    if not hasattr(contract.events, event_name):
        raise ValueError(f"Event {event_name} does not exist on the contract")
    
    event_filter = getattr(contract.events, event_name).create_filter(fromBlock='latest')
    
    print(f"Listening for {event_name} events...")
    while True:
        for event in event_filter.get_new_entries():
            print(f"New event: {event}")

# Main function
def main():
    """Main function"""
    try:
        # Initialize Web3
        w3 = initialize_web3()
        
        # Get contract
        contract = get_contract(w3)
        print(f"Contract loaded at address: {CONTRACT_ADDRESS}")
        
        # Example usage:
        # 1. Read from contract
        # value = read_contract(contract, 'getValue')
        # print(f"Contract value: {value}")
        
        # 2. Write to contract
        # receipt = write_contract(w3, contract, 'setValue', [42])
        # print(f"Transaction status: {'Success' if receipt['status'] == 1 else 'Failed'}")
        
        # 3. Listen for events
        # listen_for_events(contract, 'ValueChanged')
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
