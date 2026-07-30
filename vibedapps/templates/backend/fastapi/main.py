import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

# Load modules
from app.routers import contract, network
from app.core.config import settings

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(contract.router, prefix="/api/contract", tags=["contract"])
app.include_router(network.router, prefix="/api/network", tags=["network"])

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    from app.core.blockchain import get_web3
    
    w3 = get_web3()
    
    return {
        "status": "healthy",
        "blockchain": {
            "connected": w3.is_connected(),
            "chain_id": w3.eth.chain_id,
            "latest_block": w3.eth.block_number
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
