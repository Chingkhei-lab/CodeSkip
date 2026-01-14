"""
AI Engine - Handles model calls with minimal metadata exposure.
"""
import os
import re
import logging
from enum import Enum
from typing import Dict, List, Final, Optional
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()
_logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """Supported question classification types."""
    CODING = "coding"
    MCQ = "mcq"
    TEXT = "text"


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass
class AIConfig:
    """Configuration for AI provider."""
    provider: AIProvider
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout: int
    referer: Optional[str] = None
    title: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Load configuration from environment variables."""
        provider_name = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
        provider = AIProvider(provider_name)
        
        key_map = {
            AIProvider.OPENROUTER: "OPENROUTER_API_KEY",
            AIProvider.OPENAI: "OPENAI_API_KEY"
        }
        
        api_key = os.getenv(key_map.get(provider, "")).strip()
        if not api_key:
            raise ValueError(f"API key not configured: {key_map[provider]}")

        return cls(
            provider=provider,
            api_key=api_key,
            model=os.getenv("AI_MODEL", "").strip() or "meta-llama/llama-3-8b-instruct",
            temperature=float(os.getenv("AI_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "1500")),
            timeout=int(os.getenv("AI_TIMEOUT", "25")),
            referer=os.getenv("APP_REFERER", "http://localhost:3000"),
            title=os.getenv("APP_TITLE", "Assistant")
        )


class _QuestionAnalyzer:
    """Analyzes text to determine question type and language."""
    
    _MCQ_PATTERNS: Final[List[re.Pattern]] = [
        re.compile(r"\(a\).*\(b\)", re.IGNORECASE),
        re.compile(r"\ba\)\s*.*\bb\)", re.IGNORECASE),
        re.compile(r"select.*correct.*option", re.IGNORECASE),
        re.compile(r"which.*following.*options?", re.IGNORECASE),
    ]
    
    _CODING_PATTERNS: Final[List[re.Pattern]] = [
        re.compile(r"write.*function|write.*program|write.*code", re.IGNORECASE),
        re.compile(r"implement.*function|implement.*algorithm", re.IGNORECASE),
        re.compile(r"create.*function|create.*class", re.IGNORECASE),
        re.compile(r"solve.*problem|solve.*code", re.IGNORECASE),
        re.compile(r"def\s+\w+\s*\(|class\s+\w+\s*:"),
    ]
    
    _LANG_KEYWORDS: Final[Dict[str, List[str]]] = {
        "python": ["python", "py"],
        "javascript": ["javascript", "js", "node"],
        "java": ["java"],
        "cpp": ["c++", "cpp"],
        "go": ["go", "golang"],
        "rust": ["rust"],
        "typescript": ["typescript", "ts"],
    }

    def analyze_type(self, text: str) -> QuestionType:
        """Detect question classification."""
        if not text or len(text.strip()) < 10:
            return QuestionType.TEXT

        text_lower = text.lower()
        
        if any(p.search(text_lower) for p in self._CODING_PATTERNS):
            return QuestionType.CODING
        
        if any(p.search(text_lower) for p in self._MCQ_PATTERNS):
            return QuestionType.MCQ
        
        return QuestionType.TEXT
    
    def detect_language(self, text: str) -> str:
        """Detect programming language from context."""
        if not text:
            return "python"
        
        text_lower = text.lower()
        
        for lang, keywords in self._LANG_KEYWORDS.items():
            for kw in keywords:
                if re.search(rf"\b{kw}\b", text_lower):
                    return lang
        
        return "python"


class _PromptBuilder:
    """Constructs prompts based on question type."""
    
    @staticmethod
    def build(
        screen_text: str, 
        audio_text: str, 
        question_type: QuestionType, 
        language: str,
        error_msg: str = ""
    ) -> List[Dict[str, str]]:
        """Build prompt messages for the model."""
        audio_ctx = audio_text.strip() if audio_text else "No audio"
        
        if question_type == QuestionType.CODING:
            sys_prompt = _PromptBuilder._coding_prompt(language, error_msg)
            err_section = f"\n\nERROR:\n{error_msg}" if error_msg else ""
            user = f"PROBLEM:\n{screen_text}{err_section}\n\nAUDIO:{audio_ctx}"
        elif question_type == QuestionType.MCQ:
            sys_prompt = "Answer MCQ. Output: **Answer: [Letter]**"
            user = f"QUESTION:\n{screen_text}\n\nAUDIO:{audio_ctx}"
        else:
            sys_prompt = "Explain concisely with bullet points."
            user = f"QUESTION:\n{screen_text}\n\nAUDIO:{audio_ctx}"
        
        return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]
    
    @staticmethod
    def _coding_prompt(language: str, error_msg: str) -> str:
        """Generate coding system prompt."""
        lang_upper = language.upper()
        
        if error_msg:
            return f"Debug the {lang_upper} code. Fix the error. Output corrected code only."
        
        return f"Generate {lang_upper} code. Code only with inline comments."


class _AIClient:
    """Low-level AI API client with retry logic."""
    
    _RETRY_CODES: Final[List[int]] = [429, 500, 502, 503, 504]
    _MAX_RETRIES: Final[int] = 2

    def __init__(self, config: AIConfig):
        self._config = config
        self._base_url = self._get_base_url()
        self._headers = self._build_headers()

    def _get_base_url(self) -> str:
        """Get API endpoint base URL."""
        return {
            AIProvider.OPENROUTER: "https://openrouter.ai/api/v1",
            AIProvider.OPENAI: "https://api.openai.com/v1"
        }[self._config.provider]

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        h = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }
        
        if self._config.provider == AIProvider.OPENROUTER:
            h["HTTP-Referer"] = self._config.referer or ""
            h["X-Title"] = self._config.title or ""
        
        return h

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Execute chat completion request."""
        url = f"{self._base_url}/chat/completions"
        
        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens
        }

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    headers=self._headers,
                    json=payload,
                    timeout=self._config.timeout
                )
                response.raise_for_status()
                
                return response.json()["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                if attempt == self._MAX_RETRIES:
                    raise
                
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                if status in self._RETRY_CODES and attempt < self._MAX_RETRIES:
                    continue
                raise
            
            except requests.exceptions.ConnectionError:
                raise Exception("Connection failed")

        raise Exception("Max retries exceeded")


class AIEngine:
    """Main orchestrator for AI processing."""
    
    def __init__(self, config: Optional[AIConfig] = None):
        self._config = config or AIConfig.from_env()
        self._analyzer = _QuestionAnalyzer()
        self._builder = _PromptBuilder()
        self._client = _AIClient(self._config)

    def process(self, screen_text: str, audio_text: str = "", error_msg: str = "") -> str:
        """
        Process input and return AI response.
        
        Args:
            screen_text: Text extracted from screenshot
            audio_text: Optional transcribed audio
            error_msg: Optional error to debug
            
        Returns:
            AI-generated response
        """
        try:
            if not screen_text or len(screen_text.strip()) < 5:
                return "⚠️ No text detected."

            q_type = self._analyzer.analyze_type(screen_text)
            lang = self._analyzer.detect_language(screen_text) if q_type == QuestionType.CODING else "python"
            
            messages = self._builder.build(screen_text, audio_text, q_type, lang, error_msg)
            
            return self._client.complete(messages)
            
        except Exception as e:
            _logger.error(f"AI processing error: {type(e).__name__}: {e}")
            return f"⚠️ Error: {type(e).__name__}"


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    try:
        engine = AIEngine()
        test_screen = "Write a function to reverse a string."
        result = engine.process(test_screen, "")
        print(f"Response:\n{result}")
    except ValueError as e:
        print(f"Config error: {e}")
