from pydantic import BaseModel
from typing import Optional

class NetworkStatus(BaseModel):
    """Network status schema"""
    chain_id: int
    current_block: int
    is_syncing: bool
    is_connected: bool

class GasPrice(BaseModel):
    """Gas price schema"""
    gas_price_wei: str
    gas_price_gwei: float
    base_fee_per_gas: Optional[str] = None
    max_priority_fee_per_gas: Optional[str] = None

class BlockInfo(BaseModel):
    """Block information schema"""
    block_number: int
    block_hash: str
    timestamp: int
    transactions_count: int
    gas_used: int
    gas_limit: int
    parent_hash: str
    miner: str
