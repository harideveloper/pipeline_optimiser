"""
Database helper module for Pipeline Optimiser
Handles Postgres interactions for repositories, runs, artifacts, issues, reviews, decisions, and PRs.
"""

import psycopg2.extras
from typing import Optional, Dict, Any

from app.repository.db_pool import db_pool
from app.utils.logger import get_logger
from app.exceptions import DatabaseError

logger = get_logger(__name__, "PipelineDB")


# REPOSITORIES
def get_or_create_repo(repo_url: str, default_branch: str = "main") -> int:
    """Get repository ID if exists, otherwise insert and return ID."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM repositories WHERE repo_url = %s", (repo_url,))
                row = cur.fetchone()
                if row:
                    return row["id"]

                cur.execute(
                    "INSERT INTO repositories (repo_url, default_branch) VALUES (%s, %s) RETURNING id",
                    (repo_url, default_branch)
                )
                repo_id = cur.fetchone()["id"]
                conn.commit()
                
                logger.debug(f"Created new repository record: {repo_url} (id={repo_id})", correlation_id="DB")
                return repo_id
                
    except Exception as e:
        logger.error(f"Failed to get/create repository: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to get/create repository: {e}") from e


# RUNS
def create_run(
    repo_id: int,
    pipeline_path: str,
    branch: str = "main",
    commit_sha: Optional[str] = None,
    trigger_source: str = "API",
    correlation_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    risk_level: Optional[str] = None
) -> int:
    """Create a new pipeline run."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO runs (
                        repo_id, pipeline_path, branch, commit_sha, 
                        trigger_source, correlation_id, workflow_type, risk_level
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (repo_id, pipeline_path, branch, commit_sha, trigger_source, correlation_id, workflow_type, risk_level)
                )
                run_id = cur.fetchone()["id"]
                conn.commit()
                
                logger.debug(f"Created new optimisation run: {run_id} for repo_id {repo_id}", correlation_id="DB")
                return run_id
                
    except Exception as e:
        logger.error(f"Failed to create run: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to create run: {e}") from e


def update_run_status(
    run_id: int,
    status: str,
    duration_seconds: Optional[float] = None,
    end_time: Optional[str] = None
) -> None:
    """Update run status."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs
                    SET status = %s, duration_seconds = %s, end_time = COALESCE(%s, NOW())
                    WHERE id = %s
                    """,
                    (status, duration_seconds, end_time, run_id)
                )
                conn.commit()
                logger.debug(f"Updated run {run_id} status to {status}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to update run status: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to update run status: {e}") from e
    
def update_run_metadata(
        run_id: int,
        workflow_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> None:
        """Update run metadata (workflow_type and risk_level)."""
        try:
            with db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE runs
                        SET workflow_type = %s, risk_level = %s
                        WHERE id = %s
                        """,
                        (workflow_type, risk_level, run_id)
                    )
                    conn.commit()
                    logger.debug(f"Updated run {run_id} metadata: type={workflow_type}, risk={risk_level}", correlation_id="DB")
                    
        except Exception as e:
            logger.error(f"Failed to update run metadata: {e}", correlation_id="DB")
            raise DatabaseError(f"Failed to update run metadata: {e}") from e


# ARTIFACTS
def insert_artifact(
    run_id: int,
    stage: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Insert workflow artifact."""
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
                logger.debug(f"Inserted artifact for run_id {run_id}, stage {stage}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to insert artifact: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert artifact: {e}") from e


# ISSUES
def insert_issue(
    run_id: int,
    type: str,
    description: str,
    severity: str = "medium",
    location: str = "unknown",
    suggested_fix: Optional[str] = None
) -> None:
    """Insert detected issue."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO issues (run_id, type, description, severity, location, suggested_fix)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (run_id, type, description, severity, location, suggested_fix)
                )
                conn.commit()
                logger.debug(f"Inserted issue for run_id {run_id}, type {type}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to insert issue: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert issue: {e}") from e


# REVIEWS
def insert_review(
    run_id: int,
    review_type: str,
    fix_confidence: Optional[float] = None,
    merge_confidence: Optional[float] = None,
    quality_score: Optional[int] = None,
    risk_score: Optional[float] = None,
    overall_risk: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> None:
    """Insert review (critic/risk/security)."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reviews (
                        run_id, review_type, fix_confidence, merge_confidence,
                        quality_score, risk_score, overall_risk, data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (run_id, review_type, fix_confidence, merge_confidence, 
                     quality_score, risk_score, overall_risk, psycopg2.extras.Json(data or {}))
                )
                conn.commit()
                logger.debug(f"Inserted review for run_id {run_id}, type {review_type}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to insert review: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert review: {e}") from e


# DECISIONS
def insert_decision(
    run_id: int,
    tool_name: str,
    action: str,
    reasoning: str
) -> None:
    """Insert decision agent choice."""
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO decisions (run_id, tool_name, action, reasoning)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (run_id, tool_name, action, reasoning)
                )
                conn.commit()
                logger.debug(f"Inserted decision for run_id {run_id}, tool {tool_name}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to insert decision: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert decision: {e}") from e


# PRs
def insert_pr(
    run_id: int,
    branch_name: str,
    pr_url: str,
    status: str = "created",
    merged: bool = False
) -> None:
    """Insert PR metadata."""
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
                logger.debug(f"Inserted PR for run_id {run_id}, branch {branch_name}", correlation_id="DB")
                
    except Exception as e:
        logger.error(f"Failed to insert PR: {e}", correlation_id="DB")
        raise DatabaseError(f"Failed to insert PR: {e}") from e