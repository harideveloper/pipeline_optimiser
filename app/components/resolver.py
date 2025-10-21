"""
Resolver Agent - Resolves pipeline issues by creating PRs with optimised YAML.
"""

from typing import Dict, Any, Optional

from github import Github, Auth
from github.GithubException import GithubException

from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.config import config
from app.exceptions import ResolverError

logger = get_logger(__name__, "Resolver")


class Resolver(BaseService):
    """
    Handles resolution of pipeline issues by pushing optimised YAML 
    to GitHub and creating a pull request.
    
    Integrates with GitHub API to:
    - Create feature branches
    - Commit optimised YAML
    - Create pull requests with detailed descriptions
    """

    def __init__(self, gh_token: Optional[str] = None):
        """
        Initialize Resolver with GitHub authentication.
        
        Args:
            gh_token: GitHub personal access token (defaults to config.GITHUB_TOKEN)
            
        Raises:
            ResolverError: If GitHub token is not available
        """
        super().__init__(agent_name="resolve")
        
        self.gh_token = gh_token or config.GITHUB_TOKEN
        if not self.gh_token:
            logger.error("GITHUB_TOKEN is required for Resolver", correlation_id="INIT")
            raise ResolverError("GITHUB_TOKEN is required for Resolver")

        auth = Auth.Token(self.gh_token)
        self.gh = Github(auth=auth)
        logger.debug("Initialised Resolver with GitHub token", correlation_id="INIT")

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
        
        Args:
            repo_url: GitHub repository URL
            optimised_yaml: Optimised YAML content to commit
            file_path: Path to file in repository
            base_branch: Base branch to create PR against (default: main)
            correlation_id: Request correlation ID
            pr_create: Whether to create a pull request (default: True)
            analysis_result: Optional analysis results for PR description
            risk_assessment: Optional risk assessment for PR description
            
        Returns:
            URL of created PR, or None if pr_create=False
            
        Raises:
            ResolverError: If file_path is invalid or GitHub operations fail
        """
        # Validate inputs
        if not file_path or not file_path.strip():
            raise ResolverError("file_path is required and cannot be empty")
        
        if not optimised_yaml or not optimised_yaml.strip():
            raise ResolverError("optimised_yaml is required and cannot be empty")
        
        # Create branch name
        pr_branch = f"optimise-pipeline-{correlation_id}" if correlation_id else "optimise-pipeline"
        
        # Extract repository name from URL
        repo_name = self._extract_repo_name(repo_url)
        
        try:
            # Get repository
            repo = self.gh.get_repo(repo_name)
            
            # Create branch
            self._create_branch(repo, pr_branch, base_branch, correlation_id)
            
            # Commit changes
            self._commit_changes(repo, file_path, optimised_yaml, pr_branch, correlation_id)
            
            # Create PR if requested
            if pr_create:
                pr_url = self._create_pull_request(
                    repo=repo,
                    pr_branch=pr_branch,
                    base_branch=base_branch,
                    file_path=file_path,
                    correlation_id=correlation_id,
                    analysis_result=analysis_result,
                    risk_assessment=risk_assessment
                )
                return pr_url
            
            logger.info("Changes committed to branch without PR", correlation_id=correlation_id)
            return None
            
        except GithubException as e:
            logger.error(f"GitHub API error: {e}", correlation_id=correlation_id)
            raise ResolverError(f"GitHub operation failed: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error: {e}", correlation_id=correlation_id)
            raise ResolverError(f"Unexpected error: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute resolver within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with pr_url (if created)
        """
        correlation_id = state.get("correlation_id")

        # Check if PR creation was requested
        if not state.get("pr_create"):
            logger.info("PR creation not requested, skipping", correlation_id=correlation_id)
            return state

        # Check if optimised YAML is available
        if not state.get("optimised_yaml"):
            logger.warning("No optimised YAML available, skipping PR creation", correlation_id=correlation_id)
            return state

        # Validate pipeline path
        pipeline_path = state.get("pipeline_path")
        if not pipeline_path:
            logger.error("pipeline_path is missing from state", correlation_id=correlation_id)
            state["error"] = "pipeline_path is required for PR creation"
            return state

        try:
            # Create PR
            pr_url = self.run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                file_path=pipeline_path,
                base_branch=state.get("branch", "main"),
                correlation_id=correlation_id,
                pr_create=True,
                analysis_result=state.get("analysis_result"),
                risk_assessment=state.get("risk_assessment")
            )

            if pr_url:
                state["pr_url"] = pr_url
                logger.info(f"PR created: {pr_url}", correlation_id=correlation_id)
                
                # Save PR to database
                branch_name = f"optimise-pipeline-{correlation_id}" if correlation_id else "optimise-pipeline"
                try:
                    self.repository.save_pr(
                        run_id=state["run_id"],
                        branch_name=branch_name,
                        pr_url=pr_url,
                        correlation_id=correlation_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist PR info: {e}", correlation_id=correlation_id)

        except ResolverError as e:
            logger.error(f"PR creation failed: {e}", correlation_id=correlation_id)
            state["error"] = f"PR creation failed: {e}"
        except Exception as e:
            logger.exception(f"Unexpected error during PR creation: {e}", correlation_id=correlation_id)
            state["error"] = f"Unexpected error during PR creation: {e}"

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Resolver doesn't produce artifacts.
        
        Returns:
            None
        """
        return None

    def _extract_repo_name(self, repo_url: str) -> str:
        """
        Extract repository name from GitHub URL.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Repository name in format 'owner/repo'
            
        Raises:
            ResolverError: If URL format is invalid
        """
        try:
            # Handle both HTTPS and SSH URLs
            if "github.com/" in repo_url:
                repo_name = repo_url.split("github.com/")[-1].rstrip("/").rstrip(".git")
                return repo_name
            else:
                raise ResolverError(f"Invalid GitHub URL format: {repo_url}")
        except Exception as e:
            raise ResolverError(f"Failed to extract repo name from URL: {e}") from e

    def _create_branch(
        self,
        repo: Any,
        pr_branch: str,
        base_branch: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Create a new branch for the PR.
        
        Args:
            repo: GitHub repository object
            pr_branch: Name of branch to create
            base_branch: Base branch to branch from
            correlation_id: Request correlation ID
        """
        try:
            base = repo.get_branch(base_branch)
            logger.debug(
                f"Base branch: {base_branch} (SHA: {base.commit.sha[:7]})",
                correlation_id=correlation_id
            )
            
            # Create new branch
            repo.create_git_ref(ref=f"refs/heads/{pr_branch}", sha=base.commit.sha)
            logger.debug(f"Created new branch: {pr_branch}", correlation_id=correlation_id)
            
        except GithubException as e:
            if e.status == 422:
                logger.warning(f"Branch {pr_branch} already exists", correlation_id=correlation_id)
            else:
                logger.warning(f"Branch creation issue: {e}", correlation_id=correlation_id)
                raise

    def _commit_changes(
        self,
        repo: Any,
        file_path: str,
        optimised_yaml: str,
        pr_branch: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Commit optimised YAML to the branch.
        
        Args:
            repo: GitHub repository object
            file_path: Path to file in repository
            optimised_yaml: Optimised YAML content
            pr_branch: Branch to commit to
            correlation_id: Request correlation ID
        """
        # Check if file exists
        file_exists = False
        file_sha = None
        
        try:
            existing_file = repo.get_contents(file_path, ref=pr_branch)
            file_sha = existing_file.sha
            file_exists = True
            logger.debug(f"File exists, will update: {file_path}", correlation_id=correlation_id)
        except GithubException as e:
            if e.status == 404:
                logger.debug(f"File does not exist, will create: {file_path}", correlation_id=correlation_id)
            else:
                logger.warning(f"Error checking file existence: {e}", correlation_id=correlation_id)

        # Build commit message
        commit_message = f"Optimise CI/CD pipeline: {file_path}"
        if correlation_id:
            commit_message += f" [{correlation_id}]"
        
        # Update or create file
        if file_exists and file_sha:
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=optimised_yaml,
                sha=file_sha,
                branch=pr_branch,
            )
            logger.debug(f"File updated successfully: {file_path}", correlation_id=correlation_id)
        else:
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=optimised_yaml,
                branch=pr_branch,
            )
            logger.debug(f"File created successfully: {file_path}", correlation_id=correlation_id)

    def _create_pull_request(
        self,
        repo: Any,
        pr_branch: str,
        base_branch: str,
        file_path: str,
        correlation_id: Optional[str] = None,
        analysis_result: Optional[Dict[str, Any]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a pull request.
        
        Args:
            repo: GitHub repository object
            pr_branch: Head branch for PR
            base_branch: Base branch for PR
            file_path: Path to file being changed
            correlation_id: Request correlation ID
            analysis_result: Analysis results for PR description
            risk_assessment: Risk assessment for PR description
            
        Returns:
            URL of created PR
        """
        # Check for existing PR
        open_prs = repo.get_pulls(
            state="open",
            head=f"{repo.owner.login}:{pr_branch}",
            base=base_branch
        )

        if open_prs.totalCount > 0:
            pr_url = open_prs[0].html_url
            logger.warning(f"PR already exists: {pr_url}", correlation_id=correlation_id)
            return pr_url

        # Build PR content
        pr_body = self._build_pr_body(file_path, correlation_id, analysis_result, risk_assessment)
        pr_title = f"Optimise CI/CD Pipeline: {file_path}"
        if correlation_id:
            pr_title += f" [{correlation_id}]"

        # Create PR
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=pr_branch,
            base=base_branch
        )

        logger.info(f"PR created successfully: {pr.html_url}", correlation_id=correlation_id)
        return pr.html_url

    def _build_pr_body(
        self,
        file_path: str,
        correlation_id: Optional[str] = None,
        analysis_result: Optional[Dict[str, Any]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build PR description with available information.
        
        Args:
            file_path: Path to file being changed
            correlation_id: Request correlation ID
            analysis_result: Analysis results
            risk_assessment: Risk assessment
            
        Returns:
            Formatted PR description
        """
        body_parts = [
            f"This PR applies automated optimisations to `{file_path}` to improve CI/CD pipeline efficiency.\n"
        ]

        if correlation_id:
            body_parts.append(f"\n**Correlation ID**: `{correlation_id}`\n")

        # Add analysis results
        if analysis_result:
            self._add_analysis_section(body_parts, analysis_result)
        else:
            body_parts.append(
                "\n## Changes Applied\n"
                "- Optimised pipeline configuration\n"
                "- Improved resource utilisation\n"
            )

        # Add risk assessment
        if risk_assessment:
            self._add_risk_assessment_section(body_parts, risk_assessment)

        # Footer
        body_parts.append(
            "\n---\n"
            "*This PR was automatically generated by the Pipeline Optimiser Agent.*"
        )

        return "".join(body_parts)

    def _add_analysis_section(self, body_parts: list, analysis_result: Dict[str, Any]) -> None:
        """Add analysis results to PR body."""
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

    def _add_risk_assessment_section(self, body_parts: list, risk_assessment: Dict[str, Any]) -> None:
        """Add risk assessment to PR body."""
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
            body_parts.append("\n### Affected Components\n")
            body_parts.append(", ".join(affected) + "\n")

        if rollback:
            body_parts.append(f"\n### Rollback Plan\n{rollback}\n")