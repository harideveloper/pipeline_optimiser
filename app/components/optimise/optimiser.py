"""
Pipeline Optimiser - Two-stage pipeline optimisation using Claude Sonnet.
Combines analysis and fixing into a single efficient component.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
import anthropic

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.config import config
from app.exceptions import AnalysisError, FixerError
from app.components.optimise.prompt import OPTIMISER_SYSTEM_PROMPT, OPTIMISER_EXECUTION_PROMPT

logger = get_logger(__name__, "Optimiser")


class Optimiser(BaseService):
    """
    Two-stage pipeline optimiser: Analysis → Execution
    """

    def __init__(
        self,
        model: str = None,
        temperature: float = 0,
        seed: int = 42,
        max_tokens: int = 4096
    ):
        """
        Initialise Optimiser
        
        Args:
            model: llm model name 
            temperature: Sampling temperature (0 for deterministic)
            seed: Random seed for deterministic outputs
            max_tokens: Maximum tokens per response
        """
        super().__init__(agent_name="optimise")
        
        # Model configuration
        self.model = model or "claude-sonnet-4-20250514"
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        logger.info(
            f"Initialized PipelineOptimiser: model={self.model}, "
            f"temperature={self.temperature}, seed={self.seed}",
            correlation_id="INIT"
        )

    def run(
        self,
        pipeline_yaml: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        optimise pipeline YAML using two-stage approach.
        
        Stage 1: Analyze pipeline and identify issues
        Stage 2: Apply optimisations and generate improved YAML
        
        Args:
            pipeline_yaml: Pipeline YAML content to optimise
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Dictionary containing:
                - optimised_yaml: optimised pipeline YAML
                - issues_detected: List of issues found
                - applied_fixes: List of fixes applied
                - expected_improvement: Expected performance gain
                - analysis: Full analysis details
                
        Raises:
            AnalysisError: If analysis stage fails
            FixerError: If execution stage fails
        """
        # Input validation
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            raise AnalysisError("pipeline_yaml must be a non-empty string")
        
        logger.info("Starting two-stage pipeline optimisation", correlation_id=correlation_id)
        
        try:
            # Stage 1: Analysis
            analysis = self._analyze_pipeline(pipeline_yaml, correlation_id)
            
            issues_count = len(analysis.get("issues", []))
            changes_count = len(analysis.get("recommended_changes", []))
            
            logger.info(
                f"Analysis complete: {issues_count} issues, {changes_count} recommendations",
                correlation_id=correlation_id
            )
            
            # Log issues details at DEBUG level
            if issues_count > 0:
                logger.debug(
                    f"Issues detected: {json.dumps(analysis.get('issues', []), indent=2)}",
                    correlation_id=correlation_id
                )
            
            # Stage 2: Execution
            execution = self._execute_optimisations(pipeline_yaml, analysis, correlation_id)
            
            fixes_count = len(execution.get("applied_fixes", []))
            
            # Validate optimised YAML
            self._validate_yaml(execution["optimised_yaml"], correlation_id)
            
            # Log applied fixes at DEBUG level
            if fixes_count > 0:
                logger.debug(
                    f"Applied fixes: {json.dumps(execution.get('applied_fixes', []), indent=2)}",
                    correlation_id=correlation_id
                )
            
            # Log optimised YAML at DEBUG level (ADDED - This was missing!)
            logger.debug(
                f"Original YAML:\n{pipeline_yaml}\n\nOptimised YAML:\n{execution['optimised_yaml']}",
                correlation_id=correlation_id
            )
            
            # Calculate expected improvement
            expected_improvement = self._calculate_improvement(
                analysis.get("issues", []),
                execution.get("applied_fixes", [])
            )
            
            # Combine results
            result = {
                "optimised_yaml": execution["optimised_yaml"],
                "issues_detected": analysis.get("issues", []),
                "applied_fixes": execution.get("applied_fixes", []),
                "expected_improvement": expected_improvement,
                "analysis": analysis,
                "is_fixable": len(execution.get("applied_fixes", [])) > 0
            }
            
            # Single consolidated success log (CONSOLIDATED - removed duplicates)
            logger.info(
                f"Execution complete: {fixes_count} fixes applied",
                correlation_id=correlation_id
            )
            
            logger.info(
                f"optimisation complete: {issues_count} issues -> {fixes_count} fixes applied",
                correlation_id=correlation_id
            )
            
            return result
            
        except anthropic.APIError as e:
            logger.error(
                f"Anthropic API error: {str(e)[:200]}",
                correlation_id=correlation_id
            )
            raise AnalysisError(f"API error during optimisation: {e}") from e
        except Exception as e:
            logger.exception(
                f"optimisation failed: {str(e)[:200]}",
                correlation_id=correlation_id
            )
            raise AnalysisError(f"Failed to optimise pipeline: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute optimisation within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with optimisation results
        """
        correlation_id = state.get("correlation_id")
        
        try:
            # Run optimisation
            result = self.run(
                pipeline_yaml=state["pipeline_yaml"],
                correlation_id=correlation_id
            )
            
            # Update state with all results
            state["optimised_yaml"] = result["optimised_yaml"]
            state["analysis_result"] = {
                "issues_detected": result["issues_detected"],
                "suggested_fixes": [fix["fix"] for fix in result["applied_fixes"]],
                "expected_improvement": result["expected_improvement"]["summary"],
                "is_fixable": result["is_fixable"]
            }
            state["optimisation_result"] = result
            
            # Save issues to database if found
            if result["issues_detected"]:
                self._save_issues_to_db(state, result, correlation_id)
            else:
                logger.info(
                    "No issues detected - pipeline is already optimal",
                    correlation_id=correlation_id
                )
            
        except (AnalysisError, FixerError) as e:
            state["error"] = str(e)
            logger.error(
                f"optimisation failed: {str(e)[:200]}",
                correlation_id=correlation_id
            )
        except Exception as e:
            state["error"] = f"Unexpected optimisation error: {e}"
            logger.exception(
                f"Unexpected error: {str(e)[:200]}",
                correlation_id=correlation_id
            )
        
        return state

    def _analyze_pipeline(
        self,
        pipeline_yaml: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stage 1: Analyze pipeline and identify issues.
        
        Args:
            pipeline_yaml: Pipeline YAML to analyze
            correlation_id: Request correlation ID
            
        Returns:
            Analysis dictionary with issues and recommended changes
            
        Raises:
            AnalysisError: If analysis fails
        """
        user_prompt = f"Analyze this GitHub Actions pipeline:\n\n```yaml\n{pipeline_yaml}\n```"
        
        try:
            raw_result = self._call_llm(
                system_prompt=OPTIMISER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                correlation_id=correlation_id
            )
            
            analysis = self._parse_json_response(raw_result, "analysis", correlation_id)
            
            # Validate analysis structure
            if "issues" not in analysis or "recommended_changes" not in analysis:
                raise AnalysisError(
                    "Analysis response missing required fields (issues or recommended_changes)"
                )
            
            return analysis
            
        except anthropic.APIError as e:
            raise AnalysisError(f"API error during analysis: {e}") from e
        except Exception as e:
            raise AnalysisError(f"Analysis stage failed: {e}") from e

    def _execute_optimisations(
        self,
        pipeline_yaml: str,
        analysis: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stage 2: Apply optimisations to pipeline.
        
        Args:
            pipeline_yaml: Original pipeline YAML
            analysis: Analysis results with recommended changes
            correlation_id: Request correlation ID
            
        Returns:
            Execution dictionary with optimised_yaml and applied_fixes
            
        Raises:
            FixerError: If execution fails
        """
        # Build execution prompt with analysis results
        user_prompt = f"""Original Pipeline:
```yaml
{pipeline_yaml}
```

Analysis Results:
{json.dumps(analysis, indent=2)}

Apply the recommended changes from the analysis to generate an optimised pipeline."""
        
        try:
            raw_result = self._call_llm(
                system_prompt=OPTIMISER_EXECUTION_PROMPT,
                user_prompt=user_prompt,
                correlation_id=correlation_id
            )
            
            execution = self._parse_json_response(raw_result, "execution", correlation_id)
            
            # Validate execution structure
            if "optimised_yaml" not in execution:
                raise FixerError("Execution response missing optimised_yaml")
            
            if "applied_fixes" not in execution:
                logger.warning(
                    "Execution response missing applied_fixes field",
                    correlation_id=correlation_id
                )
                execution["applied_fixes"] = []
            
            return execution
            
        except anthropic.APIError as e:
            raise FixerError(f"API error during execution: {e}") from e
        except Exception as e:
            raise FixerError(f"Execution stage failed: {e}") from e

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Call Claude Sonnet with deterministic parameters.
        
        Args:
            system_prompt: System instructions
            user_prompt: User message
            correlation_id: Request correlation ID
            
        Returns:
            Raw response text from Claude
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return message.content[0].text

    def _parse_json_response(
        self,
        text_output: str,
        stage: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse JSON response from Claude, handling markdown code blocks.
        
        Args:
            text_output: Raw text output from LLM
            stage: Stage name for logging (analysis/execution)
            correlation_id: Request correlation ID
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If JSON parsing fails
        """
        cleaned = text_output.strip()
        
        # Remove markdown code blocks
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        
        try:
            parsed = json.loads(cleaned)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse {stage} JSON: {e}",
                correlation_id=correlation_id
            )
            logger.debug(
                f"Raw {stage} output (first 500 chars): {text_output[:500]}",
                correlation_id=correlation_id
            )
            raise ValueError(f"Invalid JSON from {stage} stage: {e}") from e

    def _validate_yaml(
        self,
        yaml_content: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Validate YAML syntax and structure.
        
        Args:
            yaml_content: YAML content to validate
            correlation_id: Request correlation ID
            
        Raises:
            FixerError: If YAML is invalid
        """
        try:
            parsed_yaml = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(
                f"optimised YAML is invalid: {e}",
                correlation_id=correlation_id
            )
            raise FixerError(f"optimised YAML is invalid: {e}") from e
        
        # Validate required top-level keys
        required_top_level = {
            "name": ["name"],
            "on": ["on", True],
            "jobs": ["jobs"]
        }
        
        for key_name, acceptable_keys in required_top_level.items():
            if not any(k in parsed_yaml for k in acceptable_keys):
                raise FixerError(
                    f"optimised YAML missing required top-level key: '{key_name}'"
                )
        
        if not parsed_yaml.get("jobs"):
            raise FixerError("optimised YAML has no jobs defined")

    def _calculate_improvement(
        self,
        issues: List[Dict[str, Any]],
        applied_fixes: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Calculate expected improvements based on issues and fixes.
        
        Args:
            issues: List of detected issues
            applied_fixes: List of applied fixes
            
        Returns:
            Dictionary with improvement estimates
        """
        time_saved = "0 minutes per run"
        cost = "None"
        
        # Count fix types
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

    def _save_issues_to_db(
        self,
        state: Dict[str, Any],
        result: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save detected issues to database.
        
        Args:
            state: Current workflow state
            result: optimisation result
            correlation_id: Request correlation ID
        """
        issues_detected = result.get("issues_detected", [])
        applied_fixes = result.get("applied_fixes", [])
        
        # Map fixes to issues for database storage
        issues = []
        for issue in issues_detected:
            # Find matching fix
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
            self.repository.save_issues(
                run_id=state["run_id"],
                issues=issues,
                correlation_id=correlation_id
            )
            logger.debug(
                f"Stored {len(issues)} issues in database",
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning(
                f"Failed to store issues in database: {str(e)[:200]}",
                correlation_id=correlation_id
            )

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for optimised YAML in state
        """
        return "optimised_yaml"