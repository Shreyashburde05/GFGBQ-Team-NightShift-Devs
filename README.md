# 1. Problem Statement
Generative AI models often produce "hallucinations"—factual errors presented with high confidence—and fake citations. This undermines trust in AI-generated content for research, journalism, and decision-making. **TrustGuard AI** serves as a "Truth Layer" that automatically extracts factual claims from any text, cross-references them with real-time web search data, and provides a visual trust score to help users distinguish between fact and fiction.

# 2. Project Name
TrustGuard AI (AI Trust Beacon)

# 3. Team Name
nightshift-devs

# 4. Deployed Link (optional)
[Localhost Development Environment]

# 5. 2-minute Demonstration Video link
[Insert Video Link Here]

# 6. PPT Link
[Insert PPT Link Here]

---

## Project Overview
TrustGuard AI is a comprehensive AI safety tool consisting of a **FastAPI Backend** and a **Chrome Extension**. It allows users to highlight any text on the web and instantly verify its accuracy. The system uses Google Gemini for claim extraction and verification, combined with DuckDuckGo for real-time fact-checking.

### Key Features:
- **Real-time Fact Checking:** Cross-references claims with live search results.
- **API Key Rotation:** Automatically switches between multiple Gemini API keys to bypass free-tier rate limits.
- **Parallel Processing:** Verifies multiple claims simultaneously for faster results.
- **Visual Trust Score:** Provides an overall percentage score and detailed explanations for each claim.
- **Citation Verification:** Checks if mentioned sources actually exist.

## Setup and Installation Instructions

### Prerequisites:
- Python 3.10+
- Node.js & npm
- Google Gemini API Key(s)

### 1. Backend Setup
```bash
cd backend
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure Environment Variables
# Create a .env file in the backend folder:
# GEMINI_API_KEYS=your_key_1,your_key_2
# (You can add multiple keys separated by commas to enable automatic rotation)
```

### 2. Frontend/Extension Setup
```bash
# Install frontend dependencies (for the web dashboard)
npm install

# To load the Chrome Extension:
1. Open Chrome and go to chrome://extensions/
2. Enable "Developer mode" (top right).
3. Click "Load unpacked".
4. Select the 'extension' folder from this repository.
```

## Usage Instructions
1. **Start the Backend:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload --port 8000
   ```
2. **Start the Web App (Optional):**
   ```bash
   npm run dev
   ```
3. **Using the Extension:**
   - Navigate to any website (e.g., a news article or ChatGPT).
   - **Highlight** a paragraph of text.
   - Click the floating **🛡️ Verify with TrustGuard** button that appears.
   - View the analysis modal for trust scores and evidence links.

## Relevant Screenshots
*(Add screenshots of the extension in action, the trust score gauge, and the claim cards here)*

