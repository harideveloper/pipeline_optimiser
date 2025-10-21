"""
Shared LLM client used across all components invoking LLM calls
"""
import json
import time
from typing import Dict, Any, Optional
from openai import OpenAI, RateLimitError, APIError

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")


class LLMClient:
    """
    Reusable llm client
    """
    
    def __init__(
        self,
        model: str = None,
        temperature: float = None,
        max_retries: int = None,
        timeout: int = None
    ):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = model or config.MODEL_NAME
        self.temperature = temperature if temperature is not None else config.MODEL_TEMPERATURE
        self.max_retries = max_retries or config.LLM_MAX_RETRIES
        self.timeout = timeout or config.LLM_TIMEOUT
    
    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, str]] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Make a chat completion request with retry logic
        
        Args:
            system_prompt: System message
            user_prompt: User message
            response_format: Optional response format (e.g., {"type": "json_object"})
            correlation_id: Request correlation ID
            
        Returns:
            Response content as string
            
        Raises:
            Exception: If all retries fail
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "timeout": self.timeout
                }
                
                if response_format:
                    kwargs["response_format"] = response_format
                
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
                
            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})",
                        correlation_id=correlation_id
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exceeded for rate limit", correlation_id=correlation_id)
                    raise
                    
            except APIError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"API error, retrying in {wait_time}s: {e}",
                        correlation_id=correlation_id
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded for API error: {e}", correlation_id=correlation_id)
                    raise
                    
            except Exception as e:
                logger.exception(f"Unexpected error: {e}", correlation_id=correlation_id)
                raise
    
    def parse_json_response(
        self,
        response: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse JSON response, handling markdown code blocks
        
        Args:
            response: Raw response string
            correlation_id: Request correlation ID
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If JSON parsing fails
        """
        import re
        
        # Remove markdown code blocks
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response, flags=re.DOTALL).strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}", correlation_id=correlation_id)
            logger.debug(f"Raw response: {response}", correlation_id=correlation_id)
            raise ValueError(f"Invalid JSON from model: {e}")