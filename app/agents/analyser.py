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
