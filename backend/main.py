from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from dotenv import load_dotenv
import json
import uuid
import time

load_dotenv()

app = FastAPI(title="TrustGuard AI API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3-flash-preview')

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

def search_web(query: str) -> dict:
    """Searches DuckDuckGo and returns the first result."""
    try:
        with DDGS() as ddgs:
            # Add a small delay or retry logic if needed, but DDGS is usually fine
            results = list(ddgs.text(query, max_results=3))
            if results:
                # Try to find the best match or just return the first
                return {
                    "title": results[0].get('title', 'No Title'),
                    "body": results[0].get('body', 'No Content'),
                    "href": results[0].get('href', '#')
                }
    except Exception as e:
        print(f"Search Error for query '{query}': {e}")
    return {}

@app.get("/")
def read_root():
    return {"message": "TrustGuard AI Backend is Running"}

def clean_json_response(text: str) -> str:
    """Cleans the response text from the LLM to ensure it's valid JSON."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    # Remove any leading/trailing non-JSON characters
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx+1]
    
    return text

@app.post("/api/verify", response_model=VerificationResponse)
async def verify_claims(request: VerifyRequest):
    if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "Paste_Your_Google_Gemini_Key_Here":
         # Mock response for demonstration if API key is missing
         return VerificationResponse(
             claims=[
                 ClaimStatus(
                     id=str(uuid.uuid4()),
                     text="The Great Wall of China is visible from the moon.",
                     status="hallucinated",
                     confidence=95.0,
                     explanation="This is a common myth. The Great Wall is not visible to the naked eye from the moon."
                 ),
                 ClaimStatus(
                     id=str(uuid.uuid4()),
                     text="Water boils at 100 degrees Celsius at sea level.",
                     status="verified",
                     confidence=99.0,
                     source="National Institute of Standards and Technology",
                     sourceUrl="https://www.nist.gov/",
                     explanation="This is a well-established scientific fact."
                 )
             ],
             citations=[
                 CitationStatus(
                     id=str(uuid.uuid4()),
                     text="NASA (2023) Lunar Visibility Report",
                     exists=False,
                     checkingStatus="complete"
                 )
             ],
             overallScore=50
         )

    # Step 1: Extract Claims and Citations
    extraction_prompt = f"""
    Analyze the following text and extract:
    1. Key factual claims (dates, facts, numbers, quotes).
    2. Any citations or references mentioned (papers, journals, authors).
    
    Return ONLY a JSON object with this structure:
    {{
        "claims": ["claim 1", "claim 2"],
        "citations": ["citation 1", "citation 2"]
    }}
    
    Text: "{request.text}"
    """
    
    try:
        extraction_response = model.generate_content(extraction_prompt)
        if not extraction_response.text:
            raise ValueError("Empty response from model")
        resp_text = clean_json_response(extraction_response.text)
        extracted_data = json.loads(resp_text)
        claims_list = extracted_data.get("claims", [])
        citations_list = extracted_data.get("citations", [])
    except Exception as e:
        print(f"Extraction Error: {e}")
        # Fallback to simple split if JSON fails
        claims_list = [line.strip() for line in request.text.split('.') if len(line.strip()) > 20][:3]
        citations_list = []

    verified_claims = []
    verified_citations = []

    # Step 2: Verify Claims
    for claim_text in claims_list:
        time.sleep(1) # Small delay to avoid rate limiting
        try:
            search_result = search_web(claim_text)
            evidence = f"Source: {search_result.get('title')} - {search_result.get('body')} (URL: {search_result.get('href')})" if search_result else "No evidence found."
            
            verification_prompt = f"""
            You are a Fact Checker. 
            Claim: "{claim_text}"
            Evidence from Search: "{evidence}"
            
            Task: Determine verification status based on the evidence.
            Status options: "verified", "uncertain", "hallucinated".
            
            Return ONLY a JSON object with this structure:
            {{ 
                "status": "verified" | "uncertain" | "hallucinated", 
                "confidence": 0.0-1.0, 
                "explanation": "Short explanation of why this status was chosen" 
            }}
            """
            
            verification_resp = model.generate_content(verification_prompt)
            if not verification_resp.text:
                raise ValueError("Empty verification response")
                
            v_text = clean_json_response(verification_resp.text)
            data = json.loads(v_text)
            
            verified_claims.append(ClaimStatus(
                id=str(uuid.uuid4()),
                text=claim_text,
                status=data.get("status", "uncertain"),
                confidence=data.get("confidence", 0.5) * 100,
                source=search_result.get("title") if search_result else None,
                sourceUrl=search_result.get("href") if search_result else None,
                explanation=data.get("explanation", "")
            ))
        except Exception as e:
            print(f"Claim Verification Error for '{claim_text}': {e}")
            verified_claims.append(ClaimStatus(
                id=str(uuid.uuid4()),
                text=claim_text,
                status="uncertain",
                confidence=50.0,
                explanation=f"Verification failed: {str(e)}"
            ))

    # Step 3: Verify Citations
    for cit_text in citations_list:
        time.sleep(0.5) # Small delay
        search_result = search_web(cit_text)
        exists = True if search_result else False
        
        verified_citations.append(CitationStatus(
            id=str(uuid.uuid4()),
            text=cit_text,
            exists=exists,
            url=search_result.get("href") if search_result else None,
            checkingStatus="complete"
        ))

    # Calculate Overall Score
    if not verified_claims:
        overall_score = 100
    else:
        verified_count = sum(1 for c in verified_claims if c.status == "verified")
        overall_score = int((verified_count / len(verified_claims)) * 100)

    return VerificationResponse(
        claims=verified_claims,
        citations=verified_citations,
        overallScore=overall_score
    )

