from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os

app = FastAPI(title="TrustGuard AI API")

class VerifyRequest(BaseModel):
    text: str
    context_url: Optional[str] = None

class ClaimStatus(BaseModel):
    claim: str
    status: str # "verified", "misleading", "hallucination", "unverifiable"
    source: Optional[str] = None
    confidence: float

@app.get("/")
def read_root():
    return {"message": "TrustGuard AI Backend is Running"}

@app.post("/api/verify", response_model=List[ClaimStatus])
async def verify_claims(request: VerifyRequest):
    # Placeholder logic
    # 1. Extract Claims (simulated)
    # 2. Search (simulated)
    # 3. Verify (simulated)
    
    return [
        {
            "claim": "Simulation: The extracted claim from text.",
            "status": "unverifiable",
            "source": "Process not implemented yet",
            "confidence": 0.0
        }
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
