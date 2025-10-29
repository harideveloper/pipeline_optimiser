"""
Unified LLM client supporting both OpenAI and Anthropic models.
"""
import json
import re
import os
from typing import Optional
import anthropic
from openai import OpenAI
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")

class LLMClient:
    """Unified LLM client supporting both OpenAI and Anthropic models."""
    
    def __init__(self, model, temperature, provider: Optional[str] = None):
        self.model = model
        self.temperature = temperature
        
        # ADD: Log environment variables related to SSL
        logger.debug(f"SSL_CERT_FILE env: {os.getenv('SSL_CERT_FILE', 'NOT SET')}", correlation_id="INIT")
        logger.debug(f"REQUESTS_CA_BUNDLE env: {os.getenv('REQUESTS_CA_BUNDLE', 'NOT SET')}", correlation_id="INIT")
        
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
            
            # ADD: Log API key status (first/last 4 chars only)
            key = config.ANTHROPIC_API_KEY
            masked_key = f"{key[:7]}...{key[-4:]}" if len(key) > 11 else "***"
            logger.debug(f"Anthropic API key: {masked_key}", correlation_id="INIT")
            
            # ADD: Try to initialize with detailed error handling
            try:
                self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                logger.info(f"Anthropic client initialized successfully", correlation_id="INIT")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {type(e).__name__}: {e}", correlation_id="INIT")
                raise
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.debug(f"Initialized {self.provider.upper()} client with model: {self.model}", correlation_id="INIT")

    def chat_completion(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        # ADD: Log before making API call
        logger.debug(f"Starting {self.provider} API call with model: {self.model}", correlation_id="API_CALL")
        
        try:
            if self.provider == "openai":
                return self._openai_completion(system_prompt, user_prompt, max_tokens)
            elif self.provider == "anthropic":
                return self._anthropic_completion(system_prompt, user_prompt, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            # ADD: Detailed error logging
            logger.error(
                f"API call failed - Type: {type(e).__name__}, Message: {str(e)}", 
                correlation_id="API_CALL",
                exc_info=True  # This will log the full traceback
            )
            raise

    def _anthropic_completion(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        logger.debug(f"Calling Anthropic API - Model: {self.model}, Max Tokens: {max_tokens}", correlation_id="API_CALL")
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            logger.debug(f"Anthropic API call successful", correlation_id="API_CALL")
            return message.content[0].text
        except anthropic.APIConnectionError as e:
            logger.error(f"Anthropic API Connection Error: {e}", correlation_id="API_CALL", exc_info=True)
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API Error: {e}", correlation_id="API_CALL", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Anthropic completion: {type(e).__name__}: {e}", correlation_id="API_CALL", exc_info=True)
            raise
    
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