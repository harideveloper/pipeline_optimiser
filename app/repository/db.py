"""
Database helper module for Pipeline Optimiser
Handles Postgres interactions for repositories, runs, artifacts, issues, and PRs.
"""

import psycopg2.extras
from typing import Optional, Dict, Any

from app.repository.db_pool import db_pool
from app.utils.logger import get_logger
from app.exceptions import DatabaseError

logger = get_logger(__name__, "PipelineDB")


# REPOSITORIES
def get_or_create_repo(repo_url: str, default_branch: str = "main") -> int:
    """
    Get repository ID if exists, otherwise insert and return ID.
    
    Args:
        repo_url: GitHub repository URL
        default_branch: Default branch name (default: main)
        
    Returns:
        Repository ID
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if repository exists
                cur.execute(
                    "SELECT id FROM repositories WHERE repo_url = %s",
                    (repo_url,)
                )
                row = cur.fetchone()
                if row:
                    return row["id"]

                # Insert new repository
                cur.execute(
                    "INSERT INTO repositories (repo_url, default_branch) VALUES (%s, %s) RETURNING id",
                    (repo_url, default_branch)
                )
                repo_id = cur.fetchone()["id"]
                conn.commit()
                
                logger.debug(
                    f"Created new repository record: {repo_url} (id={repo_id})",
                    correlation_id="DB"
                )
                return repo_id
                
    except Exception as e:
        logger.error(f"Failed to get/create repository: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to get/create repository: {e}") from e



# RUNS
def create_run(
    repo_id: int,
    commit_sha: Optional[str] = None,
    trigger_source: str = "API"
) -> int:
    """
    Create a new pipeline run.
    
    Args:
        repo_id: Repository ID
        commit_sha: Optional commit SHA
        trigger_source: How run was triggered (API/Webhook/Schedule)
        
    Returns:
        Run ID
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO runs (repo_id, commit_sha, trigger_source)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (repo_id, commit_sha, trigger_source)
                )
                run_id = cur.fetchone()["id"]
                conn.commit()
                
                logger.debug(
                    f"Created new optimisation run record : {run_id} for repo_id {repo_id}",
                    correlation_id="DB"
                )
                return run_id
                
    except Exception as e:
        logger.error(f"Failed to create run: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to create run: {e}") from e


def update_run_status(
    run_id: int,
    status: str,
    end_time: Optional[str] = None
) -> None:
    """
    Update run status.
    
    Args:
        run_id: Run ID
        status: New status (started/completed/failed)
        end_time: Optional end time (default: NOW())
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs
                    SET status = %s, end_time = COALESCE(%s, NOW())
                    WHERE id = %s
                    """,
                    (status, end_time, run_id)
                )
                conn.commit()
                
                logger.debug(
                    f"Updated optimisation run {run_id} status to {status}",
                    correlation_id="DB"
                )
                
    except Exception as e:
        logger.error(f"Failed to update run status: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to update run status: {e}") from e


# ARTIFACTS
def insert_artifact(
    run_id: int,
    stage: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Insert workflow artifact.
    
    Args:
        run_id: Run ID
        stage: Stage name (ingest/analyze/fix/etc)
        content: Artifact content
        metadata: Optional metadata dictionary
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO artifacts (run_id, stage, content, metadata)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (run_id, stage, content, psycopg2.extras.Json(metadata or {}))
                )
                conn.commit()
                
                logger.debug(
                    f"Inserted artifact for run_id {run_id}, stage {stage}",
                    correlation_id="DB"
                )
                
    except Exception as e:
        logger.error(f"Failed to insert artifact: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert artifact: {e}") from e


# ISSUES
def insert_issue(
    run_id: int,
    type: str,
    description: str,
    severity: str = "medium",
    suggested_fix: Optional[str] = None
) -> None:
    """
    Insert detected issue.
    
    Args:
        run_id: Run ID
        type: Issue type
        description: Issue description
        severity: Severity level (low/medium/high)
        suggested_fix: Optional suggested fix
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO issues (run_id, type, description, severity, suggested_fix)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, type, description, severity, suggested_fix)
                )
                conn.commit()
                
                logger.debug(
                    f"Inserted issue for run_id {run_id}, type {type}",
                    correlation_id="DB"
                )
                
    except Exception as e:
        logger.error(f"Failed to insert issue: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert issue: {e}") from e


# PRs
def insert_pr(
    run_id: int,
    branch_name: str,
    pr_url: str,
    status: str = "created",
    merged: bool = False
) -> None:
    """
    Insert PR metadata.
    
    Args:
        run_id: Run ID
        branch_name: Git branch name
        pr_url: Pull request URL
        status: PR status (created/merged/closed)
        merged: Whether PR is merged
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO prs (run_id, branch_name, pr_url, status, merged)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, branch_name, pr_url, status, merged)
                )
                conn.commit()
                
                logger.debug(
                    f"Inserted PR record for run_id {run_id}, branch {branch_name}",
                    correlation_id="DB"
                )
                
    except Exception as e:
        logger.error(f"Failed to insert PR: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert PR: {e}") from e