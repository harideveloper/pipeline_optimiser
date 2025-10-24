"""
Unified LLM client supporting both OpenAI and Anthropic models.
"""

import os
import json
import re
from typing import Optional
import anthropic
from openai import OpenAI

from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")


class LLMClient:
    """
    Unified LLM client supporting both OpenAI and Anthropic models.
    Automatically detects provider based on model name.
    """
    
    def __init__(
        self, 
        model: str = "gpt-4o-mini", 
        temperature: float = 0,
        provider: Optional[str] = None
    ):
        """
        Initialize LLM client.
        
        Args:
            model: Model identifier (e.g., "gpt-4o-mini" or "claude-sonnet-4-20250514")
            temperature: Sampling temperature (0-1)
            provider: Optional explicit provider ("openai" or "anthropic")
                     If None, auto-detected from model name
        """
        self.model = model
        self.temperature = temperature
        
        # Auto-detect provider if not specified
        if provider is None:
            if model.startswith("claude"):
                self.provider = "anthropic"
            elif model.startswith("gpt") or model.startswith("o1"):
                self.provider = "openai"
            else:
                raise ValueError(
                    f"Cannot auto-detect provider for model '{model}'. "
                    "Please specify provider='openai' or provider='anthropic'"
                )
        else:
            self.provider = provider.lower()
        
        # Initialize appropriate client
        if self.provider == "openai":
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.debug(
            f"Initialized {self.provider.upper()} client with model: {self.model}",
            correlation_id="INIT"
        )
    
    def chat_completion(
        self, 
        system_prompt: str, 
        user_prompt: str,
        max_tokens: int = 4096
    ) -> str:
        """
        Get chat completion from the LLM.
        
        Args:
            system_prompt: System instructions
            user_prompt: User message
            max_tokens: Maximum tokens in response
            
        Returns:
            Model response as string
        """
        if self.provider == "openai":
            return self._openai_completion(system_prompt, user_prompt, max_tokens)
        elif self.provider == "anthropic":
            return self._anthropic_completion(system_prompt, user_prompt, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _openai_completion(
        self, 
        system_prompt: str, 
        user_prompt: str,
        max_tokens: int
    ) -> str:
        """OpenAI API completion."""
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
    
    def _anthropic_completion(
        self, 
        system_prompt: str, 
        user_prompt: str,
        max_tokens: int
    ) -> str:
        """Anthropic (Claude) API completion."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return message.content[0].text
    
    def parse_json_response(self, response: str, correlation_id: Optional[str] = None) -> dict:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            response: Raw LLM response text
            correlation_id: Optional correlation ID for logging
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            json.JSONDecodeError: If response contains invalid JSON
        """
        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Log error with context
            error_msg = f"Failed to parse JSON response: {e}"
            logger.error(
                f"{error_msg}\nResponse preview: {response[:200]}...",
                correlation_id=correlation_id
            )
            raise json.JSONDecodeError(error_msg, response, e.pos)