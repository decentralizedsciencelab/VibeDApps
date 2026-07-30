import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load contract ABI
with open('contract_abi.json', 'r') as f:
    contract_abi = json.load(f)

# Web3 configuration
RPC_URL = os.getenv('RPC_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

# Initialize Web3
w3 = Web3(HTTPProvider(RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Required for some networks like Polygon

# Check if connected
if not w3.is_connected():
    raise Exception("Not connected to Ethereum node")

# Contract instance
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'connected': w3.is_connected(),
        'chain_id': w3.eth.chain_id
    })

@app.route('/api/contract/info', methods=['GET'])
def get_contract_info():
    """Get contract information"""
    try:
        # Basic contract info
        contract_info = {
            'address': CONTRACT_ADDRESS,
            'network': {
                'chain_id': w3.eth.chain_id,
                'current_block': w3.eth.block_number
            }
        }
        
        return jsonify({'success': True, 'data': contract_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contract/read/<method>', methods=['GET'])
def read_contract(method):
    """Read data from the contract"""
    try:
        # Check if method exists
        if not hasattr(contract.functions, method):
            return jsonify({
                'success': False,
                'error': f'Method {method} does not exist on the contract'
            }), 400
        
        # Parse args if provided
        args = []
        if 'args' in request.args:
            args = json.loads(request.args.get('args'))
        
        # Call the method
        contract_method = getattr(contract.functions, method)
        result = contract_method(*args).call()
        
        # Format result (handle tuples, lists, etc.)
        if isinstance(result, (list, tuple)):
            result = list(result)
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contract/write/<method>', methods=['POST'])
def write_contract(method):
    """Write data to the contract"""
    try:
        data = request.json
        args = data.get('args', [])
        
        # Check if method exists
        if not hasattr(contract.functions, method):
            return jsonify({
                'success': False, 
                'error': f'Method {method} does not exist on the contract'
            }), 400
        
        # Check if private key is configured
        if not PRIVATE_KEY:
            return jsonify({
                'success': False, 
                'error': 'Private key not configured'
            }), 500
        
        # Get account from private key
        account = w3.eth.account.from_key(PRIVATE_KEY)
        
        # Build transaction
        contract_method = getattr(contract.functions, method)
        transaction = contract_method(*args).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 2000000,  # Gas limit
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id,
        })
        
        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        return jsonify({
            'success': True, 
            'data': {
                'transaction_hash': receipt['transactionHash'].hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed'],
                'status': receipt['status']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/status', methods=['GET'])
def get_network_status():
    """Get network status"""
    try:
        status = {
            'connected': w3.is_connected(),
            'chain_id': w3.eth.chain_id,
            'current_block': w3.eth.block_number,
            'gas_price': w3.eth.gas_price,
            'is_syncing': w3.eth.syncing
        }
        
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True', host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
