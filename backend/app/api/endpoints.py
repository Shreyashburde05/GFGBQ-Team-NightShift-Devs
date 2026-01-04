from fastapi import APIRouter
import uuid
import json
import asyncio
from google.api_core import exceptions as google_exceptions
from ..models.schemas import VerifyRequest, ClaimStatus, CitationStatus, VerificationResponse
from ..services.gemini import gemini_manager
from ..services.search import search_web_async
from ..core.utils import clean_json_response

router = APIRouter()

async def verify_single_claim(claim_text: str, language: str = "en"):
    """Verifies a single claim in parallel with retries."""
    max_retries = 5
    search_result = None
    
    # Step 0: Generate a better search query
    search_query = claim_text
    try:
        # We ask for a query that works best for verification. 
        # Often English queries are better, but we let the model decide based on the claim.
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
            
            IMPORTANT: Provide the explanation in the detected language: {language}.
            
            Return ONLY a JSON object:
            {{ 
                "status": "verified" | "uncertain" | "hallucinated", 
                "confidence": 0.0-1.0, 
                "explanation": "A concise explanation in {language}. If no evidence was found, state that clearly." 
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

@router.post("/verify", response_model=VerificationResponse)
async def verify_claims(request: VerifyRequest):
    print(f"Received verification request for text: {request.text[:50]}...")
    
    # Step 1: Extract Claims and Citations
    print("Step 1: Extracting claims and citations with language detection...")
    extraction_prompt = f"""
    Analyze the following text and extract:
    1. The ISO 639-1 language code of the text (e.g., 'en', 'hi', 'es'). Default to 'en' if unsure.
    2. Key factual claims (dates, facts, numbers, quotes). Limit to the 3 most important claims.
    3. Any citations or references mentioned (papers, journals, authors). Limit to 2.
    
    Return ONLY a JSON object with this structure:
    {{
        "language": "en",
        "claims": ["claim 1", "claim 2"],
        "citations": ["citation 1", "citation 2"]
    }}
    
    Text: "{request.text}"
    """
    
    claims_list = []
    citations_list = []
    detected_language = "en"
    
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
            detected_language = extracted_data.get("language", "en")
            print(f"Extracted {len(claims_list)} claims in language '{detected_language}'.")
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
            # Pass the detected language to the verification function
            return await verify_single_claim(c, language=detected_language)
            
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
