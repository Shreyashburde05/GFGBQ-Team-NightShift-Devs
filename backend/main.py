from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from duckduckgo_search import DDGS
from dotenv import load_dotenv
import json
import uuid
import time
import asyncio

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

# Gemini Manager for API Key Rotation
class GeminiManager:
    def __init__(self):
        # Support both GEMINI_API_KEY (single) and GEMINI_API_KEYS (comma-separated)
        keys_str = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
        self.keys = [k.strip() for k in keys_str.split(",") if k.strip() and k.strip() != "Paste_Your_Google_Gemini_Key_Here"]
        self.key_cooldowns = {i: 0 for i in range(len(self.keys))}
        self.current_key_index = 0
        self.model = None
        self.refresh_model()

    def refresh_model(self):
        if not self.keys:
            print("Warning: No Gemini API keys found!")
            return
        print(f"Using Gemini API Key #{self.current_key_index + 1}")
        genai.configure(api_key=self.keys[self.current_key_index])
        self.model = genai.GenerativeModel('gemini-3-flash-preview')

    def switch_key(self):
        if len(self.keys) <= 1:
            print(f"No alternative API keys available. Current key index: {self.current_key_index}")
            return False
        
        # Mark current key as on cooldown
        self.key_cooldowns[self.current_key_index] = time.time() + 60
        
        # Find next key not on cooldown
        for _ in range(len(self.keys)):
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            if time.time() > self.key_cooldowns[self.current_key_index]:
                print(f"SWITCHING API KEY: Now using index {self.current_key_index}")
                self.refresh_model()
                return True
        
        print("All API keys are currently rate-limited/on cooldown.")
        return False

gemini_manager = GeminiManager()

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
    print(f"Searching web for: {query[:50]}...")
    try:
        with DDGS() as ddgs:
            # Use a shorter timeout if possible, but DDGS doesn't expose it easily
            # We'll just try to get results quickly
            results = list(ddgs.text(query, max_results=2))
            if results:
                print(f"Found results for: {query[:30]}")
                return {
                    "title": results[0].get('title', 'No Title'),
                    "body": results[0].get('body', 'No Content'),
                    "href": results[0].get('href', '#')
                }
    except Exception as e:
        print(f"Search Error for query '{query}': {e}")
    print(f"No results found for: {query[:30]}")
    return {}

async def search_web_async(query: str) -> dict:
    """Searches DuckDuckGo and returns the first result (Async)."""
    return await asyncio.to_thread(search_web, query)

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

async def verify_single_claim(claim_text: str):
    """Verifies a single claim in parallel with retries."""
    max_retries = 3
    search_result = None
    for attempt in range(max_retries):
        try:
            if search_result is None:
                search_result = await search_web_async(claim_text)
            
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
            
            verification_resp = await gemini_manager.model.generate_content_async(verification_prompt)
            if not verification_resp.text:
                raise ValueError("Empty verification response")
                
            v_text = clean_json_response(verification_resp.text)
            data = json.loads(v_text)
            
            return ClaimStatus(
                id=str(uuid.uuid4()),
                text=claim_text,
                status=data.get("status", "uncertain"),
                confidence=data.get("confidence", 0.5) * 100,
                source=search_result.get("title") if search_result else None,
                sourceUrl=search_result.get("href") if search_result else None,
                explanation=data.get("explanation", "")
            )
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "quota" in err_str or "limit" in err_str or isinstance(e, google_exceptions.ResourceExhausted)
            
            if is_rate_limit and attempt < max_retries - 1:
                # Try switching key if rate limited
                if gemini_manager.switch_key():
                    print(f"Retrying with new API key for '{claim_text[:20]}'. Waiting 2s...")
                    await asyncio.sleep(2)
                    continue
                
                wait_time = (attempt + 1) * 10
                print(f"All keys exhausted. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            
            error_msg = str(e)
            if is_rate_limit:
                error_msg = "Rate limit reached. Please wait a minute or add more API keys to .env"
            
            print(f"Claim Verification Error: {error_msg}")
            return ClaimStatus(
                id=str(uuid.uuid4()),
                text=claim_text,
                status="uncertain",
                confidence=50.0,
                explanation=f"Verification failed: {error_msg}"
            )

async def verify_single_citation(cit_text: str):
    """Verifies a single citation in parallel with retries."""
    max_retries = 3
    search_result = None
    for attempt in range(max_retries):
        try:
            if search_result is None:
                search_result = await search_web_async(cit_text)
            
            citation_prompt = f"""
            You are a Citation Validator.
            Citation: "{cit_text}"
            Search Result: "{search_result.get('title') if search_result else 'No results'}"
            
            Task: Verify if this citation is likely real or fabricated.
            Return ONLY a JSON object:
            {{
                "isReal": true | false,
                "confidence": 0.0-1.0
            }}
            """
            
            citation_resp = await gemini_manager.model.generate_content_async(citation_prompt)
            if not citation_resp.text:
                raise ValueError("Empty citation response")
                
            c_text = clean_json_response(citation_resp.text)
            data = json.loads(c_text)
            
            return CitationStatus(
                id=str(uuid.uuid4()),
                text=cit_text,
                exists=data.get("isReal", False) or (search_result is not None),
                url=search_result.get("href") if search_result else None,
                checkingStatus="complete"
            )
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "quota" in err_str or "limit" in err_str or isinstance(e, google_exceptions.ResourceExhausted)
            
            if is_rate_limit and attempt < max_retries - 1:
                if gemini_manager.switch_key():
                    print(f"Retrying citation with new API key. Waiting 2s...")
                    await asyncio.sleep(2)
                    continue
                
                wait_time = (attempt + 1) * 10
                print(f"All keys exhausted for citation. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
                
            print(f"Citation Verification Error: {e}")
            return CitationStatus(
                id=str(uuid.uuid4()),
                text=cit_text,
                exists=search_result is not None,
                url=search_result.get("href") if search_result else None,
                checkingStatus="complete"
            )

@app.post("/api/verify", response_model=VerificationResponse)
async def verify_claims(request: VerifyRequest):
    print(f"Received verification request for text: {request.text[:50]}...")
    if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "Paste_Your_Google_Gemini_Key_Here":
         # Mock response for demonstration if API key is missing
         print("Using mock response (no API key)")
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
    print("Step 1: Extracting claims and citations...")
    extraction_prompt = f"""
    Analyze the following text and extract:
    1. Key factual claims (dates, facts, numbers, quotes). Limit to the 3 most important claims.
    2. Any citations or references mentioned (papers, journals, authors). Limit to 2.
    
    Return ONLY a JSON object with this structure:
    {{
        "claims": ["claim 1", "claim 2"],
        "citations": ["citation 1", "citation 2"]
    }}
    
    Text: "{request.text}"
    """
    
    claims_list = []
    citations_list = []
    
    for attempt in range(3):
        try:
            if not gemini_manager.model:
                raise ValueError("Gemini model not initialized. Check your API keys.")
                
            extraction_response = await gemini_manager.model.generate_content_async(extraction_prompt)
            if not extraction_response.text:
                raise ValueError("Empty response from model")
            resp_text = clean_json_response(extraction_response.text)
            extracted_data = json.loads(resp_text)
            claims_list = extracted_data.get("claims", [])[:3]
            citations_list = extracted_data.get("citations", [])[:2]
            print(f"Extracted {len(claims_list)} claims and {len(citations_list)} citations.")
            break
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "quota" in err_str or "limit" in err_str or isinstance(e, google_exceptions.ResourceExhausted)
            if is_rate_limit and attempt < 2:
                if gemini_manager.switch_key():
                    print("Switched API key during extraction. Waiting 2s...")
                    await asyncio.sleep(2)
                    continue
                
                wait_time = (attempt + 1) * 10
                print(f"Extraction rate limit hit, all keys exhausted. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            
            error_msg = "Rate limit reached" if is_rate_limit else str(e)
            print(f"Extraction Error: {error_msg}")
            # Fallback to simple split if JSON fails
            claims_list = [line.strip() for line in request.text.split('.') if len(line.strip()) > 20][:2]
            citations_list = []
            print(f"Fallback: Extracted {len(claims_list)} claims.")
            break

    # Step 2 & 3: Verify in Parallel with Concurrency Limit
    print("Step 2 & 3: Verifying claims and citations in parallel...")
    
    semaphore = asyncio.Semaphore(2) # Increased to 2 since we have rotation
    
    async def sem_verify_claim(c):
        async with semaphore:
            await asyncio.sleep(1) # Small delay between requests
            return await verify_single_claim(c)
            
    async def sem_verify_citation(c):
        async with semaphore:
            return await verify_single_citation(c)
    
    claim_tasks = [sem_verify_claim(c) for c in claims_list]
    citation_tasks = [sem_verify_citation(c) for c in citations_list]
    
    results = await asyncio.gather(*claim_tasks, *citation_tasks)
    
    verified_claims = results[:len(claim_tasks)]
    verified_citations = results[len(claim_tasks):]

    # Calculate Overall Score
    if not verified_claims:
        overall_score = 100
    else:
        verified_count = sum(1 for c in verified_claims if c.status == "verified")
        overall_score = int((verified_count / len(verified_claims)) * 100)

    print(f"Verification complete. Overall Score: {overall_score}")
    return VerificationResponse(
        claims=verified_claims,
        citations=verified_citations,
        overallScore=overall_score
    )

