# """
# Analyzer Agent - Analyzes CI/CD pipelines for optimization opportunities.
# """

# import os
# import json
# import re
# import logging
# from typing import Optional, Dict, Any, List
# from openai import OpenAI

# from app.agents.agent import Agent

# logger = logging.getLogger(__name__)


# class AnalyserAgent(Agent):
#     """
#     Analyzes CI/CD pipeline YAML to identify optimization opportunities.
    
#     Uses OpenAI's GPT model to detect inefficiencies and suggest improvements.
#     """
    
#     def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3):
#         """
#         Initialize the Analyzer agent.
        
#         Args:
#             model: OpenAI model to use for analysis
#             temperature: Model temperature (0.0-1.0, lower = more deterministic)
            
#         Raises:
#             ValueError: If OPENAI_API_KEY is not set
#         """
#         logger.info("Initializing AnalyzerAgent: model=%s, temperature=%.2f", model, temperature)
        
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             logger.error("OPENAI_API_KEY environment variable not set")
#             raise ValueError("OPENAI_API_KEY environment variable not set")
        
#         self.client = OpenAI(api_key=api_key)
#         self.model = model
#         self.temperature = temperature
        
#         logger.debug("OpenAI client initialized successfully")
    
#     def run(
#         self,
#         pipeline_yaml: str,
#         build_log: Optional[str] = None,
#         save_path: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """
#         Analyze pipeline YAML for optimization opportunities.
        
#         Args:
#             pipeline_yaml: Pipeline YAML content to analyze
#             build_log: Optional build log for additional context
#             save_path: Optional file path to save analysis results
            
#         Returns:
#             Dictionary containing:
#             - issues_detected: List of identified issues
#             - suggested_fixes: List of recommended changes
#             - expected_improvement: Description of expected gains
#             - is_fixable: Boolean indicating if issues can be fixed
            
#         Raises:
#             ValueError: If input validation fails or API returns invalid JSON
#         """
#         logger.info("Starting pipeline analysis")
        
#         # Input validation
#         if not pipeline_yaml or not isinstance(pipeline_yaml, str):
#             logger.error("Invalid pipeline_yaml: must be non-empty string")
#             raise ValueError("pipeline_yaml must be a non-empty string")
        
#         if pipeline_yaml.strip() == "":
#             logger.error("Pipeline YAML is empty after stripping whitespace")
#             raise ValueError("pipeline_yaml cannot be empty")
        
#         logger.debug("Pipeline YAML size: %d bytes", len(pipeline_yaml))
#         logger.debug("Build log provided: %s", "yes" if build_log else "no")
        
#         if build_log:
#             logger.debug("Build log size: %d bytes", len(build_log))
        
#         # Build prompt
#         prompt = self._build_analysis_prompt(pipeline_yaml, build_log)
        
#         # Call OpenAI API
#         analysis_result = self._call_openai_api(prompt)
        
#         # Parse and validate result
#         parsed_analysis = self._parse_and_validate_result(analysis_result)
        
#         # Save analysis only if path explicitly provided
#         if save_path:
#             self._save_analysis(parsed_analysis, save_path)
#         else:
#             logger.debug("No save path provided, skipping analysis file save")
        
#         # Log summary
#         issues_count = len(parsed_analysis.get("issues_detected", []))
#         fixes_count = len(parsed_analysis.get("suggested_fixes", []))
#         is_fixable = parsed_analysis.get("is_fixable", False)
        
#         logger.info(
#             "Analysis complete: issues=%d, fixes=%d, fixable=%s",
#             issues_count,
#             fixes_count,
#             is_fixable
#         )
        
#         if logger.isEnabledFor(logging.DEBUG):
#             for idx, issue in enumerate(parsed_analysis.get("issues_detected", []), 1):
#                 logger.debug("Issue %d: %s", idx, issue)
        
#         return parsed_analysis
    
#     def _build_analysis_prompt(
#         self,
#         pipeline_yaml: str,
#         build_log: Optional[str]
#     ) -> str:
#         """
#         Build the analysis prompt for the LLM.
        
#         Args:
#             pipeline_yaml: Pipeline YAML content
#             build_log: Optional build log
            
#         Returns:
#             Formatted prompt string
#         """
#         logger.debug("Building analysis prompt")
        
#         prompt = f"""
# You are a CI/CD expert. Analyze this pipeline YAML for optimization opportunities.

# Pipeline YAML:
# {pipeline_yaml}

# Build Log:
# {build_log or 'N/A'}

# Return a JSON object with the following structure:
# {{
#   "issues_detected": ["list of inefficiencies or problems found"],
#   "suggested_fixes": ["concrete recommended changes to address the issues"],
#   "expected_improvement": "estimated performance or efficiency gain",
#   "is_fixable": true or false
# }}

# Be specific and actionable in your suggestions. Focus on:
# - Performance optimizations (caching, parallelization)
# - Security improvements
# - Best practices
# - Resource efficiency
# - Maintainability improvements
# """
        
#         return prompt.strip()
    
#     def _call_openai_api(self, prompt: str) -> str:
#         """
#         Call OpenAI API to analyze the pipeline.
        
#         Args:
#             prompt: Analysis prompt
            
#         Returns:
#             Raw text response from API
            
#         Raises:
#             Exception: If API call fails
#         """
#         logger.info("Calling OpenAI API: model=%s", self.model)
        
#         try:
#             response = self.client.chat.completions.create(
#                 model=self.model,
#                 messages=[
#                     {
#                         "role": "system",
#                         "content": "You are a DevOps pipeline expert specializing in CI/CD optimization."
#                     },
#                     {
#                         "role": "user",
#                         "content": prompt
#                     }
#                 ],
#                 temperature=self.temperature
#             )
            
#             text_output = response.choices[0].message.content.strip()
            
#             logger.debug("Received response from OpenAI: %d characters", len(text_output))
#             logger.debug("Response tokens used: %d", response.usage.total_tokens)
            
#             return text_output
            
#         except Exception as e:
#             logger.error("OpenAI API call failed: %s", str(e), exc_info=True)
#             raise
    
#     def _parse_and_validate_result(self, text_output: str) -> Dict[str, Any]:
#         """
#         Parse and validate the JSON result from OpenAI.
        
#         Args:
#             text_output: Raw text from OpenAI API
            
#         Returns:
#             Parsed and validated analysis dictionary
            
#         Raises:
#             ValueError: If JSON parsing fails or structure is invalid
#         """
#         logger.debug("Parsing API response")
        
#         # Remove markdown code blocks if present
#         cleaned_output = re.sub(
#             r"^```(?:json)?\s*|\s*```$",
#             "",
#             text_output,
#             flags=re.DOTALL
#         ).strip()
        
#         if cleaned_output != text_output:
#             logger.debug("Removed markdown code blocks from response")
        
#         # Parse JSON
#         try:
#             parsed = json.loads(cleaned_output)
#         except json.JSONDecodeError as e:
#             logger.error(
#                 "Failed to parse JSON from API response: %s",
#                 str(e),
#                 exc_info=True
#             )
#             logger.debug("Raw response: %s", text_output[:500])
#             raise ValueError(f"Invalid JSON from model: {str(e)}")
        
#         # Validate structure
#         self._validate_analysis_structure(parsed)
        
#         logger.debug("Successfully parsed and validated analysis result")
        
#         return parsed
    
#     def _validate_analysis_structure(self, analysis: Dict[str, Any]) -> None:
#         """
#         Validate that the analysis has the expected structure.
        
#         Args:
#             analysis: Parsed analysis dictionary
            
#         Raises:
#             ValueError: If structure is invalid
#         """
#         required_keys = ["issues_detected", "suggested_fixes", "expected_improvement", "is_fixable"]
#         missing_keys = [key for key in required_keys if key not in analysis]
        
#         if missing_keys:
#             logger.error("Analysis missing required keys: %s", missing_keys)
#             raise ValueError(f"Analysis missing required keys: {missing_keys}")
        
#         # Validate types
#         if not isinstance(analysis["issues_detected"], list):
#             logger.error("issues_detected is not a list")
#             raise ValueError("issues_detected must be a list")
        
#         if not isinstance(analysis["suggested_fixes"], list):
#             logger.error("suggested_fixes is not a list")
#             raise ValueError("suggested_fixes must be a list")
        
#         if not isinstance(analysis["expected_improvement"], str):
#             logger.error("expected_improvement is not a string")
#             raise ValueError("expected_improvement must be a string")
        
#         if not isinstance(analysis["is_fixable"], bool):
#             logger.error("is_fixable is not a boolean")
#             raise ValueError("is_fixable must be a boolean")
        
#         logger.debug("Analysis structure validation passed")
    
#     def _save_analysis(self, analysis: Dict[str, Any], save_path: str) -> None:
#         """
#         Save analysis results to a JSON file.
        
#         Args:
#             analysis: Analysis results dictionary
#             save_path: Full path where to save the analysis (including filename)
#                       Example: "/path/to/my_analysis.json"
#         """
#         logger.info("Saving analysis to: %s", save_path)
        
#         try:
#             # Ensure parent directory exists
#             parent_dir = os.path.dirname(save_path)
#             if parent_dir:
#                 os.makedirs(parent_dir, exist_ok=True)
#                 logger.debug("Ensured directory exists: %s", parent_dir)
            
#             # Write JSON file using the exact path provided
#             with open(save_path, "w", encoding="utf-8") as f:
#                 json.dump(analysis, f, indent=2, ensure_ascii=False)
            
#             file_size = os.path.getsize(save_path)
#             logger.info("Analysis saved successfully: %s (%d bytes)", save_path, file_size)
            
#         except Exception as e:
#             logger.error("Failed to save analysis to %s: %s", save_path, str(e), exc_info=True)
#             logger.warning("Continuing without saving analysis file")
#             # Don't raise - saving is optional, analysis can continue



"""
Analyser Agent - Analyses CI/CD pipelines for optimisation opportunities.
"""

import os
import json
import re
import logging
from typing import Optional, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class AnalyserAgent:
    """
    Analyses CI/CD pipeline YAML to identify optimisation opportunities.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        logger.info("Initialised AnalyserAgent: model=%s, temperature=%.2f", model, temperature)

    def run(
        self,
        pipeline_yaml: str,
        build_log: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyse pipeline YAML for optimisation opportunities."""

        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            raise ValueError("pipeline_yaml must be a non-empty string")

        prompt = self._build_prompt(pipeline_yaml, build_log)
        raw_result = self._call_openai_api(prompt)
        analysis = self._parse_and_validate_result(raw_result)

        if save_path:
            self._save_analysis(analysis, save_path)

        logger.info(
            "Analysis complete: %d issues, %d suggested fixes, fixable=%s",
            len(analysis.get("issues_detected", [])),
            len(analysis.get("suggested_fixes", [])),
            analysis.get("is_fixable", False)
        )

        return analysis

    # -------------------------
    # Internal helpers
    # -------------------------
    def _build_prompt(self, pipeline_yaml: str, build_log: Optional[str]) -> str:
        """Construct prompt for LLM analysis."""
        return f"""
            You are a CI/CD expert. Analyse this pipeline YAML for optimisation opportunities.

            Pipeline YAML:
            {pipeline_yaml}

            Build Log:
            {build_log or 'N/A'}

            Return a JSON object with:
            {{
            "issues_detected": ["list of inefficiencies or problems found"],
            "suggested_fixes": ["concrete recommended changes to address the issues"],
            "expected_improvement": "estimated performance or efficiency gain",
            "is_fixable": true or false
            }}

            Be specific and actionable. Focus on:
            - Performance optimisation (caching, parallelisation)
            - Security improvements
            - Best practices
            - Resource efficiency
            - Maintainability improvements
        """.strip()

    def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API and return raw text response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a DevOps pipeline expert specializing in CI/CD optimisation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("OpenAI API call failed: %s", str(e), exc_info=True)
            raise

    def _parse_and_validate_result(self, text_output: str) -> Dict[str, Any]:
        """Parse OpenAI output and validate JSON structure."""
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_output, flags=re.DOTALL).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s", str(e))
            raise ValueError(f"Invalid JSON from model: {str(e)}")

        self._validate_structure(parsed)
        return parsed

    def _validate_structure(self, analysis: Dict[str, Any]) -> None:
        """Ensure analysis dictionary has expected keys and types."""
        required = ["issues_detected", "suggested_fixes", "expected_improvement", "is_fixable"]
        missing = [k for k in required if k not in analysis]
        if missing:
            raise ValueError(f"Analysis missing required keys: {missing}")

        if not isinstance(analysis["issues_detected"], list):
            raise ValueError("issues_detected must be a list")
        if not isinstance(analysis["suggested_fixes"], list):
            raise ValueError("suggested_fixes must be a list")
        if not isinstance(analysis["expected_improvement"], str):
            raise ValueError("expected_improvement must be a string")
        if not isinstance(analysis["is_fixable"], bool):
            raise ValueError("is_fixable must be a boolean")

    def _save_analysis(self, analysis: Dict[str, Any], save_path: str) -> None:
        """Save analysis results as JSON to a file."""
        try:
            parent_dir = os.path.dirname(save_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            logger.info("Analysis saved to: %s", save_path)
        except Exception as e:
            logger.warning("Failed to save analysis to %s: %s", save_path, str(e))
