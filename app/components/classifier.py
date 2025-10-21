"""
Workflow Classifier Agent - Analyzes GitHub Actions workflows
Classifies workflow type, risk level, and creates execution strategy
"""

import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.constants import (
    WORKFLOW_TYPE_CI,
    WORKFLOW_TYPE_CD,
    WORKFLOW_TYPE_RELEASE,
    WORKFLOW_TYPE_SCHEDULED,
    WORKFLOW_TYPE_MANUAL,
    WORKFLOW_TYPE_UNKNOWN,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_LEVEL_HIGH,
    CHANGE_SCOPE_DOCS_ONLY,
    CHANGE_SCOPE_CODE,
    CHANGE_SCOPE_INFRASTRUCTURE,
    CHANGE_SCOPE_DEPLOYMENT,
    TOOL_VALIDATE,
    TOOL_ANALYSE,
    TOOL_FIX,
    TOOL_RISK_ASSESSMENT,
    TOOL_SECURITY_SCAN,
    TOOL_REVIEW,
    TOOL_RESOLVE
)
from app.exceptions import ClassificationError

logger = get_logger(__name__, "Classifier")


@dataclass
class ClassifierProfile:
    """Profile of a GitHub Actions workflow"""
    workflow_type: str
    risk_level: str
    change_scope: str
    strategy: Dict[str, Any]
    characteristics: Dict[str, Any]


class Classifier(BaseService):
    """
    Classifies GitHub Actions workflows using deterministic rule-based analysis.
    No LLM calls - purely algorithmic classification ( possibility to change this to LLM based classification)
    """

    def __init__(self):
        """Initialize Classifier."""
        super().__init__(agent_name="classify")
        logger.debug("Initialized Classifier", correlation_id="INIT")

    def run(self, **kwargs) -> Any:
        """
        External usage entry point.
        
        Args:
            **kwargs: Must contain 'state' with pipeline_yaml
            
        Returns:
            Updated state with classification results
        """
        state = kwargs.get("state", {})
        return self._execute(state)

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node execution for classification.
        
        Args:
            state: Current workflow state containing pipeline_yaml
            
        Returns:
            Updated state with workflow_type, risk_level, and execution plan
        """
        correlation_id = state.get("correlation_id")

        pipeline_yaml = state.get("pipeline_yaml", "")
        build_log = state.get("build_log", "")

        try:
            # Classify the workflow
            profile = self._classify(pipeline_yaml, build_log, correlation_id)

            # Update state with classification info
            state["workflow_type"] = profile.workflow_type
            state["risk_level"] = profile.risk_level
            state["plan"] = self._generate_plan(profile.risk_level, state.get("pr_create", False))
            state["plan_index"] = 0

            logger.info(
                f"Classification complete: type={profile.workflow_type}, "
                f"risk={profile.risk_level}, plan={len(state['plan'])} steps",
                correlation_id=correlation_id
            )

        except ClassificationError as e:
            logger.error(f"Classification failed: {e}", correlation_id=correlation_id)
            # Set default values to allow workflow to continue
            state["workflow_type"] = WORKFLOW_TYPE_UNKNOWN
            state["risk_level"] = RISK_LEVEL_MEDIUM
            state["plan"] = self._generate_plan(RISK_LEVEL_MEDIUM, state.get("pr_create", False))
            state["plan_index"] = 0

        return state

    def _classify(
        self,
        pipeline_yaml: str,
        build_log: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ClassifierProfile:
        """
        Classify workflow based on YAML content.
        
        Args:
            pipeline_yaml: GitHub Actions workflow YAML
            build_log: Optional build log (unused currently)
            correlation_id: Request correlation ID
            
        Returns:
            ClassifierProfile with classification results
            
        Raises:
            ClassificationError: If YAML is invalid or parsing fails
        """
        # Validate input
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            return self._get_default_profile()

        # Parse YAML
        try:
            workflow = yaml.safe_load(pipeline_yaml)
            if workflow is None or not isinstance(workflow, dict):
                logger.error("Pipeline YAML invalid or empty", correlation_id=correlation_id)
                return self._get_default_profile()
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing failed: {e}", correlation_id=correlation_id)
            return self._get_default_profile()

        # Perform classification
        workflow_type = self._detect_workflow_type(workflow, correlation_id)
        risk_level = self._calculate_risk_level(workflow, correlation_id)
        change_scope = self._detect_change_scope(workflow, correlation_id)
        characteristics = self._extract_characteristics(workflow, correlation_id)
        strategy = self._create_strategy(workflow_type, risk_level, change_scope, correlation_id)

        profile = ClassifierProfile(
            workflow_type=workflow_type,
            risk_level=risk_level,
            change_scope=change_scope,
            strategy=strategy,
            characteristics=characteristics
        )

        logger.debug(
            f"Classified: type={workflow_type}, risk={risk_level}, scope={change_scope}",
            correlation_id=correlation_id
        )

        return profile

    def _generate_plan(self, risk_level: str, pr_create: bool) -> list[str]:
        """
        Generate execution plan based on risk level.
        
        Args:
            risk_level: Risk level (HIGH/MEDIUM/LOW)
            pr_create: Whether to create a pull request
            
        Returns:
            Ordered list of tool names to execute
        """
        base_plan = [TOOL_VALIDATE, TOOL_ANALYSE, TOOL_FIX]

        if risk_level == RISK_LEVEL_HIGH:
            plan = base_plan + [TOOL_RISK_ASSESSMENT, TOOL_SECURITY_SCAN, TOOL_REVIEW]
        elif risk_level == RISK_LEVEL_MEDIUM:
            plan = base_plan + [TOOL_SECURITY_SCAN, TOOL_REVIEW]
        else:  # LOW
            plan = base_plan + [TOOL_REVIEW]

        if pr_create:
            plan.append(TOOL_RESOLVE)

        return plan

    def _detect_workflow_type(
        self,
        workflow: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Detect workflow type from triggers.
        
        Args:
            workflow: Parsed workflow dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Workflow type (CI/CD/RELEASE/SCHEDULED/MANUAL/UNKNOWN)
        """
        # Get triggers (handle both 'on' and True keys due to YAML parsing)
        triggers = workflow.get('on', workflow.get(True, {}))
        
        # Normalize triggers to dictionary format
        if isinstance(triggers, str):
            triggers = {triggers: {}}
        elif isinstance(triggers, list):
            triggers = {t: {} for t in triggers}
        elif not isinstance(triggers, dict) or not triggers:
            logger.debug("No valid triggers found", correlation_id=correlation_id)
            triggers = {}

        has_pr = 'pull_request' in triggers
        has_push = 'push' in triggers
        has_deployment = self._has_deployment_job(workflow, correlation_id)
        
        # Classification logic
        if has_pr and not has_deployment:
            return WORKFLOW_TYPE_CI
        
        if has_push and has_deployment:
            push_config = triggers.get('push', {})
            branches = push_config.get('branches', [])
            if branches and any(b in ['main', 'master', 'production'] for b in branches):
                return WORKFLOW_TYPE_CD
        
        if has_pr and has_push and not has_deployment:
            return WORKFLOW_TYPE_CI
        
        if has_push and not has_deployment:
            return WORKFLOW_TYPE_CI
        
        if any(k in triggers for k in ['release', 'create', 'published']):
            return WORKFLOW_TYPE_RELEASE
        
        if 'schedule' in triggers:
            return WORKFLOW_TYPE_SCHEDULED
        
        if 'workflow_dispatch' in triggers:
            return WORKFLOW_TYPE_MANUAL

        logger.info("Could not determine workflow type, using UNKNOWN", correlation_id=correlation_id)
        return WORKFLOW_TYPE_UNKNOWN
    
    def _has_deployment_job(
        self,
        workflow: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Check if workflow has deployment-related jobs.
        
        Args:
            workflow: Parsed workflow dictionary
            correlation_id: Request correlation ID
            
        Returns:
            True if deployment-related jobs found
        """
        jobs = workflow.get('jobs', {})
        
        deployment_keywords = ['deploy', 'release', 'publish', 'production']
        cloud_keywords = ['kubectl', 'aws', 'azure', 'gcp', 'heroku']
        
        for job_name, job in jobs.items():
            # Check job name
            if any(keyword in job_name.lower() for keyword in deployment_keywords):
                return True
            
            # Check for environment (indicates deployment)
            if 'environment' in job:
                return True
            
            # Check steps for deployment commands
            steps = job.get('steps', [])
            for step in steps:
                step_str = str(step).lower()
                if any(keyword in step_str for keyword in deployment_keywords + cloud_keywords):
                    return True
        
        return False

    def _calculate_risk_level(
        self,
        workflow: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Calculate risk level based on workflow content.
        
        Uses a scoring system to determine risk:
        - Production deployments: +30
        - Cloud deployments: +20
        - Infrastructure as code: +25
        - Secrets usage: +10
        - Database operations: +15
        - Container operations: +5
        
        Args:
            workflow: Parsed workflow dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Risk level (HIGH >= 50, MEDIUM >= 20, LOW < 20)
        """
        risk_score = 0
        jobs = workflow.get('jobs', {})

        for job_name, job in jobs.items():
            steps = job.get('steps', [])
            job_env = job.get('env', {})
            job_str = f"{job_name} {str(job_env)} {str(job.get('environment', ''))}".lower()
            
            # Production/deployment indicators
            if any(keyword in job_str for keyword in ['production', 'prod', 'deploy', 'release']):
                risk_score += 30
            
            for step in steps:
                step_str = str(step).lower()
                
                # Cloud deployment tools
                if any(keyword in step_str for keyword in ['deploy', 'aws', 'azure', 'gcp', 'kubectl']):
                    risk_score += 20
                
                # Infrastructure as code
                if any(keyword in step_str for keyword in ['terraform', 'cloudformation', 'pulumi']):
                    risk_score += 25
                
                # Secrets usage
                if 'secret' in step_str or '${{' in str(step):
                    risk_score += 10
                
                # Database operations
                if any(keyword in step_str for keyword in ['migrate', 'database', 'db', 'sql']):
                    risk_score += 15
                
                # Container operations
                if any(keyword in step_str for keyword in ['docker', 'container', 'registry']):
                    risk_score += 5

        # Determine risk level from score
        if risk_score >= 50:
            return RISK_LEVEL_HIGH
        elif risk_score >= 20:
            return RISK_LEVEL_MEDIUM
        else:
            return RISK_LEVEL_LOW

    def _detect_change_scope(
        self,
        workflow: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Detect the scope of changes in the workflow.
        
        Args:
            workflow: Parsed workflow dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Change scope (DEPLOYMENT/CODE/DOCS_ONLY/INFRASTRUCTURE)
        """
        jobs = workflow.get('jobs', {})
        
        has_tests = False
        has_build = False
        has_deploy = False
        has_docs = False
        
        for job_name, job in jobs.items():
            job_str = f"{job_name} {str(job)}".lower()
            
            if any(keyword in job_str for keyword in ['test', 'lint', 'check']):
                has_tests = True
            
            if any(keyword in job_str for keyword in ['build', 'compile', 'package']):
                has_build = True
            
            if any(keyword in job_str for keyword in ['deploy', 'release', 'publish']):
                has_deploy = True
            
            if any(keyword in job_str for keyword in ['docs', 'documentation']):
                has_docs = True

        # Determine scope based on detected activities
        if has_deploy:
            return CHANGE_SCOPE_DEPLOYMENT
        elif has_build or has_tests:
            return CHANGE_SCOPE_CODE
        elif has_docs and not (has_build or has_tests or has_deploy):
            return CHANGE_SCOPE_DOCS_ONLY
        else:
            return CHANGE_SCOPE_INFRASTRUCTURE

    def _extract_characteristics(
        self,
        workflow: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract additional workflow characteristics for context.
        
        Args:
            workflow: Parsed workflow dictionary
            correlation_id: Request correlation ID
            
        Returns:
            Dictionary of workflow characteristics
        """
        jobs = workflow.get('jobs', {})
        
        characteristics = {
            'job_count': len(jobs),
            'has_matrix': False,
            'has_secrets': False,
            'has_artifacts': False,
            'has_caching': False,
            'uses_actions': [],
            'runners': []
        }

        for job_name, job in jobs.items():
            # Check for matrix strategy
            if 'strategy' in job and 'matrix' in job['strategy']:
                characteristics['has_matrix'] = True
            
            # Check for secrets usage
            if 'env' in job or 'secrets' in str(job):
                characteristics['has_secrets'] = True
            
            # Track runners
            runner = job.get('runs-on', 'unknown')
            if runner not in characteristics['runners']:
                characteristics['runners'].append(runner)
            
            # Analyze steps
            for step in job.get('steps', []):
                if 'uses' in step:
                    action = step['uses']
                    if action not in characteristics['uses_actions']:
                        characteristics['uses_actions'].append(action)
                    
                    # Check for caching
                    if 'cache' in action.lower():
                        characteristics['has_caching'] = True
                    
                    # Check for artifacts
                    if 'upload-artifact' in action.lower() or 'download-artifact' in action.lower():
                        characteristics['has_artifacts'] = True

        return characteristics

    def _create_strategy(
        self,
        workflow_type: str,
        risk_level: str,
        change_scope: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create execution strategy based on classification.
        
        Args:
            workflow_type: Classified workflow type
            risk_level: Calculated risk level
            change_scope: Detected change scope
            correlation_id: Request correlation ID
            
        Returns:
            Strategy dictionary with mandatory/optional/recommended tools
        """
        strategies = {
            (WORKFLOW_TYPE_CI, RISK_LEVEL_LOW, CHANGE_SCOPE_DOCS_ONLY): {
                "mandatory": ["ingest", "validate"],
                "optional": ["risk_assessment", "security_scan", "review"],
                "recommended": ["analyze"],
                "focus": "speed",
                "rationale": "Simple CI with docs-only changes"
            },
            (WORKFLOW_TYPE_CI, RISK_LEVEL_LOW, CHANGE_SCOPE_CODE): {
                "mandatory": ["ingest", "validate", "analyze"],
                "optional": ["risk_assessment", "security_scan"],
                "recommended": ["fix", "review"],
                "focus": "speed",
                "rationale": "Low-risk CI workflow"
            },
            (WORKFLOW_TYPE_CI, RISK_LEVEL_MEDIUM, CHANGE_SCOPE_CODE): {
                "mandatory": ["ingest", "validate", "analyze", "security_scan"],
                "optional": ["risk_assessment"],
                "recommended": ["fix", "review"],
                "focus": "balanced",
                "rationale": "Standard CI workflow"
            },
            (WORKFLOW_TYPE_CD, RISK_LEVEL_MEDIUM, CHANGE_SCOPE_DEPLOYMENT): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan"],
                "optional": [],
                "recommended": ["fix", "review"],
                "focus": "safety",
                "rationale": "CD workflow"
            },
            (WORKFLOW_TYPE_CD, RISK_LEVEL_HIGH, CHANGE_SCOPE_DEPLOYMENT): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan", "review"],
                "optional": [],
                "recommended": ["fix"],
                "focus": "safety",
                "rationale": "High-risk CD workflow"
            },
            (WORKFLOW_TYPE_RELEASE, RISK_LEVEL_MEDIUM, CHANGE_SCOPE_DEPLOYMENT): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan"],
                "optional": [],
                "recommended": ["fix", "review"],
                "focus": "quality",
                "rationale": "Release workflow"
            },
            (WORKFLOW_TYPE_RELEASE, RISK_LEVEL_HIGH, CHANGE_SCOPE_DEPLOYMENT): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan", "review"],
                "optional": [],
                "recommended": ["fix"],
                "focus": "quality",
                "rationale": "High-risk release"
            },
        }

        key = (workflow_type, risk_level, change_scope)
        
        # Try exact match first
        if key in strategies:
            return strategies[key]
        
        # Try fallback strategies
        fallback_keys = [
            (workflow_type, risk_level, CHANGE_SCOPE_CODE),
            (workflow_type, RISK_LEVEL_MEDIUM, change_scope),
            (WORKFLOW_TYPE_CI, RISK_LEVEL_MEDIUM, CHANGE_SCOPE_CODE)
        ]
        
        for fallback_key in fallback_keys:
            if fallback_key in strategies:
                logger.info(
                    f"Using fallback strategy: {key} -> {fallback_key}",
                    correlation_id=correlation_id
                )
                return strategies[fallback_key]
        
        # Default strategy
        return {
            "mandatory": ["ingest", "validate", "analyze"],
            "optional": ["risk_assessment", "security_scan"],
            "recommended": ["fix", "review"],
            "focus": "balanced",
            "rationale": "Default strategy"
        }

    def _get_default_profile(self) -> ClassifierProfile:
        """
        Return default profile when classification fails.
        
        Returns:
            Default ClassifierProfile with moderate settings
        """
        return ClassifierProfile(
            workflow_type=WORKFLOW_TYPE_UNKNOWN,
            risk_level=RISK_LEVEL_MEDIUM,
            change_scope=CHANGE_SCOPE_CODE,
            strategy={
                "mandatory": ["ingest", "validate", "analyze"],
                "optional": ["risk_assessment", "security_scan"],
                "recommended": ["fix", "review"],
                "focus": "balanced",
                "rationale": "Default strategy due to classification failure"
            },
            characteristics={}
        )
    
    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for classifier results in state
        """
        return "classifier"