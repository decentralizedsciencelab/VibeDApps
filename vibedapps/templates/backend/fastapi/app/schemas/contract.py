from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class ContractInfo(BaseModel):
    """Contract information schema"""
    address: str
    chain_id: int
    current_block: int

class TransactionResult(BaseModel):
    """Transaction result schema"""
    transaction_hash: str
    block_number: int
    gas_used: int
    status: int = Field(..., description="1 for success, 0 for failure")

class EventData(BaseModel):
    """Event data schema"""
    transaction_hash: str
    block_number: int
    args: Dict[str, Any]

class EventList(BaseModel):
    """Event list schema"""
    events: List[EventData]
