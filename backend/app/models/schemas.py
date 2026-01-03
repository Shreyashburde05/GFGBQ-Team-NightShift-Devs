from pydantic import BaseModel
from typing import List, Optional

class VerifyRequest(BaseModel):
    text: str
    context_url: Optional[str] = None

class ClaimStatus(BaseModel):
    id: str
    text: str
    status: str # "verified", "uncertain", "hallucinated"
    confidence: float
    source: Optional[str] = None
    sourceUrl: Optional[str] = None
    explanation: Optional[str] = None

class CitationStatus(BaseModel):
    id: str
    text: str
    exists: Optional[bool] = None
    url: Optional[str] = None
    checkingStatus: str = "complete"

class VerificationResponse(BaseModel):
    claims: List[ClaimStatus]
    citations: List[CitationStatus]
    overallScore: int
