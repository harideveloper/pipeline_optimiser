"""
Resolver Agent - Resolves pipeline issues by creating PRs with optimised YAML.
"""

import os
from typing import Dict, Any, Optional

from github import Github, Auth
from github.GithubException import GithubException

from app.agents.components.base_agent import BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__, "ResolverAgent")


class ResolverAgent(BaseAgent):
    """
    Handles resolution of pipeline issues by pushing optimised YAML 
    to GitHub and creating a pull request.
    """

    def __init__(self, gh_token: Optional[str] = None):
        super().__init__(agent_name="create_pr")
        
        self.gh_token = gh_token or os.getenv("GITHUB_TOKEN")
        if not self.gh_token:
            logger.error("GITHUB_TOKEN is required for ResolverAgent", correlation_id="INIT")
            raise ValueError("GITHUB_TOKEN is required for ResolverAgent")

        auth = Auth.Token(self.gh_token)
        self.gh = Github(auth=auth)
        logger.debug("Initialised ResolverAgent with provided GitHub token", correlation_id="INIT")

    def run(
        self,
        repo_url: str,
        optimised_yaml: str,
        file_path: str,
        base_branch: str = "main",
        correlation_id: Optional[str] = None,
        pr_create: bool = True,
        analysis_result: Optional[Dict[str, Any]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Push optimised YAML to repo and optionally create a pull request.

        Returns:
            URL of created PR, or None if pr_create=False
        """
        if not file_path:
            raise ValueError("file_path is required and cannot be empty")
        
        pr_branch = f"optimise-pipeline-{correlation_id}" if correlation_id else "optimise-pipeline"
        
        repo_name = repo_url.split("github.com/")[-1].rstrip("/")
        repo = self.gh.get_repo(repo_name)

        base = repo.get_branch(base_branch)
        logger.debug("Base branch: %s (SHA: %s)" % (base_branch, base.commit.sha[:7]), correlation_id=correlation_id)

        try:
            repo.create_git_ref(ref=f"refs/heads/{pr_branch}", sha=base.commit.sha)
            logger.debug("Created new branch: %s" % pr_branch, correlation_id=correlation_id)
        except GithubException as e:
            if e.status == 422:
                logger.warning("Branch %s already exists" % pr_branch, correlation_id=correlation_id)
            else:
                logger.warning("Branch creation issue: %s" % e, correlation_id=correlation_id)

        file_exists = False
        file_sha = None
        try:
            existing_file = repo.get_contents(file_path, ref=pr_branch)
            file_sha = existing_file.sha
            file_exists = True
            logger.debug("File exists on branch, will update: %s" % file_path, correlation_id=correlation_id)
        except GithubException as e:
            if e.status == 404:
                logger.warning("File does not exist on branch: %s" % file_path, correlation_id=correlation_id)
            else:
                logger.warning("Error checking file existence: %s" % e, correlation_id=correlation_id)

        commit_message = f"Optimise CI/CD pipeline: {file_path}"
        if correlation_id:
            commit_message += f" [{correlation_id}]"
        
        if file_exists and file_sha:
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=optimised_yaml,
                sha=file_sha,
                branch=pr_branch,
            )
            logger.debug("File updated successfully: %s" % file_path, correlation_id=correlation_id)
        else:
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=optimised_yaml,
                branch=pr_branch,
            )
            logger.debug("File created successfully: %s" % file_path, correlation_id=correlation_id)

        if pr_create:
            open_prs = repo.get_pulls(
                state="open",
                head=f"{repo.owner.login}:{pr_branch}",
                base=base_branch
            )

            if open_prs.totalCount > 0:
                pr_url = open_prs[0].html_url
                logger.warning("PR already exists: %s" % pr_url, correlation_id=correlation_id)
                return pr_url

            pr_body = self._build_pr_body(file_path, correlation_id, analysis_result, risk_assessment)

            pr_title = f"Optimise CI/CD Pipeline: {file_path}"
            if correlation_id:
                pr_title += f" [{correlation_id}]"

            pr = repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=pr_branch,
                base=base_branch
            )

            pr_url = pr.html_url
            return pr_url

        return None

    def _build_pr_body(
        self,
        file_path: str,
        correlation_id: Optional[str] = None,
        analysis_result: Optional[Dict[str, Any]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build PR description with available information"""
        
        body_parts = [
            f"This PR applies automated optimisations to `{file_path}` to improve CI/CD pipeline efficiency.\n"
        ]

        if correlation_id:
            body_parts.append(f"\n**Correlation ID**: `{correlation_id}`\n")

        if analysis_result:
            issues = analysis_result.get("issues_detected", [])
            fixes = analysis_result.get("suggested_fixes", [])
            improvement = analysis_result.get("expected_improvement", "")

            if issues:
                body_parts.append("\n## Issues Detected\n")
                for i, issue in enumerate(issues, 1):
                    body_parts.append(f"{i}. {issue}\n")

            if fixes:
                body_parts.append("\n## Changes Applied\n")
                for i, fix in enumerate(fixes, 1):
                    body_parts.append(f"{i}. {fix}\n")

            if improvement:
                body_parts.append(f"\n## Expected Improvement\n{improvement}\n")
        else:
            body_parts.append(
                "\n## Changes Applied\n"
                "- Optimised pipeline configuration\n"
                "- Improved resource utilisation\n"
            )

        if risk_assessment:
            body_parts.append("\n## Risk Assessment\n")
            
            risk_score = risk_assessment.get("risk_score", 0)
            severity = risk_assessment.get("severity", "unknown")
            safe_merge = risk_assessment.get("safe_to_auto_merge", True)
            manual_approval = risk_assessment.get("requires_manual_approval", False)
            breaking_changes = risk_assessment.get("breaking_changes", [])
            affected = risk_assessment.get("affected_components", [])
            rollback = risk_assessment.get("rollback_plan", "")

            body_parts.append(f"- **Risk Score**: {risk_score}/100\n")
            body_parts.append(f"- **Severity**: {severity}\n")
            body_parts.append(f"- **Safe to Auto-Merge**: {'Yes' if safe_merge else 'No'}\n")
            body_parts.append(f"- **Manual Approval Required**: {'Yes' if manual_approval else 'No'}\n")

            if breaking_changes:
                body_parts.append(f"\n### Breaking Changes ({len(breaking_changes)})\n")
                for i, change in enumerate(breaking_changes, 1):
                    body_parts.append(f"{i}. {change}\n")

            if affected:
                body_parts.append(f"\n### Affected Components\n")
                body_parts.append(", ".join(affected) + "\n")

            if rollback:
                body_parts.append(f"\n### Rollback Plan\n{rollback}\n")

        body_parts.append(
            "\n---\n"
            "*This PR was automatically generated by the Pipeline Optimiser Agent.*"
        )

        return "".join(body_parts)

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute resolver within workflow"""
        correlation_id = state.get("correlation_id")
            
        if not state.get("pr_create"):
            logger.info("PR creation not requested by the user, hence skipping", correlation_id=correlation_id)
            return state

        if not state.get("optimised_yaml"):
            logger.warning("No optimised YAML available, skipping PR creation", correlation_id=correlation_id)
            return state

        pipeline_path = state.get("pipeline_path")
        if not pipeline_path:
            logger.error("pipeline_path is missing from state", correlation_id=correlation_id)
            state["error"] = "pipeline_path is required for PR creation"
            return state

        try:
            pr_url = self.run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                file_path=pipeline_path,
                base_branch=state["branch"],
                correlation_id=correlation_id,
                pr_create=True,
                analysis_result=state.get("analysis_result"),
                risk_assessment=state.get("risk_assessment")
            )

            if pr_url:
                state["pr_url"] = pr_url
            logger.info("PR created: %s" % pr_url, correlation_id=correlation_id)

            from app.db import db
            db.insert_pr(
                run_id=state["run_id"],
                branch_name=f"optimise-pipeline-{correlation_id}" if correlation_id else "optimise-pipeline",
                pr_url=state["pr_url"]
            )

        except Exception as e:
            logger.exception("PR creation failed: %s" % e, correlation_id=correlation_id)
            state["error"] = f"PR creation failed: {str(e)}"

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """No artifact to save for resolver"""
        return None