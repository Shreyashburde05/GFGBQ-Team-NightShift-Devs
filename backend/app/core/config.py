import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MASTER_KEY = os.getenv("GEMINI_MASTER_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

settings = Settings()
