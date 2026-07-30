from fastapi import APIRouter, HTTPException, Query, Body
from typing import Any, Dict, List, Optional
import json

from app.core.blockchain import get_web3, get_contract, send_transaction
from app.schemas.contract import ContractInfo, TransactionResult

router = APIRouter()

@router.get("/info", response_model=ContractInfo)
async def get_contract_info():
    """Get contract information"""
    try:
        w3 = get_web3()
        contract = get_contract()
        
        return {
            "address": contract.address,
            "chain_id": w3.eth.chain_id,
            "current_block": w3.eth.block_number
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/read/{method}")
async def read_contract(method: str, args: Optional[str] = Query(None)):
    """Read data from the contract"""
    try:
        contract = get_contract()
        
        # Check if method exists
        if not hasattr(contract.functions, method):
            raise HTTPException(
                status_code=400,
                detail=f"Method {method} does not exist on the contract"
            )
        
        # Parse args if provided
        arg_list = []
        if args:
            arg_list = json.loads(args)
        
        # Call the method
        contract_method = getattr(contract.functions, method)
        result = contract_method(*arg_list).call()
        
        # Format result (handle tuples, lists, etc.)
        if isinstance(result, (list, tuple)):
            result = list(result)
        
        return {"result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/write/{method}", response_model=TransactionResult)
async def write_contract(method: str, args: List[Any] = Body(...)):
    """Write data to the contract"""
    try:
        contract = get_contract()
        
        # Check if method exists
        if not hasattr(contract.functions, method):
            raise HTTPException(
                status_code=400,
                detail=f"Method {method} does not exist on the contract"
            )
        
        # Build function call
        contract_method = getattr(contract.functions, method)
        function_call = contract_method(*args)
        
        # Send transaction
        receipt = send_transaction(function_call)
        
        return {
            "transaction_hash": receipt["transactionHash"].hex(),
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "status": receipt["status"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events/{event_name}")
async def get_events(
    event_name: str,
    from_block: int = Query(0),
    to_block: str = Query("latest"),
    filters: Optional[str] = Query(None)
):
    """Get contract events"""
    try:
        w3 = get_web3()
        contract = get_contract()
        
        # Check if event exists
        if not hasattr(contract.events, event_name):
            raise HTTPException(
                status_code=400, 
                detail=f"Event {event_name} does not exist on the contract"
            )
        
        # Parse filters if provided
        filter_dict = {}
        if filters:
            filter_dict = json.loads(filters)
        
        # Create event filter
        event_filter = getattr(contract.events, event_name).create_filter(
            fromBlock=from_block,
            toBlock=to_block,
            argument_filters=filter_dict
        )
        
        # Get events
        events = event_filter.get_all_entries()
        
        # Format events
        formatted_events = []
        for event in events:
            formatted_event = {
                "transaction_hash": event["transactionHash"].hex(),
                "block_number": event["blockNumber"],
                "args": dict(event["args"])
            }
            formatted_events.append(formatted_event)
        
        return {"events": formatted_events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
