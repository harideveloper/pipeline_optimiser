"""
Workflow Classifier Agent - Analyzes GitHub Actions workflows
Classifies workflow type, risk level, and creates execution strategy
"""

import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.components.base_service import BaseService
from app.utils.logger import get_logger

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
    Classifies GitHub Actions workflows in a BaseAgent style.
    Deterministic; no LLM calls.
    """

    def __init__(self):
        super().__init__(agent_name="classify")
        logger.debug("Initialized Classifier", correlation_id="INIT")

    # =============================================
    # BaseAgent implementations
    # =============================================
    def run(self, **kwargs) -> Any:
        """
        External usage entry point
        """
        state = kwargs.get("state", {})
        return self._execute(state)

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node execution for classification
        """
        correlation_id = state.get("correlation_id")

        pipeline_yaml = state.get("pipeline_yaml", "")
        build_log = state.get("build_log", "")

        profile = self._classify(pipeline_yaml, build_log, correlation_id)

        # Update state with classification info
        state["workflow_type"] = profile.workflow_type
        state["risk_level"] = profile.risk_level
        state["plan"] = self._generate_plan(profile.risk_level, state.get("pr_create", False))
        state["plan_index"] = 0

        return state

    # =============================================
    # Deterministic classification logic
    # =============================================
    def _classify(self, pipeline_yaml: str, build_log: str = None, correlation_id: Optional[str] = None) -> ClassifierProfile:
        if not pipeline_yaml or not isinstance(pipeline_yaml, str) or not pipeline_yaml.strip():
            logger.error("Invalid or empty pipeline YAML", correlation_id=correlation_id)
            return self._get_default_profile()

        try:
            workflow = yaml.safe_load(pipeline_yaml)
            if workflow is None or not isinstance(workflow, dict):
                logger.error("Pipeline YAML invalid or empty", correlation_id=correlation_id)
                return self._get_default_profile()
        except yaml.YAMLError as e:
            logger.error("YAML parsing failed: %s" % str(e), correlation_id=correlation_id)
            return self._get_default_profile()

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

        logger.info(
            "Classified: type=%s, risk=%s, scope=%s" % (workflow_type, risk_level, change_scope),
            correlation_id=correlation_id
        )

        return profile

    # =============================================
    # Plan generation
    # =============================================
    def _generate_plan(self, risk_level: str, pr_create: bool) -> list[str]:
        base_plan = ["validate", "analyse", "fix"]

        if risk_level == "HIGH":
            plan = base_plan + ["risk_assessment", "security_scan", "review"]
        elif risk_level == "MEDIUM":
            plan = base_plan + ["security_scan", "review"]
        else:  # LOW
            plan = base_plan + ["review"]

        if pr_create:
            plan.append("resolve")

        return plan

    def _detect_workflow_type(self, workflow: Dict, correlation_id: Optional[str] = None) -> str:
        """Detect workflow type from triggers"""
        
        triggers = workflow.get('on', workflow.get(True, {}))
        
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
        
        if has_pr and not has_deployment:
            return "CI"
        
        if has_push and has_deployment:
            push_config = triggers.get('push', {})
            branches = push_config.get('branches', [])
            if branches and any(b in ['main', 'master', 'production'] for b in branches):
                return "CD"
        
        if has_pr and has_push and not has_deployment:
            return "CI"
        
        if has_push and not has_deployment:
            return "CI"
        
        if any(k in triggers for k in ['release', 'create', 'published']):
            return "RELEASE"
        
        if 'schedule' in triggers:
            return "SCHEDULED"
        
        if 'workflow_dispatch' in triggers:
            return "MANUAL"

        logger.info("Could not determine workflow type, using UNKNOWN", correlation_id=correlation_id)
        return "UNKNOWN"
    
    def _has_deployment_job(self, workflow: Dict, correlation_id: Optional[str] = None) -> bool:
        """Check if workflow has deployment-related jobs"""
        
        jobs = workflow.get('jobs', {})
        
        for job_name, job in jobs.items():
            if any(keyword in job_name.lower() for keyword in ['deploy', 'release', 'publish', 'production']):
                return True
            
            if 'environment' in job:
                return True
            
            steps = job.get('steps', [])
            for step in steps:
                step_str = str(step).lower()
                if any(keyword in step_str for keyword in ['deploy', 'kubectl', 'aws', 'azure', 'gcp', 'heroku']):
                    return True
        
        return False

    def _calculate_risk_level(self, workflow: Dict, correlation_id: Optional[str] = None) -> str:
        """Calculate risk level based on workflow content"""
        
        risk_score = 0
        jobs = workflow.get('jobs', {})

        for job_name, job in jobs.items():
            steps = job.get('steps', [])
            job_env = job.get('env', {})
            job_str = f"{job_name} {str(job_env)} {str(job.get('environment', ''))}".lower()
            
            if any(keyword in job_str for keyword in ['production', 'prod', 'deploy', 'release']):
                risk_score += 30
            
            for step in steps:
                step_str = str(step).lower()
                
                if any(keyword in step_str for keyword in ['deploy', 'aws', 'azure', 'gcp', 'kubectl']):
                    risk_score += 20
                
                if any(keyword in step_str for keyword in ['terraform', 'cloudformation', 'pulumi']):
                    risk_score += 25
                
                if 'secret' in step_str or '${{' in str(step):
                    risk_score += 10
                
                if any(keyword in step_str for keyword in ['migrate', 'database', 'db', 'sql']):
                    risk_score += 15
                
                if any(keyword in step_str for keyword in ['docker', 'container', 'registry']):
                    risk_score += 5

        if risk_score >= 50:
            return "HIGH"
        elif risk_score >= 20:
            return "MEDIUM"
        else:
            return "LOW"

    def _detect_change_scope(self, workflow: Dict, correlation_id: Optional[str] = None) -> str:
        """Detect the scope of changes in the workflow"""
        
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

        if has_deploy:
            return "DEPLOYMENT"
        elif has_build or has_tests:
            return "CODE"
        elif has_docs and not (has_build or has_tests or has_deploy):
            return "DOCS_ONLY"
        else:
            return "INFRASTRUCTURE"

    def _extract_characteristics(self, workflow: Dict, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract additional workflow characteristics"""
        
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
            if 'strategy' in job and 'matrix' in job['strategy']:
                characteristics['has_matrix'] = True
            
            if 'env' in job or 'secrets' in str(job):
                characteristics['has_secrets'] = True
            
            runner = job.get('runs-on', 'unknown')
            if runner not in characteristics['runners']:
                characteristics['runners'].append(runner)
            
            for step in job.get('steps', []):
                if 'uses' in step:
                    action = step['uses']
                    if action not in characteristics['uses_actions']:
                        characteristics['uses_actions'].append(action)
                    
                    if 'cache' in action.lower():
                        characteristics['has_caching'] = True
                    if 'upload-artifact' in action.lower() or 'download-artifact' in action.lower():
                        characteristics['has_artifacts'] = True

        return characteristics

    def _create_strategy(self, workflow_type: str, risk_level: str, change_scope: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Create execution strategy based on classification"""
        
        strategies = {
            ("CI", "LOW", "DOCS_ONLY"): {
                "mandatory": ["ingest", "validate"],
                "optional": ["risk_assessment", "security_scan", "review"],
                "recommended": ["analyze"],
                "focus": "speed",
                "rationale": "Simple CI with docs-only changes"
            },
            ("CI", "LOW", "CODE"): {
                "mandatory": ["ingest", "validate", "analyze"],
                "optional": ["risk_assessment", "security_scan"],
                "recommended": ["fix", "review"],
                "focus": "speed",
                "rationale": "Low-risk CI workflow"
            },
            ("CI", "MEDIUM", "CODE"): {
                "mandatory": ["ingest", "validate", "analyze", "security_scan"],
                "optional": ["risk_assessment"],
                "recommended": ["fix", "review"],
                "focus": "balanced",
                "rationale": "Standard CI workflow"
            },
            ("CD", "MEDIUM", "DEPLOYMENT"): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan"],
                "optional": [],
                "recommended": ["fix", "review"],
                "focus": "safety",
                "rationale": "CD workflow"
            },
            ("CD", "HIGH", "DEPLOYMENT"): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan", "review"],
                "optional": [],
                "recommended": ["fix"],
                "focus": "safety",
                "rationale": "High-risk CD workflow"
            },
            ("RELEASE", "MEDIUM", "DEPLOYMENT"): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan"],
                "optional": [],
                "recommended": ["fix", "review"],
                "focus": "quality",
                "rationale": "Release workflow"
            },
            ("RELEASE", "HIGH", "DEPLOYMENT"): {
                "mandatory": ["ingest", "validate", "analyze", "risk_assessment", "security_scan", "review"],
                "optional": [],
                "recommended": ["fix"],
                "focus": "quality",
                "rationale": "High-risk release"
            },
        }

        key = (workflow_type, risk_level, change_scope)
        
        if key in strategies:
            return strategies[key]
        
        fallback_keys = [
            (workflow_type, risk_level, "CODE"),
            (workflow_type, "MEDIUM", change_scope),
            ("CI", "MEDIUM", "CODE")
        ]
        
        for fallback_key in fallback_keys:
            if fallback_key in strategies:
                logger.info("Using fallback strategy: %s -> %s" % (key, fallback_key), correlation_id=correlation_id)
                return strategies[fallback_key]
        
        # logger.debug("No strategy match, using default", correlation_id=correlation_id)
        return {
            "mandatory": ["ingest", "validate", "analyze"],
            "optional": ["risk_assessment", "security_scan"],
            "recommended": ["fix", "review"],
            "focus": "balanced",
            "rationale": "Default strategy"
        }

    def _get_default_profile(self) -> ClassifierProfile:
        """Return default profile when classification fails"""
        return ClassifierProfile(
            workflow_type="UNKNOWN",
            risk_level="MEDIUM",
            change_scope="CODE",
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
        """classification artifacts should be saved as artifact"""
        return "classifier"