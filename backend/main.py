<<<<<<< HEAD
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router

app = FastAPI(title="TrustGuard AI API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router. Prefix /api is used in frontend, but check if original had it.
# Original: @app.post("/api/verify"...)
# So we should prefix here or in router.
# Router has @router.post("/verify")
# So we need to include with prefix="/api".
app.include_router(router, prefix="/api")
=======
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TrustGuard AI API")

# Configure Gemini
# NOTE: User needs to set GEMINI_API_KEY in .env or environment variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel('gemini-1.5-flash')

class VerifyRequest(BaseModel):
    text: str
    context_url: Optional[str] = None

class ClaimStatus(BaseModel):
    claim: str
    status: str # "verified", "misleading", "hallucination", "unverifiable"
    source: Optional[str] = None
    confidence: float
    reasoning: Optional[str] = None

def search_web(query: str) -> str:
    """Searches DuckDuckGo and returns the first result snippet."""
    try:
        results = DDGS().text(query, max_results=1)
        if results:
            return f"Source: {results[0]['title']} - {results[0]['body']} (URL: {results[0]['href']})"
    except Exception as e:
        print(f"Search Error: {e}")
    return "No search results found."
>>>>>>> 9233c0b2173e78e87f4038743812522fb3b03b15

@app.get("/")
def read_root():
    return {"message": "TrustGuard AI Backend is Running"}
<<<<<<< HEAD
=======

@app.post("/api/verify", response_model=List[ClaimStatus])
async def verify_claims(request: VerifyRequest):
    if not os.getenv("GEMINI_API_KEY"):
         raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")

    # Step 1: Extract Claims
    extraction_prompt = f"""
    Analyze the following text and extract the key factual claims that need verification.
    Return ONLY a raw list of strings, one per line. No bullets, no numbering.
    Text: "{request.text}"
    """
    try:
        extraction_response = model.generate_content(extraction_prompt)
        claims = [line.strip() for line in extraction_response.text.strip().split('\n') if line.strip()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claim extraction failed: {str(e)}")

    verified_results = []

    # Step 2 & 3: Search and Verify each claim
    for claim in claims:
        # Search for evidence
        search_result = search_web(claim)
        
        # Verify with Gemini
        verification_prompt = f"""
        You are a Fact Checker. 
        Claim: "{claim}"
        Evidence from Search: "{search_result}"
        
        Task: verification status of the claim based on the evidence.
        Status options: "verified" (true), "misleading" (mostly true but needs context), "hallucination" (false or not present in evidence), "unverifiable" (no evidence found).
        
        Return JSON format: {{ "status": "...", "confidence": 0.0-1.0, "reasoning": "..." }}
        """
        
        try:
            # Enforce JSON response if possible, or parse carefully
            # Gemini 1.5 Flash supports JSON mode but for simplicity we'll just ask for text and assume it behaves or use regex if needed.
            # Ideally use response_schema if using updated SDK, but let's trust the prompt for now or use string parsing.
            verification_resp = model.generate_content(verification_prompt)
            # Simple string cleanup to parse typical JSON-like output
            response_text = verification_resp.text.strip().replace("```json", "").replace("```", "")
            import json
            data = json.loads(response_text)
            
            verified_results.append(ClaimStatus(
                claim=claim,
                status=data.get("status", "unverifiable"),
                source=search_result if "Source:" in search_result else None,
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", "")
            ))
        except Exception as e:
            # Fallback if AI fails or JSON parse error
            verified_results.append(ClaimStatus(
                claim=claim,
                status="unverifiable",
                source=None,
                confidence=0.0,
                reasoning=f"Verification verification error: {str(e)}"
            ))

    return verified_results

>>>>>>> 9233c0b2173e78e87f4038743812522fb3b03b15
