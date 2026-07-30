from fastapi import APIRouter, HTTPException, Path
from typing import Optional

from app.core.blockchain import get_web3
from app.schemas.network import NetworkStatus, GasPrice, BlockInfo

router = APIRouter()

@router.get("/status", response_model=NetworkStatus)
async def get_network_status():
    """Get network status"""
    try:
        w3 = get_web3()
        
        return {
            "chain_id": w3.eth.chain_id,
            "current_block": w3.eth.block_number,
            "is_syncing": w3.eth.syncing is not False,
            "is_connected": w3.is_connected()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gas-price", response_model=GasPrice)
async def get_gas_price():
    """Get current gas price"""
    try:
        w3 = get_web3()
        
        # Get fee data
        gas_price = w3.eth.gas_price
        
        # Check if EIP-1559 is supported
        try:
            base_fee = w3.eth.get_block('latest')['baseFeePerGas']
            max_priority_fee = w3.eth.max_priority_fee
        except (KeyError, AttributeError):
            base_fee = None
            max_priority_fee = None
        
        return {
            "gas_price_wei": str(gas_price),
            "gas_price_gwei": w3.from_wei(gas_price, 'gwei'),
            "base_fee_per_gas": str(base_fee) if base_fee else None,
            "max_priority_fee_per_gas": str(max_priority_fee) if max_priority_fee else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/block/{block_identifier}", response_model=BlockInfo)
async def get_block_info(block_identifier: str = Path(..., description="Block number or 'latest'")):
    """Get block information"""
    try:
        w3 = get_web3()
        
        # Convert to int if not 'latest'
        if block_identifier != 'latest':
            try:
                block_identifier = int(block_identifier)
            except ValueError:
                raise HTTPException(status_code=400, detail="Block identifier must be an integer or 'latest'")
        
        block = w3.eth.get_block(block_identifier)
        
        return {
            "block_number": block.number,
            "block_hash": block.hash.hex(),
            "timestamp": block.timestamp,
            "transactions_count": len(block.transactions),
            "gas_used": block.gasUsed,
            "gas_limit": block.gasLimit,
            "parent_hash": block.parentHash.hex(),
            "miner": block.miner
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
