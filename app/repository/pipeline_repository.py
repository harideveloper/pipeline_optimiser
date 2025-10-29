"""
Pipeline Repository - Data access layer for pipeline optimisation
Handles all database operations related to pipeline runs
"""

from typing import Optional, Dict, Any, List

from app.repository import db
from app.utils.logger import get_logger
from app.exceptions import DatabaseError

logger = get_logger(__name__, "PipelineRepository")


class PipelineRepository:
    """ 
    Using repository pattern to encapsulate database operations
    """
    
    def __init__(self):
        """Initialise repository with database connection."""
        self.db = db
        logger.debug("Initialized PipelineRepository", correlation_id="INIT")

    def start_run(
        self,
        repo_url: str,
        pipeline_path: str,
        branch: str = "main",
        commit_sha: Optional[str] = None,
        trigger_source: str = "API",
        correlation_id: Optional[str] = None,
        workflow_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> int:
        """
        Creates repository record if needed and initializes run.
        
        Args:
            repo_url: GitHub repository URL
            pipeline_path: Path to pipeline file
            branch: Git branch
            commit_sha: Optional commit SHA
            trigger_source: How run was triggered
            correlation_id: Request correlation ID
            workflow_type: CI/CD/HYBRID
            risk_level: LOW/MEDIUM/HIGH
            
        Returns:
            run_id: ID of the created run
        """
        logger.debug(f"Starting optimisation run for repo: {repo_url}", correlation_id=correlation_id)
        
        try:
            repo_id = self.db.get_or_create_repo(repo_url=repo_url, default_branch=branch)
            
            run_id = self.db.create_run(
                repo_id=repo_id,
                pipeline_path=pipeline_path,
                branch=branch,
                commit_sha=commit_sha,
                trigger_source=trigger_source,
                correlation_id=correlation_id,
                workflow_type=workflow_type,
                risk_level=risk_level
            )
            
            logger.debug(f"Run started: run_id={run_id}, repo_id={repo_id}", correlation_id=correlation_id)
            return run_id
            
        except DatabaseError as e:
            logger.error(f"Failed to start run: {e}", correlation_id=correlation_id)
            raise
    
    def complete_run(
        self,
        run_id: int,
        duration_seconds: Optional[float] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Mark run as completed successfully."""
        try:
            self.db.update_run_status(
                run_id=run_id,
                status="completed",
                duration_seconds=duration_seconds
            )
            logger.info(f"Run completed: run_id={run_id}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.error(f"Failed to complete run: {e}", correlation_id=correlation_id)
            raise

    
    def update_run_metadata(
        self,
        run_id: int,
        workflow_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Update run metadata after classification."""
        try:
            self.db.update_run_metadata(
                run_id=run_id,
                workflow_type=workflow_type,
                risk_level=risk_level
            )
            logger.debug(f"Run metadata updated: run_id={run_id}, type={workflow_type}, risk={risk_level}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.error(f"Failed to update run metadata: {e}", correlation_id=correlation_id)
            raise

    def fail_run(
        self,
        run_id: int,
        error: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Mark run as failed."""
        try:
            self.db.update_run_status(run_id=run_id, status="failed")
            logger.error(f"Run failed: run_id={run_id}, error={error}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.error(f"Failed to mark run as failed: {e}", correlation_id=correlation_id)
            raise

    def save_artifact(
        self,
        run_id: int,
        stage: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Save workflow artifact."""
        try:
            self.db.insert_artifact(
                run_id=run_id,
                stage=stage,
                content=content,
                metadata=metadata or {}
            )
            logger.debug(f"Artifact saved: run_id={run_id}, stage={stage}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.warning(f"Failed to save artifact: {e}", correlation_id=correlation_id)
  
    def save_issues(
        self,
        run_id: int,
        issues: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> None:
        """Save detected issues."""
        try:
            for issue in issues:
                self.db.insert_issue(
                    run_id=run_id,
                    type=issue.get("type", "generic"),
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "medium"),
                    location=issue.get("location", "unknown"),
                    suggested_fix=issue.get("suggested_fix", "")
                )
            logger.debug(f"Saved {len(issues)} issues for run_id={run_id}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.warning(f"Failed to save issues: {e}", correlation_id=correlation_id)
    
    def save_review(
        self,
        run_id: int,
        review_type: str,
        review_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save review (critic/risk/security).
        
        Args:
            run_id: Run identifier
            review_type: 'critic', 'risk', or 'security'
            review_data: Full review data
            correlation_id: Request correlation ID
        """
        try:
            self.db.insert_review(
                run_id=run_id,
                review_type=review_type,
                fix_confidence=review_data.get("fix_confidence"),
                merge_confidence=review_data.get("merge_confidence"),
                quality_score=review_data.get("quality_score"),
                risk_score=review_data.get("risk_score"),
                overall_risk=review_data.get("overall_risk"),
                data=review_data
            )
            logger.debug(f"Review saved: run_id={run_id}, type={review_type}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.warning(f"Failed to save review: {e}", correlation_id=correlation_id)
    
    def save_decision(
        self,
        run_id: int,
        tool_name: str,
        action: str,
        reasoning: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save decision agent choice.
        
        Args:
            run_id: Run identifier
            tool_name: Name of tool
            action: 'run' or 'skip'
            reasoning: Why this decision was made
            correlation_id: Request correlation ID
        """
        try:
            self.db.insert_decision(
                run_id=run_id,
                tool_name=tool_name,
                action=action,
                reasoning=reasoning
            )
            logger.debug(f"Decision saved: run_id={run_id}, tool={tool_name}, action={action}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.warning(f"Failed to save decision: {e}", correlation_id=correlation_id)
    
    def save_pr(
        self,
        run_id: int,
        branch_name: str,
        pr_url: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Save PR information."""
        try:
            self.db.insert_pr(
                run_id=run_id,
                branch_name=branch_name,
                pr_url=pr_url
            )
            logger.info(f"PR saved: run_id={run_id}, url={pr_url}", correlation_id=correlation_id)
        except DatabaseError as e:
            logger.warning(f"Failed to save PR info: {e}", correlation_id=correlation_id)