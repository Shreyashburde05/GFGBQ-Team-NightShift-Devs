import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from groq import Groq
import os
import time
import asyncio
from ..core.config import settings

class GeminiManager:
    def __init__(self):
        # Support both GEMINI_API_KEY (single) and GEMINI_API_KEYS (comma-separated)
        keys_str = settings.GEMINI_API_KEYS
        self.keys = [k.strip() for k in keys_str.split(",") if k.strip() and k.strip() != "Paste_Your_Google_Gemini_Key_Here"]
        
        # Support for a "Master Key" that is always active/fallback (e.g. a paid tier key)
        self.master_key = settings.GEMINI_MASTER_KEY
        
        # Groq Fallback - Used when Gemini is completely unavailable
        self.groq_key = settings.GROQ_API_KEY
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
