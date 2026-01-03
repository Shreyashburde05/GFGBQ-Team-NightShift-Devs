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
from groq import Groq
try:
    from tavily import TavilyClient
    tavily_available = True
except ImportError:
    tavily_available = False

load_dotenv()

app = FastAPI(title="TrustGuard AI API")

# Tavily Client for high-quality search (Optional)
tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
tavily_client = TavilyClient(api_key=tavily_key) if tavily_available and tavily_key else None

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini Manager for API Key Rotation
# This class handles the "Truth Layer" resilience by rotating between multiple API keys
# and falling back to Groq (Llama 3) if all Gemini keys are rate-limited.
class GeminiManager:
    def __init__(self):
        # Support both GEMINI_API_KEY (single) and GEMINI_API_KEYS (comma-separated)
        keys_str = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
        self.keys = [k.strip() for k in keys_str.split(",") if k.strip() and k.strip() != "Paste_Your_Google_Gemini_Key_Here"]
        
        # Support for a "Master Key" that is always active/fallback (e.g. a paid tier key)
        self.master_key = os.getenv("GEMINI_MASTER_KEY", "").strip()
        
        # Groq Fallback - Used when Gemini is completely unavailable
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_client = Groq(api_key=self.groq_key) if self.groq_key else None
        
        # Track cooldowns for each key to avoid repeated 429 errors
        self.key_cooldowns = {i: 0 for i in range(len(self.keys))}
        self.current_key_index = 0
        self.using_master = False
        self.model = None
        self.refresh_model()

    def refresh_model(self):
        """Configures the generative AI model with the currently active key."""
        key = self.master_key if self.using_master else (self.keys[self.current_key_index] if self.keys else None)
        if not key:
            print("Warning: No Gemini API keys found!")
            return
            
        print(f"Using Gemini API Key {'MASTER' if self.using_master else f'#{self.current_key_index + 1}'}")
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel('gemini-3-flash-preview') # Using Gemini 3 Flash Preview

    def switch_key(self):
        """Rotates to the next available API key that is not on cooldown."""
        # If we have a master key and we aren't using it yet, switch to it as a last resort
        if self.master_key and not self.using_master:
            # Check if all regular keys are on cooldown
            all_on_cooldown = all(time.time() < self.key_cooldowns[i] for i in range(len(self.keys)))
            if all_on_cooldown or not self.keys:
                print("All regular keys exhausted. Switching to MASTER KEY (Always Active).")
                self.using_master = True
                self.refresh_model()
                return True

        if not self.keys:
            return False
            
        # Mark current regular key as on cooldown (60s is standard for Gemini free tier)
        if not self.using_master:
            self.key_cooldowns[self.current_key_index] = time.time() + 60
        
        # Find next regular key not on cooldown
        for _ in range(len(self.keys)):
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            if time.time() > self.key_cooldowns[self.current_key_index]:
                self.using_master = False
                print(f"SWITCHING API KEY: Now using index {self.current_key_index}")
                self.refresh_model()
                return True
        
        # If still no regular key, and we have a master key, use it
        if self.master_key:
            self.using_master = True
            self.refresh_model()
            return True
            
        print("All API keys are currently rate-limited/on cooldown.")
        return False

    async def call_groq_async(self, prompt: str):
        """Calls Groq Llama 3 as a high-speed fallback."""
        if not self.groq_client:
            raise ValueError("Groq API key not configured")
            
        print("FALLBACK: Using Groq (Llama 3) for verification...")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=1000
            )
        )
        return response.choices[0].message.content

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
    """Searches Tavily (High Quality) or DuckDuckGo (Fallback) and returns results."""
    # Try Tavily first if available
    if tavily_client:
        try:
            print(f"Searching Tavily for: {query[:50]}...")
            # Tavily is optimized for LLM context
            response = tavily_client.search(query, search_depth="advanced", max_results=3)
            if response and response.get('results'):
                results = response['results']
                print(f"Tavily found {len(results)} results.")
                combined_body = "\n".join([f"- {r.get('content', '')}" for r in results])
                return {
                    "title": results[0].get('title', 'Multiple Sources'),
                    "body": combined_body,
                    "href": results[0].get('url', '#')
                }
        except Exception as e:
            print(f"Tavily Search Error: {e}")

    # Fallback to DuckDuckGo
    print(f"Searching DuckDuckGo for: {query[:50]}...")
    try:
        with DDGS() as ddgs:
            # Get more results for better context
            results = list(ddgs.text(query, max_results=5))
            if results:
                print(f"Found {len(results)} results for: {query[:30]}")
                # Combine top 3 results for better evidence
                combined_body = "\n".join([f"- {r.get('body', '')}" for r in results[:3]])
                return {
                    "title": results[0].get('title', 'Multiple Sources'),
                    "body": combined_body,
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
    max_retries = 5
    search_result = None
    
    # Step 0: Generate a better search query
    search_query = claim_text
    try:
        query_prompt = f"Generate a simple, effective search engine query to verify this claim: '{claim_text}'. Return ONLY the query string, no quotes."
        query_resp = await gemini_manager.model.generate_content_async(query_prompt)
        if query_resp.text:
            candidate_query = query_resp.text.strip().strip('"').strip("'")
            if 0 < len(candidate_query) < 150:
                search_query = candidate_query
    except Exception as e:
        print(f"Query generation failed: {e}")

    for attempt in range(max_retries):
        try:
            if search_result is None:
                search_result = await search_web_async(search_query)
            
            evidence = f"Source: {search_result.get('title')} - {search_result.get('body')} (URL: {search_result.get('href')})" if search_result and search_result.get('body') else "No relevant search results found."
            
            verification_prompt = f"""
            You are an expert Fact Checker. 
            Claim: "{claim_text}"
            Evidence from Search: "{evidence}"
            
            Task: Determine verification status based on the evidence.
            - "verified": Evidence directly and clearly supports the claim.
            - "uncertain": Evidence is missing, unrelated, or inconclusive.
            - "hallucinated": Evidence directly contradicts the claim or the claim is a known common AI hallucination.
            
            Return ONLY a JSON object:
            {{ 
                "status": "verified" | "uncertain" | "hallucinated", 
                "confidence": 0.0-1.0, 
                "explanation": "A concise explanation. If no evidence was found, state that clearly." 
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
                
                # If all Gemini keys fail, try Groq as the ultimate fallback
                if gemini_manager.groq_client:
                    try:
                        print(f"Gemini exhausted. Falling back to Groq for '{claim_text[:20]}'")
                        groq_resp = await gemini_manager.call_groq_async(verification_prompt)
                        v_text = clean_json_response(groq_resp)
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
                    except Exception as groq_err:
                        print(f"Groq Fallback Error: {groq_err}")

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
    max_retries = 5
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
                
                # Groq Fallback for Citations
                if gemini_manager.groq_client:
                    try:
                        print(f"Gemini exhausted. Falling back to Groq for citation '{cit_text[:20]}'")
                        groq_resp = await gemini_manager.call_groq_async(citation_prompt)
                        c_text = clean_json_response(groq_resp)
                        data = json.loads(c_text)
                        return CitationStatus(
                            id=str(uuid.uuid4()),
                            text=cit_text,
                            exists=data.get("isReal", False) or (search_result is not None),
                            url=search_result.get("href") if search_result else None,
                            checkingStatus="complete"
                        )
                    except Exception as groq_err:
                        print(f"Groq Fallback Error (Citation): {groq_err}")

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
                
                # Groq Fallback for Extraction
                if gemini_manager.groq_client:
                    try:
                        print("Gemini exhausted. Falling back to Groq for extraction...")
                        groq_resp = await gemini_manager.call_groq_async(extraction_prompt)
                        resp_text = clean_json_response(groq_resp)
                        extracted_data = json.loads(resp_text)
                        claims_list = extracted_data.get("claims", [])[:3]
                        citations_list = extracted_data.get("citations", [])[:2]
                        print(f"Extracted {len(claims_list)} claims and {len(citations_list)} citations via Groq.")
                        break
                    except Exception as groq_err:
                        print(f"Groq Fallback Error (Extraction): {groq_err}")

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
        overall_score = 0
    else:
        # Scoring Logic: 
        # Verified = 1.0 (100%)
        # Uncertain = 0.3 (30%) - Conservative score for unproven claims
        # Hallucinated = 0.0 (0%)
        score_map = {"verified": 1.0, "uncertain": 0.3, "hallucinated": 0.0}
        
        total_weighted_score = 0.0
        for c in verified_claims:
            base_score = score_map.get(c.status.lower(), 0.0)
            # If uncertain, we factor in confidence to penalize "I don't know" even more
            if c.status.lower() == "uncertain":
                # Confidence is 0-100. 
                # If confidence is 0, score is 0. If confidence is 100, score is 0.3
                total_weighted_score += base_score * (c.confidence / 100.0)
            else:
                total_weighted_score += base_score
                
        overall_score = int((total_weighted_score / len(verified_claims)) * 100)

    print(f"Verification complete. Overall Score: {overall_score}")
    return VerificationResponse(
        claims=verified_claims,
        citations=verified_citations,
        overallScore=overall_score
    )

