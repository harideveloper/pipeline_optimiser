"""
LLM client for pipeline optimiser.
"""
import json
import re
from typing import Dict, Any, Optional
import anthropic
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "LLMClient")


class LLMClient:
    """LLM client for Anthropic models (currently supports Claude)."""

    def __init__(self, model: str, temperature: float = 0, provider: Optional[str] = None):
        self.model = model
        self.temperature = temperature

        # Only support Anthropic
        self.provider = provider.lower() if provider else "anthropic"
        if self.provider != "anthropic":
            raise ValueError(f"Unsupported provider: {self.provider}")

        if not getattr(config, "ANTHROPIC_API_KEY", None):
            raise ValueError("ANTHROPIC_API_KEY not configured")

        try:
            self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            logger.debug("Anthropic client initialised successfully", correlation_id="INIT")
        except Exception as e:
            logger.error(f"Failed to initialise Anthropic client: {type(e).__name__}: {e}", correlation_id="INIT")
            raise

        logger.debug(f"Initialised ANTHROPIC client with model: {self.model}", correlation_id="INIT")

    def chat_completion(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Send a chat completion request to Anthropic."""
        logger.debug(f"Starting Anthropic API call with model: {self.model}", correlation_id="API_CALL")

        try:
            return self._anthropic_completion(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            logger.error(
                f"Anthropic API call failed - Type: {type(e).__name__}, Message: {str(e)}",
                correlation_id="API_CALL",
                exc_info=True,
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
            logger.debug("Anthropic API call successful", correlation_id="API_CALL")
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
        """Attempt to parse JSON from the response."""
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
            logger.error(f"{error_msg}\nResponse preview: {response[:200]}...", correlation_id=correlation_id)
            raise json.JSONDecodeError(error_msg, response, e.pos)

    def parse_optimiser_response(self, response: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Parse <optimised_yaml> and <metadata> from Anthropic response."""
        # Extract optimised YAML
        yaml_match = re.search(r'<optimised_yaml>\s*(.*?)\s*</optimised_yaml>', response, re.DOTALL)
        if not yaml_match:
            logger.error("Failed to find <optimised_yaml> tags in response", correlation_id=correlation_id)
            optimised_yaml = ""
        else:
            optimised_yaml = yaml_match.group(1).strip()

        # Extract metadata JSON
        metadata_match = re.search(r'<metadata>\s*(.*?)\s*</metadata>', response, re.DOTALL)
        if not metadata_match:
            logger.warning("Response missing <metadata> section, using defaults", correlation_id=correlation_id)
            metadata = {"applied_fixes": [], "verification": "No metadata provided"}
        else:
            try:
                metadata = json.loads(metadata_match.group(1).strip())
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse metadata JSON: {e}", correlation_id=correlation_id)
                metadata = {"applied_fixes": [], "verification": "Failed to parse metadata"}

        return {
            "optimised_yaml": optimised_yaml,
            "applied_fixes": metadata.get("applied_fixes", []),
            "verification": metadata.get("verification", "")
        }
