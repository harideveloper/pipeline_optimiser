"""
Pipeline Repository - Data access layer for pipeline optimisation
Handles all database operations related to pipeline runs
"""

from typing import Optional, Dict, Any

from app.repository import db
from app.utils.logger import get_logger
from app.exceptions import DatabaseError

logger = get_logger(__name__, "PipelineRepository")


class PipelineRepository:
    """ 
        Using repository pattern, similar to java's Data Accessor patterns to encapsulate database operations
        Encapsulates all database operations related to pipeline optimisations:
        - Repository tracking
        - Run lifecycle
        - Artifact storage
        - Issue tracking
        - PR metadata
        
        Benefits:
        - Single place for all DB logic
        - Easy to test (mock this instead of db module)
        - Easy to switch databases
        - Clear transaction boundaries
    """
    
    def __init__(self):
        """Initialise repository with database connection."""
        self.db = db
        logger.debug("Initialized PipelineRepository", correlation_id="INIT")

    # start run faiure
    def start_run(
        self,
        repo_url: str,
        branch: str = "main",
        commit_sha: Optional[str] = None,
        trigger_source: str = "API",
        correlation_id: Optional[str] = None
    ) -> int:
        """
        Creates repository record if needed and initializes run.
        
        Args:
            repo_url: GitHub repository URL
            branch: Git branch
            commit_sha: Optional commit SHA
            trigger_source: How run was triggered (API/Webhook/Schedule)
            correlation_id: Request correlation ID
            
        Returns:
            run_id: ID of the created run
            
        Raises:
            DatabaseError: If database operation fails
        """
        logger.debug(
            f"Starting optimisation run for repo: {repo_url}",
            correlation_id=correlation_id
        )
        
        try:
            # Get or create repository
            repo_id = self.db.get_or_create_repo(
                repo_url=repo_url,
                default_branch=branch
            )
            
            # Create run
            run_id = self.db.create_run(
                repo_id=repo_id,
                commit_sha=commit_sha,
                trigger_source=trigger_source
            )
            
            logger.debug(
                f"Run started: run_id={run_id}, repo_id={repo_id}",
                correlation_id=correlation_id
            )
            
            return run_id
            
        except DatabaseError as e:
            logger.error(f"Failed to start run: {e}", correlation_id=correlation_id)
            raise
    
     # mark run completion
    def complete_run(
        self,
        run_id: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Mark run as completed successfully.
        
        Args:
            run_id: Run identifier
            correlation_id: Request correlation ID
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.db.update_run_status(run_id=run_id, status="completed")
            
            logger.info(
                f"Run completed: run_id={run_id}",
                correlation_id=correlation_id
            )
            
        except DatabaseError as e:
            logger.error(f"Failed to complete run: {e}", correlation_id=correlation_id)
            raise

    # Update run failure
    def fail_run(
        self,
        run_id: int,
        error: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Mark run as failed.
        Args:
            run_id: Run identifier
            error: Error message
            correlation_id: Request correlation ID
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.db.update_run_status(run_id=run_id, status="failed")
            
            logger.error(
                f"Run failed: run_id={run_id}, error={error}",
                correlation_id=correlation_id
            )
            
        except DatabaseError as e:
            logger.error(f"Failed to mark run as failed: {e}", correlation_id=correlation_id)
            raise
    

    # Save Artifacts    
    def save_artifact(
        self,
        run_id: int,
        stage: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save workflow artifact.
        
        Args:
            run_id: Run identifier
            stage: Stage name (ingest/analyze/fix/etc)
            content: Artifact content
            metadata: Optional metadata
            correlation_id: Request correlation ID
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.db.insert_artifact(
                run_id=run_id,
                stage=stage,
                content=content,
                metadata=metadata or {}
            )
            
            logger.debug(
                f"Artifact saved: run_id={run_id}, stage={stage}",
                correlation_id=correlation_id
            )
            
        except DatabaseError as e:
            logger.warning(
                f"Failed to save artifact: {e}",
                correlation_id=correlation_id
            )
  
    # Save Issues for future issue     
    def save_issues(
        self,
        run_id: int,
        issues: list[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save detected issues.
        Args:
            run_id: Run identifier
            issues: List of issue dictionaries
            correlation_id: Request correlation ID
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            for issue in issues:
                self.db.insert_issue(
                    run_id=run_id,
                    type=issue.get("type", "generic"),
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "medium"),
                    suggested_fix=issue.get("suggested_fix", "")
                )
            
            logger.debug(
                f"Saved {len(issues)} issues for run_id={run_id}",
                correlation_id=correlation_id
            )
            
        except DatabaseError as e:
            logger.warning(
                f"Failed to save issues: {e}",
                correlation_id=correlation_id
            )
    
    # Save PR Information
    def save_pr(
        self,
        run_id: int,
        branch_name: str,
        pr_url: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Save PR information.
        Args:
            run_id: Run identifier
            branch_name: Git branch name
            pr_url: Pull request URL
            correlation_id: Request correlation ID
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.db.insert_pr(
                run_id=run_id,
                branch_name=branch_name,
                pr_url=pr_url
            )
            
            logger.info(
                f"PR saved: run_id={run_id}, url={pr_url}",
                correlation_id=correlation_id
            )
            
        except DatabaseError as e:
            logger.warning(
                f"Failed to save PR info: {e}",
                correlation_id=correlation_id
            )