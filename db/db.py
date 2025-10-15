import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import json
import logging

logger = logging.getLogger(__name__)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "pipeline_user")
DB_PASS = os.getenv("DB_PASS", "pipeline_pass")
DB_NAME = os.getenv("DB_NAME", "pipeline_db")


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_run(repo_id: int, commit_sha: str, trigger_source: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO runs (repo_id, commit_sha, trigger_source, status) "
                "VALUES (%s, %s, %s, 'started') RETURNING id",
                (repo_id, commit_sha, trigger_source)
            )
            run_id = cur.fetchone()[0]
            logger.info(f"Inserted run: {run_id}")
            return run_id


def update_run_status(run_id: int, status: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE runs SET status=%s, end_time=NOW() WHERE id=%s",
                (status, run_id)
            )
            logger.info(f"Updated run {run_id} to status {status}")


def insert_artifact(run_id: int, stage: str, content: str, metadata: dict = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO artifacts (run_id, stage, content, metadata) VALUES (%s, %s, %s, %s)",
                (run_id, stage, content, json.dumps(metadata) if metadata else None)
            )
            logger.debug(f"Inserted artifact for run {run_id}, stage {stage}")


def insert_issue(run_id: int, type: str, description: str, severity: str, suggested_fix: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO issues (run_id, type, description, severity, suggested_fix) "
                "VALUES (%s, %s, %s, %s, %s)",
                (run_id, type, description, severity, suggested_fix)
            )
            logger.debug(f"Inserted issue for run {run_id}, type {type}")


def insert_pr(run_id: int, branch_name: str, pr_url: str, status: str = "created", merged: bool = False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO prs (run_id, branch_name, pr_url, status, merged) "
                "VALUES (%s, %s, %s, %s, %s)",
                (run_id, branch_name, pr_url, status, merged)
            )
            logger.info(f"Inserted PR for run {run_id}, branch {branch_name}")
