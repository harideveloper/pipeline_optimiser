"""
Enhanced Resolver Agent - Resolves pipeline issues by creating PRs with optimised YAML.
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
    """

    def __init__(self, gh_token: Optional[str] = None):
        """
        Initialise Resolver with GitHub authentication.
        
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
        risk_assessment: Optional[Dict[str, Any]] = None,
        critic_review: Optional[Dict[str, Any]] = None
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
            critic_review: Optional LLM review results with confidence scores
            
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
        
        # Create target branch name with correlation id suffix
        pr_branch = f"optimise-pipeline-{correlation_id}" if correlation_id else "optimise-pipeline"
        repo_name = self._extract_repo_name(repo_url)
        
        try:
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
                    risk_assessment=risk_assessment,
                    critic_review=critic_review
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
            pr_url = self.run(
                repo_url=state["repo_url"],
                optimised_yaml=state["optimised_yaml"],
                file_path=pipeline_path,
                base_branch=state.get("branch", "main"),
                correlation_id=correlation_id,
                pr_create=True,
                analysis_result=state.get("analysis_result"),
                risk_assessment=state.get("risk_assessment"),
                critic_review=state.get("critic_review")
            )

            if pr_url:
                state["pr_url"] = pr_url
                logger.info(f"PR created: {pr_url}", correlation_id=correlation_id)
                
                # Save PR info to database
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
            Repository name in format "owner/repo"
            
        Raises:
            ResolverError: If URL is invalid
        """

        url = repo_url.rstrip("/")
        
        if "github.com/" in url:
            parts = url.split("github.com/")[1].split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1].replace('.git', '')}"
        
        raise ResolverError(f"Invalid GitHub repository URL: {repo_url}")

    def _create_branch(
        self,
        repo: Any,
        pr_branch: str,
        base_branch: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Create a new branch from base branch.
        
        Args:
            repo: GitHub repository object
            pr_branch: Name of branch to create
            base_branch: Base branch to branch from
            correlation_id: Request correlation ID
        """
        # Get base branch SHA
        base_ref = repo.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha
        
        # Create target branch
        try:
            repo.create_git_ref(ref=f"refs/heads/{pr_branch}", sha=base_sha)
            logger.debug(f"Created branch: {pr_branch}", correlation_id=correlation_id)
        except GithubException as e:
            if e.status == 422:
                # Branch already exists
                logger.warning(f"Branch already exists: {pr_branch}", correlation_id=correlation_id)
            else:
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
        Commit changes to the branch.
        
        Args:
            repo: GitHub repository object
            file_path: Path to file to update/create
            optimised_yaml: Content to commit
            pr_branch: Branch to commit to
            correlation_id: Request correlation ID
        """
        # Check if file exists
        file_exists = False
        file_sha = None
        try:
            file_content = repo.get_contents(file_path, ref=pr_branch)
            file_exists = True
            file_sha = file_content.sha
        except GithubException:
            pass

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
        risk_assessment: Optional[Dict[str, Any]] = None,
        critic_review: Optional[Dict[str, Any]] = None
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
            critic_review: critic review results with confidence scores
            
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
        pr_body = self._build_pr_body(
            file_path,
            correlation_id,
            analysis_result,
            risk_assessment,
            critic_review 
        )
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
        risk_assessment: Optional[Dict[str, Any]] = None,
        critic_review: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build compact PR description with clear separation between optimiser and reviewer.
        """
        body_parts = []
        
        # Header
        body_parts.append(f"Automated optimisation for `{file_path}`")
        if correlation_id:
            body_parts.append(f" | Correlation ID: `{correlation_id}`")
        body_parts.append("\n\n")
        
        # optimiser Results Section
        body_parts.append("## Optimiser Summary\n\n")
        
        if analysis_result:
            self._add_analysis_section(body_parts, analysis_result)
        else:
            body_parts.append("optimised pipeline configuration\n")

        # Reviewer Results Section (if available)
        if critic_review:
            self._add_critic_review_section(body_parts, critic_review)

        # Risk assessment in compact format if present
        if risk_assessment:
            self._add_risk_assessment_section(body_parts, risk_assessment)

        # Footer
        body_parts.append(
            "\n---\n"
            "*Auto-generated by Pipeline optimiser*"
        )

        return "".join(body_parts)

    def _add_critic_review_section(self, body_parts: list, critic_review: Dict[str, Any]) -> None:
        """
        Add compact LLM review information to PR body.
        """
        body_parts.append("\n---\n\n## Critic Review\n\n")
        
        # Overall confidence scores in compact format
        fix_confidence = critic_review.get("fix_confidence", 0.0)
        merge_confidence = critic_review.get("merge_confidence", 0.0)
        quality_score = critic_review.get("quality_score", 0)
        
        # Determine status text
        status = self._get_status_text(merge_confidence)
        
        body_parts.append(
            f"**Confidence**: Fix {fix_confidence:.0%} | Merge {merge_confidence:.0%} | "
            f"Quality {quality_score}/10 | Status: {status}\n"
        )
        
        # Count issues
        issue_reviews = critic_review.get("issue_reviews", [])
        regressions = critic_review.get("regressions", [])
        unresolved = critic_review.get("unresolved_issues", [])
        recommendations = critic_review.get("recommendations", [])
        
        # Summary line
        summary_parts = []
        if issue_reviews:
            fixed = sum(1 for r in issue_reviews if r.get("properly_fixed", False))
            summary_parts.append(f"{fixed}/{len(issue_reviews)} issues resolved")
        if regressions:
            summary_parts.append(f"{len(regressions)} potential regressions")
        if unresolved:
            summary_parts.append(f"{len(unresolved)} unresolved")
        
        if summary_parts:
            body_parts.append(f"**Summary**: {' | '.join(summary_parts)}\n")
        
        # Compact per-issue review (only show if not all properly fixed)
        if issue_reviews:
            issues_to_show = [r for r in issue_reviews if not r.get("properly_fixed", True) or r.get("confidence", 1.0) < 0.8]
            if issues_to_show:
                body_parts.append("\n**Issue Review**:\n")
                for review in issues_to_show:
                    issue_id = review.get("issue_id", "?")
                    issue_confidence = review.get("confidence", 0.0)
                    fixed = review.get("properly_fixed", False)
                    status_text = "FIXED" if fixed else "PARTIAL"
                    body_parts.append(f"- Issue #{issue_id}: {status_text} ({issue_confidence:.0%} confidence)\n")
        
        # Regressions in compact format
        if regressions:
            body_parts.append("\n**Regressions Detected**:\n")
            for idx, regression in enumerate(regressions, 1):
                reg_desc = regression.get("description", "Unknown")
                reg_severity = regression.get("severity", "medium").upper()
                body_parts.append(f"{idx}. [{reg_severity}] {reg_desc}\n")
        
        # Unresolved issues in compact format
        if unresolved:
            body_parts.append("\n**Unresolved**:\n")
            for idx, issue in enumerate(unresolved, 1):
                issue_desc = issue.get("description", "Unknown")
                body_parts.append(f"{idx}. {issue_desc}\n")
        
        # Recommendations in compact format (max 3)
        if recommendations:
            body_parts.append("\n**Recommendations**:\n")
            for idx, rec in enumerate(recommendations[:3], 1):
                body_parts.append(f"{idx}. {rec}\n")
            if len(recommendations) > 3:
                body_parts.append(f"*...and {len(recommendations) - 3} more*\n")
        
        # Notes only if present and not too long
        notes = critic_review.get("notes", "")
        if notes and len(notes) < 200:
            body_parts.append(f"\n**Notes**: {notes}\n")

    def _get_status_text(self, merge_confidence: float) -> str:
        """Get compact status text based on confidence."""
        if merge_confidence >= 0.8:
            return "Ready to merge"
        elif merge_confidence >= 0.5:
            return "Review recommended"
        elif merge_confidence >= 0.25:
            return "Careful review required"
        else:
            return "Manual intervention needed"

    def _add_analysis_section(self, body_parts: list, analysis_result: Dict[str, Any]) -> None:
        """
        Add compact analysis results to PR body.
        """
        issues = analysis_result.get("issues_detected", [])
        fixes = analysis_result.get("suggested_fixes", [])
        expected = analysis_result.get("expected_improvement", "")

        # Issues in compact format
        if issues:
            body_parts.append("**Issues Detected**:\n")
            for i, issue in enumerate(issues, 1):
                if isinstance(issue, dict):
                    desc = issue.get("description", "No description")
                    sev = issue.get("severity", "medium").upper()
                    loc = issue.get("location", "unknown")
                    body_parts.append(f"{i}. [{sev}] {desc} (`{loc}`)\n")
                else:
                    body_parts.append(f"{i}. {issue}\n")
            body_parts.append("\n")

        # Fixes in compact format
        if fixes:
            body_parts.append("**Changes Applied**:\n")
            for i, fix in enumerate(fixes, 1):
                if isinstance(fix, dict):
                    fix_desc = fix.get("fix", "No description")
                    body_parts.append(f"{i}. {fix_desc}\n")
                else:
                    body_parts.append(f"{i}. {fix}\n")
            body_parts.append("\n")

        # Expected improvement
        if expected:
            body_parts.append(f"**Expected Impact**: {expected}\n")

    def _add_risk_assessment_section(self, body_parts: list, risk_assessment: Dict[str, Any]) -> None:
        """Add compact risk assessment to PR body."""
        body_parts.append("\n---\n\n## Risk Assessment\n\n")
        
        risk_score = risk_assessment.get("risk_score", 0)
        overall_risk = risk_assessment.get("overall_risk", "unknown").upper()
        safe_merge = risk_assessment.get("safe_to_auto_merge", True)
        manual_approval = risk_assessment.get("requires_manual_approval", False)
        breaking_changes = risk_assessment.get("breaking_changes", [])
        affected = risk_assessment.get("affected_components", [])

        # Scale risk_score from 0-10 to 0-100
        risk_score_scaled = int(risk_score * 10)
        
        # Single line summary
        merge_status = "Safe" if safe_merge else "Review required"
        approval_status = "Manual approval needed" if manual_approval else "Auto-merge allowed"
        
        body_parts.append(
            f"**Risk Score**: {risk_score_scaled}/100 ({overall_risk}) | "
            f"**Merge**: {merge_status} | "
            f"**Approval**: {approval_status}\n"
        )

        # Breaking changes (compact)
        if breaking_changes:
            body_parts.append(f"\n**Breaking Changes** ({len(breaking_changes)}): {', '.join(breaking_changes[:3])}")
            if len(breaking_changes) > 3:
                body_parts.append(f" *+{len(breaking_changes) - 3} more*")
            body_parts.append("\n")

        # Affected components (compact)
        if affected:
            body_parts.append(f"**Affected**: {', '.join(affected)}\n")