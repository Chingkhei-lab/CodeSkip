import os, json, requests, requests.exceptions
from dotenv import load_dotenv

load_dotenv()

class AIEngine:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "") if self.provider == "openrouter" else os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("AI_MODEL", "gpt-3.5-turbo")
        self.url = "https://openrouter.ai/api/v1/chat/completions" if self.provider == "openrouter" else "https://api.openai.com/v1/chat/completions"
        self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            self.headers.update({"HTTP-Referer": os.getenv("APP_REFERER", "http://localhost:3000"),
                                 "X-Title": os.getenv("APP_TITLE", "UltraCode")})

    def process(self, screen_text: str, audio_text: str) -> str:
        prompt = self._build_prompt(screen_text, audio_text)
        return self._call_ai(prompt)

    def _build_prompt(self, screen: str, audio: str) -> list:
        # This version forces the model to ALWAYS output JSON for coding problems,
        # and makes it crystal clear that "python_code" must be actual runnable code.
        system = (
             "You are a fast assistant. Output ONLY one of:\n\n"
            "1. **Programming task** → JSON object (no markdown, no extra text):\n"
            '{"explanation":"Bubble sort implementation","python_code":"def bubble(arr):\\n  return sorted(arr)"}\n\n'
            "   - YOU MUST provide executable code. Descriptions without code are unacceptable.\n"
            "   - Leave python_code empty ONLY if the problem is unsolvable.\n"
            "   - Never put explanations or pseudocode in python_code.\n\n"
            "2. **Non-programming question** → One plain-text sentence with the answer.\n\n"
            "Never output meta-commentary about the format or task type."
            )
        user = f"Screenshot:\n{screen}\n\nSpoken hint:\n{audio}"
        return [{"role": "system", "content": system},
                {"role": "user",   "content": user}]

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
