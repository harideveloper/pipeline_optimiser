"""
Risk Assessor Agent - Assesses risk of pipeline changes
"""

import os
import json
from typing import Dict, Any, Optional

from openai import OpenAI

from app.agents.components.base_agent import BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__, "RiskAssessorAgent")


class RiskAssessorAgent(BaseAgent):
    """
    Assesses the risk of proposed pipeline changes
    """

    def __init__(self, model: str = "gpt-4o", temperature: float = 0):
        super().__init__(agent_name="risk_assessment")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        logger.debug("Initialised RiskAssessorAgent: model=%s" % model, correlation_id="INIT")

    def run(
        self,
        pipeline_yaml: str,
        suggested_fixes: list,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assess risk of proposed changes

        Returns:
            Risk assessment dictionary
        """
        if not suggested_fixes:
            logger.info("No changes proposed, skipping risk assessment", correlation_id=correlation_id)
            return {
                "risk_score": 0,
                "severity": "none",
                "safe_to_auto_merge": True,
                "message": "No changes proposed"
            }

        prompt = f"""
            Analyze the risk of these proposed pipeline changes:

            Original Pipeline (first 500 chars):
            {pipeline_yaml[:500]}

            Proposed Changes:
            {json.dumps(suggested_fixes, indent=2)}

            Assess:
            1. Breaking change probability (0-100%)
            2. Production impact severity (low/medium/high/critical)
            3. Rollback difficulty (easy/medium/hard)
            4. Affected services/jobs

            Return JSON:
            {{
                "risk_score": 0-100,
                "severity": "low|medium|high|critical",
                "breaking_changes": ["list of potential breaking changes"],
                "affected_components": ["list"],
                "rollback_plan": "description",
                "requires_manual_approval": true/false,
                "safe_to_auto_merge": true/false
            }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            risk_assessment = json.loads(response.choices[0].message.content)
            
            logger.info(
                "Risk Assessment: score=%d/100, severity=%s, safe_to_merge=%s, manual_approval=%s, breaking_changes=%d, affected_components=%d" % (
                    risk_assessment.get("risk_score", 0),
                    risk_assessment.get("severity", "unknown"),
                    risk_assessment.get("safe_to_auto_merge", False),
                    risk_assessment.get("requires_manual_approval", False),
                    len(risk_assessment.get("breaking_changes", [])),
                    len(risk_assessment.get("affected_components", []))
                ),
                correlation_id=correlation_id
            )

            return risk_assessment

        except Exception as e:
            logger.exception("Risk assessment failed: %s" % str(e), correlation_id=correlation_id)
            raise

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute risk assessment within workflow"""
        correlation_id = state.get("correlation_id")
        suggested_fixes = state.get("analysis_result", {}).get("suggested_fixes", [])

        risk_assessment = self.run(
            pipeline_yaml=state["pipeline_yaml"],
            suggested_fixes=suggested_fixes,
            correlation_id=correlation_id
        )

        state["risk_assessment"] = risk_assessment

        if risk_assessment.get("severity") == "critical" and risk_assessment.get("risk_score", 0) >= 90:
            state["error"] = "Critical risk requires manual review"
            logger.error("Critical risk requires manual review", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """Risk assessment should be saved as artifact"""
        return "risk_assessment"