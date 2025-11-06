"""
Pipeline Optimiser - Two-stage pipeline optimisation using Claude Sonnet.
"""

import json
import yaml
from typing import Dict, Any, Optional, List

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.llm.llm_client import LLMClient
from app.config import config
from app.exceptions import OptimiserError
from app.components.optimise.prompt import (
    OPTIMISER_ANALYSE_SYSTEM_PROMPT, 
    OPTIMISER_EXECUTION_SYSTEM_PROMPT, 
    build_analysis_user_prompt,
    build_execution_user_prompt
)

logger = get_logger(__name__, "Optimiser")


class Optimiser(BaseService):
    """Pipeline optimiser: Analysis → Execution"""

    def __init__(self, model: str = None, temperature: float = None, max_tokens: int = None):
        super().__init__(agent_name="optimise")
        
        cfg = config.get_optimiser_config()
        self.model = model or cfg["model"]
        self.temperature = temperature if temperature is not None else cfg["temperature"]
        self.max_tokens = max_tokens or cfg["max_tokens"]
        
        self.llm_client = LLMClient(model=self.model, temperature=self.temperature)
        
        logger.debug(
            f"Initialised Optimiser: model={self.model}, temperature={self.temperature}, max_tokens={self.max_tokens}",
            correlation_id="INIT"
        )

    def run(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise OptimiserError("pipeline_yaml must be a non-empty string")
        
        logger.debug("Starting optimiser", correlation_id=correlation_id)
        
        try:
            analysis = self._analyse_pipeline(pipeline_yaml, correlation_id)
            issues_count = len(analysis.get("issues", []))
            changes_count = len(analysis.get("recommended_changes", []))
            
            logger.info(f"Analysis complete: {issues_count} issues, {changes_count} recommendations", correlation_id=correlation_id)
            
            if issues_count > 0:
                logger.debug(f"Issues detected: {json.dumps(analysis.get('issues', []), indent=2)}", correlation_id=correlation_id)
            
            execution = self._execute_optimisations(pipeline_yaml, analysis, correlation_id)
            fixes_count = len(execution.get("applied_fixes", []))
            
            self._validate_yaml(execution["optimised_yaml"], correlation_id)
            
            if fixes_count > 0:
                logger.debug(f"Applied fixes: {json.dumps(execution.get('applied_fixes', []), indent=2)}", correlation_id=correlation_id)
            
            logger.debug(f"Original YAML:\n{pipeline_yaml}\n\nOptimised YAML:\n{execution['optimised_yaml']}", correlation_id=correlation_id)
            
            expected_improvement = self._calculate_improvement(analysis.get("issues", []), execution.get("applied_fixes", []))
            
            result = {
                "optimised_yaml": execution["optimised_yaml"],
                "issues_detected": analysis.get("issues", []),
                "applied_fixes": execution.get("applied_fixes", []),
                "expected_improvement": expected_improvement,
                "analysis": analysis,
                "is_fixable": len(execution.get("applied_fixes", [])) > 0
            }
            
            logger.info(f"Execution complete: {fixes_count} fixes applied", correlation_id=correlation_id)
            logger.info(f"optimisation complete: {issues_count} issues -> {fixes_count} fixes applied", correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            logger.exception(f"optimisation failed: {str(e)[:200]}", correlation_id=correlation_id)
            raise OptimiserError(f"Failed to optimise pipeline: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        correlation_id = state.get("correlation_id")
        
        try:
            result = self.run(pipeline_yaml=state["pipeline_yaml"], correlation_id=correlation_id)
            
            state["optimised_yaml"] = result["optimised_yaml"]
            state["analysis_result"] = {
                "issues_detected": result["issues_detected"],
                "suggested_fixes": [fix["fix"] for fix in result["applied_fixes"]],
                "expected_improvement": result["expected_improvement"]["summary"],
                "is_fixable": result["is_fixable"]
            }
            state["optimisation_result"] = result
            
            if result["issues_detected"]:
                self._save_issues_to_db(state, result, correlation_id)
            else:
                logger.info("No issues detected - pipeline is already optimal", correlation_id=correlation_id)
            
        except OptimiserError as e:
            state["error"] = str(e)
            logger.error(f"optimisation failed: {str(e)[:200]}", correlation_id=correlation_id)
        except Exception as e:
            state["error"] = f"Unexpected optimisation error: {e}"
            logger.exception(f"Unexpected error: {str(e)[:200]}", correlation_id=correlation_id)
        
        return state

    def _analyse_pipeline(self, pipeline_yaml: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        user_prompt = build_analysis_user_prompt(pipeline_yaml)
        
        try:
            raw_result = self._call_llm(system_prompt=OPTIMISER_ANALYSE_SYSTEM_PROMPT, user_prompt=user_prompt, correlation_id=correlation_id)
            analysis = self.llm_client.parse_json_response(raw_result, correlation_id)
            
            if "issues" not in analysis or "recommended_changes" not in analysis:
                raise OptimiserError("Analysis response missing required fields (issues or recommended_changes)")
            
            return analysis
        except Exception as e:
            raise OptimiserError(f"Analysis stage failed: {e}") from e

    def _execute_optimisations(self, pipeline_yaml: str, analysis: Dict[str, Any], correlation_id: Optional[str] = None) -> Dict[str, Any]:
        user_prompt = build_execution_user_prompt(pipeline_yaml, analysis)
        try:
            raw_result = self._call_llm(system_prompt=OPTIMISER_EXECUTION_SYSTEM_PROMPT, user_prompt=user_prompt, correlation_id=correlation_id)
            # execution = self.llm_client.parse_json_response(raw_result, correlation_id)
            execution = self.llm_client.parse_optimiser_response(raw_result, correlation_id)
            
            if "optimised_yaml" not in execution:
                raise OptimiserError("Execution response missing optimised_yaml")
            
            if "applied_fixes" not in execution:
                logger.warning("Execution response missing applied_fixes field", correlation_id=correlation_id)
                execution["applied_fixes"] = []
            
            return execution
        except Exception as e:
            raise OptimiserError(f"Execution stage failed: {e}") from e

    def _call_llm(self, system_prompt: str, user_prompt: str, correlation_id: Optional[str] = None) -> str:
        return self.llm_client.chat_completion(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=self.max_tokens)

    def _validate_yaml(self, yaml_content: str, correlation_id: Optional[str] = None) -> None:
        try:
            parsed_yaml = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"optimised YAML is invalid: {e}", correlation_id=correlation_id)
            raise OptimiserError(f"optimised YAML is invalid: {e}") from e
        
        required_top_level = {
            "name": ["name"],
            "on": ["on", True],
            "jobs": ["jobs"]
        }
        
        for key_name, acceptable_keys in required_top_level.items():
            if not any(k in parsed_yaml for k in acceptable_keys):
                raise OptimiserError(f"optimised YAML missing required top-level key: '{key_name}'")
        
        if not parsed_yaml.get("jobs"):
            raise OptimiserError("optimised YAML has no jobs defined")

    def _calculate_improvement(self, issues: List[Dict[str, Any]], applied_fixes: List[Dict[str, Any]]) -> Dict[str, str]:
        time_saved = "0 minutes per run"
        cost = "None"
        
        has_caching = any("cach" in str(fix).lower() for fix in applied_fixes)
        has_parallel = any("parallel" in str(fix).lower() for fix in applied_fixes)
        
        if has_caching and has_parallel:
            time_saved = "3-5 minutes per run"
            cost = "Reduced CI costs through faster builds and caching"
        elif has_caching:
            time_saved = "2-3 minutes per run"
            cost = "Reduced network usage through caching"
        elif has_parallel:
            time_saved = "1-2 minutes per run"
            cost = "Reduced total execution time"
        
        summary_parts = []
        if len(applied_fixes) > 0:
            summary_parts.append(f"Applied {len(applied_fixes)} optimisation(s)")
            if has_caching:
                summary_parts.append("improved build speed through caching")
            if has_parallel:
                summary_parts.append("enabled parallel execution")
        else:
            summary_parts.append("No optimisations applicable or applied")
        
        return {
            "estimated_time_saved": time_saved,
            "security_improvements": "None",
            "cost_savings": cost,
            "summary": ", ".join(summary_parts) + "."
        }

    def _save_issues_to_db(self, state: Dict[str, Any], result: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        issues_detected = result.get("issues_detected", [])
        applied_fixes = result.get("applied_fixes", [])
        
        issues = []
        for issue in issues_detected:
            fix_text = "TBD"
            for fix in applied_fixes:
                if issue["description"] in fix["issue"] or fix["issue"] in issue["description"]:
                    fix_text = fix["fix"]
                    break
            
            issues.append({
                "type": issue.get("type", "optimisation"),
                "description": issue["description"],
                "severity": issue.get("severity", "medium"),
                "suggested_fix": fix_text,
                "location": issue.get("location", "unknown")
            })
        
        try:
            self.repository.save_issues(run_id=state["run_id"], issues=issues, correlation_id=correlation_id)
            logger.debug(f"Stored {len(issues)} issues in database", correlation_id=correlation_id)
        except Exception as e:
            logger.warning(f"Failed to store issues in database: {str(e)[:200]}", correlation_id=correlation_id)

    def _get_artifact_key(self) -> Optional[str]:
        return "optimised_yaml"