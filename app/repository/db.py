"""
db.py - Database helper module for Pipeline Optimiser
Handles Postgres interactions for repositories, runs, artifacts, issues, and PRs.
"""

import os
import logging
import psycopg2
import psycopg2.extras
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# -------------------------
# DATABASE CONNECTION
# -------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "pipeline_db")
DB_USER = os.getenv("DB_USER", "pipeline_user")
DB_PASS = os.getenv("DB_PASS", "pipeline_pass")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# -------------------------
# REPOSITORIES
# -------------------------
def get_or_create_repo(repo_url: str, default_branch: str = "main") -> int:
    """
    Get repository ID if exists, otherwise insert and return ID.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM repositories WHERE repo_url = %s",
                    (repo_url,)
                )
                row = cur.fetchone()
                if row:
                    return row["id"]

                # Insert new repo
                cur.execute(
                    "INSERT INTO repositories (repo_url, default_branch) VALUES (%s, %s) RETURNING id",
                    (repo_url, default_branch)
                )
                repo_id = cur.fetchone()["id"]
                logger.debug("Created new repository record: %s (id=%d)", repo_url, repo_id)
                return repo_id
    finally:
        conn.close()


# -------------------------
# RUNS
# -------------------------
def create_run(repo_id: int, commit_sha: Optional[str] = None, trigger_source: str = "API") -> int:
    conn = get_conn()
    try:
        with conn:
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
                logger.debug("Created new run: %d for repo_id %d", run_id, repo_id)
                return run_id
    finally:
        conn.close()


def update_run_status(run_id: int, status: str, end_time: Optional[str] = None):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs
                    SET status = %s, end_time = COALESCE(%s, NOW())
                    WHERE id = %s
                    """,
                    (status, end_time, run_id)
                )
                logger.debug("Updated run %d status to %s", run_id, status)
    finally:
        conn.close()


# -------------------------
# ARTIFACTS
# -------------------------
def insert_artifact(run_id: int, stage: str, content: str, metadata: Optional[Dict[str, Any]] = None):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO artifacts (run_id, stage, content, metadata)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (run_id, stage, content, psycopg2.extras.Json(metadata or {}))
                )
                logger.debug("Inserted artifact for run_id %d, stage %s", run_id, stage)
    finally:
        conn.close()


# -------------------------
# ISSUES
# -------------------------
def insert_issue(run_id: int, type: str, description: str, severity: str = "medium", suggested_fix: Optional[str] = None):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO issues (run_id, type, description, severity, suggested_fix)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, type, description, severity, suggested_fix)
                )
                logger.debug("Inserted issue for run_id %d, type %s", run_id, type)
    finally:
        conn.close()


# -------------------------
# PRs
# -------------------------
def insert_pr(run_id: int, branch_name: str, pr_url: str, status: str = "created", merged: bool = False):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO prs (run_id, branch_name, pr_url, status, merged)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, branch_name, pr_url, status, merged)
                )
                logger.debug("Inserted PR record for run_id %d, branch %s", run_id, branch_name)
    finally:
        conn.close()
