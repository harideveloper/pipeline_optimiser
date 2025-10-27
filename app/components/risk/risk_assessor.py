"""
Risk Assessor - Evaluates risk of applied pipeline optimisations.
"""

from typing import Dict, Any, List, Optional

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.utils.llm_client import LLMClient
from app.config import config
from app.exceptions import RiskAssessorError
from app.components.risk.prompt import RISK_ASSESSOR_SYSTEM_PROMPT, build_risk_context

logger = get_logger(__name__, "RiskAssessor")


class RiskAssessor(BaseService):
    """Risk assessment service that evaluates applied pipeline optimisations."""

    def __init__(self, model: str = None, temperature: float = None, max_tokens: int = None):
        super().__init__(agent_name="risk_assessment")
        
        cfg = config.get_risk_config()
        self.model = model or cfg["model"]
        self.temperature = temperature if temperature is not None else cfg["temperature"]
        self.max_tokens = max_tokens or cfg["max_tokens"]
        
        self.llm_client = LLMClient(model=self.model, temperature=self.temperature)
        
        logger.debug(f"Initialised Risk Assessor: model={self.model}, temperature={self.temperature}", correlation_id="INIT")

    def run(
        self, 
        state: Dict[str, Any],
        issues_detected: List[Dict[str, Any]],
        applied_fixes: List[Dict[str, Any]],
        original_yaml: str,
        optimised_yaml: str
    ) -> Dict[str, Any]:
        """Assess risk of applied optimisations."""
        correlation_id = state.get("correlation_id")
        
        if not applied_fixes or len(applied_fixes) == 0:
            logger.info("No changes applied - zero risk", correlation_id=correlation_id)
            return {
                "overall_risk": "low",
                "risk_score": 0,
                "risks": [],
                "recommendations": ["No changes were applied - pipeline unchanged"],
                "analysis": "No optimisations were applied, so there is no risk from changes."
            }
        
        logger.debug(f"Assessing risk for {len(applied_fixes)} applied changes", correlation_id=correlation_id)
        
        try:
            heuristic_score = self._calculate_heuristic_risk(issues_detected, applied_fixes)
            
            context = build_risk_context(
                issues_detected,
                applied_fixes,
                original_yaml,
                optimised_yaml,
                heuristic_score
            )
            
            raw_response = self.llm_client.chat_completion(
                system_prompt=RISK_ASSESSOR_SYSTEM_PROMPT,
                user_prompt=context,
                max_tokens=self.max_tokens
            )
            
            assessment = self.llm_client.parse_json_response(raw_response, correlation_id)
            assessment = self._validate_and_enhance_assessment(assessment, heuristic_score, applied_fixes, correlation_id)
            
            logger.info(
                f"Risk assessment complete: {assessment['overall_risk'].upper()} risk "
                f"(score: {assessment['risk_score']}/10) for {len(applied_fixes)} changes",
                correlation_id=correlation_id
            )
            
            return assessment
            
        except RiskAssessorError as e:
            logger.error(f"Risk assessment failed: {e}", correlation_id=correlation_id)
            raise
        except Exception as e:
            error_msg = f"Failed to assess risk: {e}"
            logger.error(error_msg, correlation_id=correlation_id)
            raise RiskAssessorError(error_msg)

    def _calculate_heuristic_risk(self, issues: List[Dict[str, Any]], fixes: List[Dict[str, Any]]) -> float:
        """Calculate initial risk score using heuristics."""
        score = 0.0
        
        num_fixes = len(fixes)
        if num_fixes >= 5:
            score += 3
        elif num_fixes >= 3:
            score += 2
        elif num_fixes >= 1:
            score += 1
        
        severity_weights = {"high": 1.5, "medium": 1.0, "low": 0.5}
        for issue in issues:
            severity = issue.get("severity", "medium").lower()
            score += severity_weights.get(severity, 1.0)
        
        risky_keywords = {
            "security": 2.0,
            "deploy": 1.5,
            "authentication": 2.0,
            "credential": 2.0,
            "permission": 1.5,
            "docker": 1.0,
            "production": 1.5
        }
        
        for fix in fixes:
            fix_text = str(fix).lower()
            for keyword, weight in risky_keywords.items():
                if keyword in fix_text:
                    score += weight
                    break
        
        return min(10.0, max(0.0, score))

    def _validate_and_enhance_assessment(
        self, 
        assessment: Dict[str, Any],
        heuristic_score: float,
        applied_fixes: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate and enhance risk assessment with additional logic."""
        validated = {
            "overall_risk": assessment.get("overall_risk", "medium"),
            "risk_score": assessment.get("risk_score", 5.0),
            "risks": assessment.get("risks", []),
            "recommendations": assessment.get("recommendations", []),
            "analysis": assessment.get("analysis", "No detailed analysis provided"),
            "changes_count": len(applied_fixes),
            "heuristic_score": heuristic_score
        }
        
        valid_levels = ["low", "medium", "high"]
        if validated["overall_risk"] not in valid_levels:
            logger.warning(f"Invalid risk level '{validated['overall_risk']}', defaulting to 'medium'", correlation_id=correlation_id)
            validated["overall_risk"] = "medium"
        
        try:
            risk_score = float(validated["risk_score"])
            validated["risk_score"] = max(0, min(10, risk_score))
        except (ValueError, TypeError):
            logger.warning(f"Invalid risk score '{validated['risk_score']}', using heuristic: {heuristic_score}", correlation_id=correlation_id)
            validated["risk_score"] = heuristic_score
        
        score = validated["risk_score"]
        expected_level = "low" if score < 4 else "medium" if score < 7 else "high"
        
        if validated["overall_risk"] != expected_level:
            logger.debug(f"Adjusting risk level from {validated['overall_risk']} to {expected_level} to match score {score}", correlation_id=correlation_id)
            validated["overall_risk"] = expected_level
        
        if not isinstance(validated["risks"], list):
            validated["risks"] = []
        if not isinstance(validated["recommendations"], list):
            validated["recommendations"] = []
        
        if not validated["recommendations"]:
            validated["recommendations"] = [
                "Test the optimised pipeline in a non-production environment",
                "Review the changes carefully before merging",
                "Monitor the first few runs after deployment"
            ]
        
        return validated

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute risk assessment within workflow."""
        correlation_id = state.get("correlation_id")
        
        optimisation_result = state.get("optimisation_result", {})
        
        if not optimisation_result:
            logger.warning("No optimisation results found in state - checking analysis_result", correlation_id=correlation_id)
            
            analysis_result = state.get("analysis_result", {})
            if not analysis_result:
                logger.warning("No optimisation or analysis results to assess", correlation_id=correlation_id)
                state["risk_assessment"] = {
                    "overall_risk": "low",
                    "risk_score": 0,
                    "risks": [],
                    "recommendations": ["No changes to assess"],
                    "analysis": "No optimisation results available for risk assessment"
                }
                return state
            
            issues_detected = analysis_result.get("issues_detected", [])
            applied_fixes = [{"fix": fix} for fix in analysis_result.get("suggested_fixes", [])]
        else:
            issues_detected = optimisation_result.get("issues_detected", [])
            applied_fixes = optimisation_result.get("applied_fixes", [])
        
        original_yaml = state.get("pipeline_yaml", "")
        optimised_yaml = state.get("optimised_yaml", "")
        
        try:
            assessment = self.run(
                state=state,
                issues_detected=issues_detected,
                applied_fixes=applied_fixes,
                original_yaml=original_yaml,
                optimised_yaml=optimised_yaml
            )
            state["risk_assessment"] = assessment
        except Exception as e:
            logger.error(f"Risk assessment execution failed: {e}", correlation_id=correlation_id)
            state["risk_assessment"] = {
                "overall_risk": "medium",
                "risk_score": 5,
                "risks": [{"category": "error", "description": str(e), "severity": "medium"}],
                "recommendations": [
                    "Risk assessment failed - proceed with caution",
                    "Manually review all changes before deployment"
                ],
                "analysis": f"Error during risk assessment: {e}"
            }
        
        return state

    def _get_artifact_key(self) -> Optional[str]:
        return "risk_assessment"