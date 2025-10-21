"""
Risk Assessor Agent - Assesses risk of pipeline changes
"""

from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.utils.llm_client import LLMClient
from app.config import config
from app.constants import SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH
from app.exceptions import RiskAssessorError
from app.orchestrator.prompts import RISK_ASSESSOR_SYSTEM_PROMPT, build_risk_assessor_prompt

logger = get_logger(__name__, "RiskAssessor")


class RiskAssessor(BaseService):
    """
    Assesses the risk of proposed pipeline changes.
    
    Uses LLM to analyze:
    - Breaking change probability
    - Production impact severity
    - Rollback difficulty
    - Affected components
    """

    def __init__(self, model: str = None, temperature: float = None):
        """
        Initialize RiskAssessor with LLM configuration.
        
        Args:
            model: LLM model name (defaults to config.RISK_ASSESSOR_MODEL)
            temperature: LLM temperature (defaults to 0 for deterministic assessment)
        """
        super().__init__(agent_name="risk_assessment")
        
        self.model = model or config.RISK_ASSESSOR_MODEL
        self.temperature = temperature if temperature is not None else 0.0
        
        # Use shared LLM client
        self.llm_client = LLMClient(
            model=self.model,
            temperature=self.temperature
        )
        
        logger.debug(
            f"Initialised RiskAssessor: model={self.model}, temperature={self.temperature}",
            correlation_id="INIT"
        )

    def run(
        self,
        pipeline_yaml: str,
        suggested_fixes: List[str],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assess risk of proposed changes.
        
        Args:
            pipeline_yaml: Original pipeline YAML
            suggested_fixes: List of proposed fixes
            correlation_id: Request correlation ID
            
        Returns:
            Risk assessment dictionary containing:
                - risk_score: 0-100
                - severity: low/medium/high/critical
                - breaking_changes: List of potential breaking changes
                - affected_components: List of affected components
                - rollback_plan: Description of rollback approach
                - requires_manual_approval: Boolean
                - safe_to_auto_merge: Boolean
        """
        # Check if there are any changes to assess
        if not suggested_fixes:
            logger.info("No changes proposed, skipping risk assessment", correlation_id=correlation_id)
            return {
                "risk_score": 0,
                "severity": "none",
                "safe_to_auto_merge": True,
                "requires_manual_approval": False,
                "breaking_changes": [],
                "affected_components": [],
                "rollback_plan": "No changes to rollback",
                "message": "No changes proposed"
            }

        logger.debug(
            f"Assessing risk for {len(suggested_fixes)} proposed changes",
            correlation_id=correlation_id
        )

        try:
            # Build assessment prompt using centralized prompt builder
            prompt = build_risk_assessor_prompt(pipeline_yaml, suggested_fixes)
            
            # Get LLM assessment
            raw_response = self.llm_client.chat_completion(
                system_prompt=RISK_ASSESSOR_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_format={"type": "json_object"},
                correlation_id=correlation_id
            )
            
            # Parse and validate response
            risk_assessment = self.llm_client.parse_json_response(raw_response, correlation_id)
            
            # Validate structure
            self._validate_assessment(risk_assessment, correlation_id)
            
            # Log summary
            logger.info(
                f"Risk Assessment: score={risk_assessment.get('risk_score', 0)}/100, "
                f"severity={risk_assessment.get('severity', 'unknown')}, "
                f"safe_to_merge={risk_assessment.get('safe_to_auto_merge', False)}, "
                f"manual_approval={risk_assessment.get('requires_manual_approval', False)}, "
                f"breaking_changes={len(risk_assessment.get('breaking_changes', []))}, "
                f"affected_components={len(risk_assessment.get('affected_components', []))}",
                correlation_id=correlation_id
            )

            return risk_assessment

        except Exception as e:
            logger.exception(f"Risk assessment failed: {e}", correlation_id=correlation_id)
            raise RiskAssessorError(f"Failed to assess risk: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute risk assessment within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with risk_assessment
        """
        correlation_id = state.get("correlation_id")
        suggested_fixes = state.get("analysis_result", {}).get("suggested_fixes", [])

        try:
            risk_assessment = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                suggested_fixes=suggested_fixes,
                correlation_id=correlation_id
            )

            state["risk_assessment"] = risk_assessment

            # Check for critical risk that should block workflow
            if self._is_critical_risk(risk_assessment):
                state["error"] = "Critical risk requires manual review"
                logger.error("Critical risk detected - blocking workflow", correlation_id=correlation_id)
                
        except RiskAssessorError as e:
            logger.error(f"Risk assessment failed: {e}", correlation_id=correlation_id)
            # Don't block workflow on assessment failure, but log it
            state["risk_assessment"] = {
                "risk_score": 50,  # Default to medium risk
                "severity": SEVERITY_MEDIUM,
                "error": str(e)
            }

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for risk assessment in state
        """
        return "risk_assessment"

    def _validate_assessment(self, assessment: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        """
        Validate risk assessment structure.
        
        Args:
            assessment: Risk assessment dictionary
            correlation_id: Request correlation ID
            
        Raises:
            RiskAssessorError: If assessment structure is invalid
        """
        required_keys = [
            "risk_score",
            "severity",
            "breaking_changes",
            "affected_components",
            "rollback_plan",
            "requires_manual_approval",
            "safe_to_auto_merge"
        ]
        
        missing = [k for k in required_keys if k not in assessment]
        if missing:
            logger.error(f"Assessment missing required keys: {missing}", correlation_id=correlation_id)
            raise RiskAssessorError(f"Assessment missing required keys: {missing}")
        
        # Type validation
        if not isinstance(assessment["risk_score"], (int, float)):
            raise RiskAssessorError("risk_score must be a number")
        
        if not isinstance(assessment["breaking_changes"], list):
            raise RiskAssessorError("breaking_changes must be a list")
        
        if not isinstance(assessment["affected_components"], list):
            raise RiskAssessorError("affected_components must be a list")
        
        # Value validation
        risk_score = assessment["risk_score"]
        if not 0 <= risk_score <= 100:
            logger.warning(
                f"Risk score {risk_score} out of range, clamping to 0-100",
                correlation_id=correlation_id
            )
            assessment["risk_score"] = max(0, min(100, risk_score))

    def _is_critical_risk(self, assessment: Dict[str, Any]) -> bool:
        """
        Determine if risk is critical and should block workflow.
        
        Args:
            assessment: Risk assessment dictionary
            
        Returns:
            True if risk is critical
        """
        severity = assessment.get("severity", "").lower()
        risk_score = assessment.get("risk_score", 0)
        
        # Block on critical severity with high risk score
        return severity == "critical" and risk_score >= 90