import os, json, requests, requests.exceptions
from dotenv import load_dotenv
load_dotenv()

class AIEngine:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
        self.api_key  = os.getenv("OPENROUTER_API_KEY", "") if self.provider == "openrouter" else os.getenv("OPENAI_API_KEY", "")
        self.model    = os.getenv("AI_MODEL", "gpt-3.5-turbo")
        self.url      = "https://openrouter.ai/api/v1/chat/completions" if self.provider == "openrouter" else "https://api.openai.com/v1/chat/completions"
        self.headers  = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            self.headers.update({"HTTP-Referer": os.getenv("APP_REFERER", "http://localhost:3000"),
                                 "X-Title": os.getenv("APP_TITLE", "UltraCode")})

    # ---------- public entry ----------
    def process(self, screen_text: str, audio_text: str) -> str:
        prompt = self._build_prompt(screen_text, audio_text)
        return self._call_ai(prompt)
    
    # ---------- prompt ----------
    def _build_prompt(self, screen: str, audio: str) -> list:
        system = (
            "You are a fast assistant. "
            "If the image is a programming task, return ONLY this JSON:\n"
            '{"explanation":"<one short sentence>","python_code":"<complete runnable script>"}\n'
            'If it is NOT programming, answer the question in the image in one short sentence '
            '(no introduction, no meta-text, just the answer).'
        )
        user = f"Screenshot:\n{screen}\n\nSpoken hint:\n{audio}"
        return [{"role": "system", "content": system},
                {"role": "user",   "content": user}]
    
    # ---------- api call ----------
    def _call_ai(self, prompt: list) -> str:
        if not self.api_key:
            return "Error: API key missing. Check backend/.env"
        payload = {"model": self.model, "messages": prompt, "temperature": 0.15, "max_tokens": 1200}
        try:
            r = requests.post(self.url, headers=self.headers, json=payload, timeout=25)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            return "Error: AI service timed out."
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return "Error: Invalid API key."
            if e.response.status_code == 429:
                return "Error: Rate limit hit – wait a moment."
            return f"Error: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error: {e}"