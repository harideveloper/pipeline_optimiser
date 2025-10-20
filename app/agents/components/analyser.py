"""
Analyser Agent - Analyses CI/CD pipelines for optimisation opportunities.
"""

import os
import json
import re
from typing import Optional, Dict, Any
from openai import OpenAI

from app.agents.components.base_agent import BaseAgent
from app.utils.logger import get_logger
from app.db import db

logger = get_logger(__name__, "AnalyserAgent")


class AnalyserAgent(BaseAgent):
    """
    Analyses CI/CD pipeline YAML to identify optimisation opportunities.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3):
        super().__init__(agent_name="analyse")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        logger.debug("Initialised AnalyserAgent: model=%s, temperature=%.2f" % (model, temperature), correlation_id="INIT")

    def run(
        self,
        pipeline_yaml: str,
        build_log: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyse pipeline YAML for optimisation opportunities."""

        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise ValueError("pipeline_yaml must be a non-empty string")

        prompt = self._build_prompt(pipeline_yaml, build_log)
        raw_result = self._call_openai_api(prompt, correlation_id)
        analysis = self._parse_and_validate_result(raw_result, correlation_id)

        logger.info(
            "Analysis complete: %d issues found, fixable=%s" % (
                len(analysis.get("issues_detected", [])),
                analysis.get("is_fixable", False)
            ),
            correlation_id=correlation_id
        )
        logger.debug(f"Full analysis result: {analysis}", correlation_id=correlation_id)        
        return analysis

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis within workflow"""
        correlation_id = state.get("correlation_id")
        
        analysis_result = self.run(
            pipeline_yaml=state["pipeline_yaml"],
            build_log=state.get("build_log", ""),
            correlation_id=correlation_id
        )

        if not isinstance(analysis_result, dict):
            analysis_result = {
                "issues_detected": [],
                "suggested_fixes": [],
                "expected_improvement": "",
                "is_fixable": False
            }

        state["analysis_result"] = analysis_result
        self._store_issues_in_db(state, analysis_result, correlation_id)

        return state

    def _store_issues_in_db(self, state: Dict[str, Any], analysis: Dict[str, Any], correlation_id: Optional[str] = None):
        """Store detected issues in database"""
        issues = analysis.get("issues_detected", [])
        fixes = analysis.get("suggested_fixes", [])

        for i, issue_text in enumerate(issues):
            fix_text = fixes[i] if i < len(fixes) else "TBD"
            try:
                db.insert_issue(
                    run_id=state["run_id"],
                    type="generic",
                    description=issue_text,
                    severity="medium",
                    suggested_fix=fix_text
                )
            except Exception as e:
                logger.debug("Failed to insert issue into DB: %s" % e, correlation_id=correlation_id)

    def _get_artifact_key(self) -> Optional[str]:
        """Analysis results are stored but not as artifact"""
        return None

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

    def _call_openai_api(self, prompt: str, correlation_id: Optional[str] = None) -> str:
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
            logger.exception("OpenAI API call failed: %s" % str(e), correlation_id=correlation_id)
            raise

    def _parse_and_validate_result(self, text_output: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Parse OpenAI output and validate JSON structure."""
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_output, flags=re.DOTALL).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s" % str(e), correlation_id=correlation_id)
            raise ValueError(f"Invalid JSON from model: {str(e)}")

        self._validate_structure(parsed, correlation_id)
        return parsed

    def _validate_structure(self, analysis: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        """Ensure analysis dictionary has expected keys and types."""
        required = ["issues_detected", "suggested_fixes", "expected_improvement", "is_fixable"]
        missing = [k for k in required if k not in analysis]
        if missing:
            logger.error("Analysis missing required keys: %s" % missing, correlation_id=correlation_id)
            raise ValueError(f"Analysis missing required keys: {missing}")

        if not isinstance(analysis["issues_detected"], list):
            raise ValueError("issues_detected must be a list")
        if not isinstance(analysis["suggested_fixes"], list):
            raise ValueError("suggested_fixes must be a list")
        if not isinstance(analysis["expected_improvement"], str):
            raise ValueError("expected_improvement must be a string")
        if not isinstance(analysis["is_fixable"], bool):
            raise ValueError("is_fixable must be a boolean")