from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import json
import os
from .config import settings

# Web3 instance
_web3 = None

def get_web3():
    """Get or create Web3 instance"""
    global _web3
    
    if _web3 is None:
        _web3 = Web3(HTTPProvider(settings.RPC_URL))
        _web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    return _web3

def get_contract():
    """Get contract instance"""
    w3 = get_web3()
    
    # Load ABI
    with open('app/core/contract_abi.json', 'r') as f:
        contract_abi = json.load(f)
    
    # Create contract instance
    contract = w3.eth.contract(
        address=settings.CONTRACT_ADDRESS,
        abi=contract_abi
    )
    
    return contract

def send_transaction(function_call):
    """Send a transaction to the blockchain"""
    w3 = get_web3()
    
    if not settings.PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in environment variables")
    
    # Get account from private key
    account = w3.eth.account.from_key(settings.PRIVATE_KEY)
    
    # Build transaction
    transaction = function_call.build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    
    # Sign and send transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, settings.PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    return receipt
