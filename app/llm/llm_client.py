"""
LLM client for pipeline optimiser.
"""
import json
import re
from typing import Dict, Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")


class LLMClient:
    """ LLM client with standard patterns with common error handling and retries."""

    def __init__(self, model: str, temperature: float = 0):
        """
        Initialise LLM client.
        
        Args:
            model: Anthropic model name (e.g., claude-sonnet-4-20250514)
            temperature: Sampling temperature (0.0 to 1.0)
        """
        self.model = model
        self.temperature = temperature

        if not getattr(config, "ANTHROPIC_API_KEY", None):
            raise ValueError("ANTHROPIC_API_KEY not configured")

        try:
            self.llm = ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                max_retries=config.LLM_MAX_RETRIES,
                timeout=config.LLM_TIMEOUT,
                default_headers={"anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"}
            )
            logger.debug(
                f"Initialised ChatAnthropic: model={self.model}, temp={self.temperature}, "
                f"retries={config.LLM_MAX_RETRIES}, timeout={config.LLM_TIMEOUT}",
                correlation_id="INIT"
            )
        except Exception as e:
            logger.error(
                f"Failed to initialise ChatAnthropic: {type(e).__name__}: {e}",
                correlation_id="INIT"
            )
            raise

    def chat_completion(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        max_tokens: int = 1024
    ) -> str:
        """
        Send a chat completion request (returns raw text).
        
        Args:
            system_prompt: System message content
            user_prompt: User message content
            max_tokens: Maximum tokens to generate
            
        Returns:
            Raw text response from LLM
        """
        logger.debug(
            f"Starting LLM call: model={self.model}, max_tokens={max_tokens}",
            correlation_id="API_CALL"
        )

        try:
            # Override max_tokens for this call
            llm_with_tokens = self.llm.bind(max_tokens=max_tokens)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = llm_with_tokens.invoke(messages)
            logger.debug("LLM call successful", correlation_id="API_CALL")
            
            return response.content

        except Exception as e:
            logger.error(
                f"LLM call failed: {type(e).__name__}: {e}",
                correlation_id="API_CALL",
                exc_info=True
            )
            raise

    def parse_json_response(
        self, 
        response: str, 
        correlation_id: Optional[str] = None
    ) -> dict:
        """
        Parse JSON from LLM response.
        
        Args:
            response: Raw LLM response text
            correlation_id: Request correlation ID
            
        Returns:
            Parsed JSON as dictionary
        """
        # extract JSON from code blocks first
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            json_str = json_match.group(0) if json_match else response

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {e}"
            logger.error(
                f"{error_msg}\nResponse preview: {response[:200]}...",
                correlation_id=correlation_id
            )
            raise json.JSONDecodeError(error_msg, response, e.pos)

    def parse_optimiser_response(
        self, 
        response: str, 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse <optimised_yaml> and <metadata> from llm response.
               
        Args:
            response: Raw LLM response with XML tags
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary with optimised_yaml, applied_fixes, and verification
        """
        # Extract optimised YAML
        yaml_match = re.search(
            r'<optimised_yaml>\s*(.*?)\s*</optimised_yaml>', 
            response, 
            re.DOTALL
        )
        if not yaml_match:
            logger.error(
                "Failed to find <optimised_yaml> tags in response",
                correlation_id=correlation_id
            )
            optimised_yaml = ""
        else:
            optimised_yaml = yaml_match.group(1).strip()

        # Extract metadata JSON
        metadata_match = re.search(
            r'<metadata>\s*(.*?)\s*</metadata>', 
            response, 
            re.DOTALL
        )
        if not metadata_match:
            logger.warning(
                "Response missing <metadata> section, using defaults",
                correlation_id=correlation_id
            )
            metadata = {"applied_fixes": [], "verification": "No metadata provided"}
        else:
            try:
                metadata = json.loads(metadata_match.group(1).strip())
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse metadata JSON: {e}",
                    correlation_id=correlation_id
                )
                metadata = {
                    "applied_fixes": [],
                    "verification": "Failed to parse metadata"
                }

        return {
            "optimised_yaml": optimised_yaml,
            "applied_fixes": metadata.get("applied_fixes", []),
            "verification": metadata.get("verification", "")
        }