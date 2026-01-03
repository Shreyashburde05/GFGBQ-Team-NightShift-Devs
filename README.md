# TrustGuard AI

**Team:** NightShift Devs  
**ByteQuest 2025 Track:** Generative AI / AI Safety (PS 03)

## Problem Statement
AI Hallucination & Citation Verification System. Generative AI models often create fake facts and citations. TrustGuard AI is a "Truth Layer" that polices these outputs.

## Solution
TrustGuard AI is a Chrome Extension that:
1.  **Extracts Claims** from any webpage (ChatGPT, Blogs, News).
2.  **Cross-Checks** them against real-time search results (DuckDuckGo).
3.  **Flags Hallucinations** visually with Red/Green highlights.

## Tech Stack
- **Frontend:** Chrome Extension (Manifest V3, JS)
- **Backend:** FastAPI (Python)
- **AI Core:** Google Gemini 1.5 Flash (Free Tier)
- **Search:** DuckDuckGo API

## Setup
### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Extension
1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. "Load unpacked" -> Select `extension/` folder.
