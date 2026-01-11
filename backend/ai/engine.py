import os
import re
import json
import logging
from enum import Enum
from typing import Dict, Any, List, Final, Optional
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """Enumeration of supported question types."""
    CODING = "coding"
    MCQ = "mcq"
    TEXT = "text"


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass
class AIConfig:
    """Immutable configuration for AI Engine."""
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
        """Load configuration from environment variables with validation."""
        provider = AIProvider(os.getenv("AI_PROVIDER", "openai").strip().lower())
        
        api_key_map = {
            AIProvider.OPENROUTER: "OPENROUTER_API_KEY",
            AIProvider.OPENAI: "OPENAI_API_KEY"
        }
        
        api_key = os.getenv(api_key_map[provider], "").strip()
        if not api_key:
            raise ValueError(f"API key not found: {api_key_map[provider]}")

        return cls(
            provider=provider,
            api_key=api_key,
            model=os.getenv("AI_MODEL", "gpt-3.5-turbo").strip(),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.15")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("AI_TIMEOUT", "30")),
            referer=os.getenv("APP_REFERER", "http://localhost:3000"),
            title=os.getenv("APP_TITLE", "UltraCode")
        )


class QuestionAnalyzer:
    """Analyzes text to determine question type and programming language."""
    
    # MORE SPECIFIC: Require multiple options for MCQ detection
    MCQ_PATTERNS: Final[List[re.Pattern]] = [
        re.compile(r'(?=.*\ba\))(?=.*\bb\))', re.IGNORECASE),  # Must have both a) and b)
        re.compile(r'(?=.*\(a\))(?=.*\(b\))', re.IGNORECASE),  # Must have both (a) and (b)
        re.compile(r'\bselect\b.*\bcorrect\b.*option', re.IGNORECASE),
        re.compile(r'\bwhich\s+of\s+the\s+following\b.*\boptions?\b', re.IGNORECASE),
        re.compile(r'\bchoose\b.*\bcorrect\b.*answer\b', re.IGNORECASE),
    ]
    
    # STRONGER: More robust coding detection
    CODING_PATTERNS: Final[List[re.Pattern]] = [
        re.compile(r'\bwrite\s+(?:a\s+)?(?:function|program|code|solution)\b', re.IGNORECASE),
        re.compile(r'\bimplement\s+(?:a\s+)?(?:function|algorithm|solution)\b', re.IGNORECASE),
        re.compile(r'\bcreate\s+(?:a\s+)?(?:function|class|program)\b', re.IGNORECASE),
        re.compile(r'\bsolve\s+(?:the\s+)?(?:problem|code|challenge)\b', re.IGNORECASE),
        re.compile(r'\bcode\s+for\b', re.IGNORECASE),
        re.compile(r'\breturn\s+(?:the\s+)?\w+', re.IGNORECASE),
        re.compile(r'def\s+\w+\s*\(|class\s+\w+\s*:', re.IGNORECASE),  # Python syntax
        re.compile(r'#code\s+here|#\s*write\s+your\s+code\b', re.IGNORECASE),  # Common placeholders
    ]
    
    LANGUAGE_KEYWORDS: Final[Dict[str, List[str]]] = {
        'python': ['python', 'py', 'python3'],
        'javascript': ['javascript', 'js', 'node', 'nodejs'],
        'java': ['java'],
        'c++': ['cpp', 'c\+\+', 'cxx'],
        'c': ['c'],
        'csharp': ['c#', 'csharp', 'cs'],
        'go': ['go', 'golang'],
        'rust': ['rust', 'rs'],
        'typescript': ['typescript', 'ts'],
        'ruby': ['ruby', 'rb'],
        'php': ['php'],
        'swift': ['swift'],
        'kotlin': ['kotlin', 'kt'],
        'r': ['r'],
        'sql': ['sql', 'mysql', 'postgresql'],
    }
    
    SYNTAX_PATTERNS: Final[Dict[str, List[re.Pattern]]] = {
        'python': [
            re.compile(r'def\s+\w+\s*\('),
            re.compile(r'class\s+\w+\s*:'),
            re.compile(r'import\s+\w+'),
        ],
        'javascript': [
            re.compile(r'function\s+\w+\s*\('),
            re.compile(r'const\s+\w+\s*='),
            re.compile(r'=>'),
        ],
        'java': [
            re.compile(r'public\s+class'),
            re.compile(r'public\s+static\s+void'),
        ],
        'c++': [
            re.compile(r'#include\s*<'),
            re.compile(r'std::'),
        ],
    }

    def analyze_type(self, text: str) -> QuestionType:
        """Detect question type from text with improved logic."""
        if not text or len(text.strip()) < 10:
            logger.warning("Text too short for analysis, defaulting to TEXT")
            return QuestionType.TEXT

        text_lower = text.lower()
        
        # CHECK CODING FIRST to avoid MCQ false positives
        if any(pattern.search(text_lower) for pattern in self.CODING_PATTERNS):
            logger.info("Detected CODING question")
            return QuestionType.CODING
        
        # Then check MCQ (requires multiple options)
        if any(pattern.search(text_lower) for pattern in self.MCQ_PATTERNS):
            logger.info("Detected MCQ question")
            return QuestionType.MCQ
        
        # Default to text
        logger.info("Detected TEXT question")
        return QuestionType.TEXT
    
    def detect_language(self, text: str) -> str:
        """Detect programming language from context, defaults to 'python'."""
        if not text:
            return 'python'
            
        text_lower = text.lower()
        
        # Explicit language mention
        for lang, keywords in self.LANGUAGE_KEYWORDS.items():
            for keyword in keywords:
                pattern = rf'\b{keyword}\b'
                if re.search(pattern, text_lower):
                    logger.info(f"Detected language: {lang}")
                    return lang
        
        # Syntax-based detection
        for lang, patterns in self.SYNTAX_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    logger.info(f"Detected language from syntax: {lang}")
                    return lang
        
        logger.debug("Defaulting to Python")
        return 'python'


class PromptBuilder:
    """Constructs prompts based on question type and context."""

    @staticmethod
    def build(
        screen_text: str, 
        audio_text: str, 
        question_type: QuestionType, 
        language: str
    ) -> List[Dict[str, str]]:
        """Build intelligent prompt based on question type."""
        
        audio_context = audio_text if audio_text.strip() else "No audio input"
        
        if question_type == QuestionType.CODING:
            system_prompt = PromptBuilder._coding_system_prompt(language)
            user_prompt = f"CODE ONLY:\n{screen_text}\n\n{audio_context}"
        elif question_type == QuestionType.MCQ:
            system_prompt = PromptBuilder._mcq_system_prompt()
            user_prompt = f"QUESTION:\n{screen_text}\n\nCONTEXT:\n{audio_context}"
        else:
            system_prompt = PromptBuilder._text_system_prompt()
            user_prompt = f"QUESTION:\n{screen_text}\n\nCONTEXT:\n{audio_context}"
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    @staticmethod
    def _coding_system_prompt(language: str) -> str:
        return f"""You are a code generator. OUTPUT CODE ONLY.

**RULES:**
• NO problem breakdown
• NO analysis paragraphs  
• NO explanations before/after code
• CODE ONLY with inline comments if needed
• Inline comments must be brief (max 5 words)
• Format: `code  # brief comment`
• Include necessary imports
• Make it executable

**EXAMPLE:**
```python
def solution(arr):  # Sort input array
    return sorted(arr)  # Return sorted result
```"""

    @staticmethod
    def _mcq_system_prompt() -> str:
        return """Analyze MCQ and output answer.

**RULES:**
• NO explanations
• Output: **Answer: [Letter]** only
• No justification unless asked"""

    @staticmethod
    def _text_system_prompt() -> str:
        return """Provide direct, concise explanation.

**RULES:**
• Be brief and clear
• Use bullet points
• No lengthy analysis"""


class AIClient:
    """Handles AI provider API calls."""

    MAX_RETRIES: Final[int] = 2
    RETRY_STATUS_CODES: Final[List[int]] = [429, 500, 502, 503, 504]

    def __init__(self, config: AIConfig):
        self.config = config
        self.base_url = self._get_base_url()
        self.headers = self._build_headers()

    def _get_base_url(self) -> str:
        """Get the correct API base URL."""
        urls = {
            AIProvider.OPENROUTER: "https://openrouter.ai/api/v1",
            AIProvider.OPENAI: "https://api.openai.com/v1"
        }
        return urls[self.config.provider]

    def _build_headers(self) -> Dict[str, str]:
        """Build API request headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        if self.config.provider == AIProvider.OPENROUTER:
            headers.update({
                "HTTP-Referer": self.config.referer,
                "X-Title": self.config.title
            })
        
        return headers

    def create_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """Call chat completions endpoint with retry logic."""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(f"Calling {self.config.provider.value} API (attempt {attempt})")
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.config.timeout  # ✅ FIXED
                )
                response.raise_for_status()
                
                content = response.json()["choices"][0]["message"]["content"]
                logger.info(f"Received response ({len(content)} chars)")
                return content

            except requests.exceptions.Timeout:
                if attempt == self.MAX_RETRIES:
                    raise
                logger.warning("Request timed out, retrying...")
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                error_msg = self._http_error_message(status_code)
                
                if status_code in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                    logger.warning(f"HTTP {status_code}, retrying...")
                    continue
                
                raise Exception(error_msg)
            
            except requests.exceptions.ConnectionError:
                raise Exception("Failed to connect to AI service")
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                raise Exception(f"Error: {str(e)}")

    def _http_error_message(self, status_code: int) -> str:
        """Map HTTP status codes to user-friendly messages."""
        messages = {
            401: "Invalid API key",
            429: "Rate limit exceeded",
            400: "Bad request",
        }
        return messages.get(status_code, f"HTTP {status_code} error")


class AIEngine:
    """Main engine that orchestrates question analysis and AI interaction."""
    
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or AIConfig.from_env()
        self.analyzer = QuestionAnalyzer()
        self.prompt_builder = PromptBuilder()
        self.client = AIClient(self.config)
        logger.info(f"AI Engine initialized: {self.config.provider.value} - {self.config.model}")

    def process(self, screen_text: str, audio_text: str = "") -> str:
        """
        Process screenshot intelligently like Perplexity AI.
        Analyzes question type and returns natural, clean output.
        
        Args:
            screen_text: Text extracted from screenshot
            audio_text: Optional audio transcription context
            
        Returns:
            Clean, formatted answer based on question type
        """
        try:
            # Validate input
            if not screen_text or len(screen_text.strip()) < 5:
                return "⚠️ Error: No text detected in screenshot."
            
            # Analyze question type
            question_type = self.analyzer.analyze_type(screen_text)
            
            # Detect language for coding questions
            language = (
                self.analyzer.detect_language(screen_text) 
                if question_type == QuestionType.CODING 
                else "python"
            )
            
            # Build prompt
            messages = self.prompt_builder.build(
                screen_text, 
                audio_text, 
                question_type, 
                language
            )
            
            # Call AI
            return self.client.create_chat_completion(messages)
            
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            return self._format_error(str(e))

    def _format_error(self, message: str) -> str:
        """Format error message for user display."""
        return f"⚠️ Error: {message}\n\nPlease check your configuration and try again."


# Usage example
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        engine = AIEngine()
        
        # Example usage with the provided screenshot text
        screen = """K-th element of two Arrays
Given two sorted arrays a[] and b[] and an element k, the task is to find the element
position of the combined sorted array.
Input: a = [2, 3, 6, 7, 9], b = [1, 4, 8, 10], k = 5
Output: 6
class Solution:
    def kthElement(self, a, b, k):
        #code here"""
        
        audio = "Need optimal binary search solution"
        
        response = engine.process(screen, audio)
        print("=" * 50)
        print(response)
        print("=" * 50)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
