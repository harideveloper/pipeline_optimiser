"""
Unified LLM client supporting both OpenAI and Anthropic models.
"""

import json
import re
from typing import Optional
import anthropic
from openai import OpenAI

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")


class LLMClient:
    """Unified LLM client supporting both OpenAI and Anthropic models."""
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0, provider: Optional[str] = None):
        self.model = model
        self.temperature = temperature
        
        if provider is None:
            if model.startswith("claude"):
                self.provider = "anthropic"
            elif model.startswith("gpt") or model.startswith("o1"):
                self.provider = "openai"
            else:
                raise ValueError(f"Cannot auto-detect provider for model '{model}'")
        else:
            self.provider = provider.lower()
        
        if self.provider == "openai":
            openai_key = getattr(config, "OPENAI_API_KEY", None)
            if not openai_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAI(api_key=openai_key)
        elif self.provider == "anthropic":
            if not config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.debug(f"Initialized {self.provider.upper()} client with model: {self.model}", correlation_id="INIT")
    
    def chat_completion(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        if self.provider == "openai":
            return self._openai_completion(system_prompt, user_prompt, max_tokens)
        elif self.provider == "anthropic":
            return self._anthropic_completion(system_prompt, user_prompt, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _openai_completion(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _anthropic_completion(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text
    
    def parse_json_response(self, response: str, correlation_id: Optional[str] = None) -> dict:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {e}"
            logger.error(f"{error_msg}\nResponse preview: {response[:200]}...", correlation_id=correlation_id)
            raise json.JSONDecodeError(error_msg, response, e.pos)