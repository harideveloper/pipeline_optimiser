"""
Ingestor Agent - Retrieves pipeline YAML and build logs from GitHub repositories.
"""

import os
import tempfile
import subprocess
from typing import Optional, Tuple, Dict, Any

from app.components.base_service import BaseService
from app.utils.logger import get_logger

logger = get_logger(__name__, "Ingestor")


class Ingestor(BaseService):
    """
    Ingests a GitHub repository to retrieve the pipeline YAML and optional build log.
    """

    def __init__(self):
        super().__init__(agent_name="ingest")

    def run(
        self,
        repo_url: str,
        pipeline_path_in_repo: str,
        build_log_path_in_repo: Optional[str] = None,
        branch: str = "main",
        correlation_id: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Clone repository and extract pipeline configuration and build logs.

        Returns:
            Tuple of (pipeline_yaml, build_log)
        """
        logger.info(
            "Cloning repo: %s (branch=%s, file=%s)" % (
                self._sanitize_url(repo_url),
                branch,
                pipeline_path_in_repo
            ),
            correlation_id=correlation_id
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_yaml = self._clone_and_load_pipeline(
                repo_url, branch, tmpdir, pipeline_path_in_repo, correlation_id
            )
            build_log = self._load_build_log(tmpdir, build_log_path_in_repo, correlation_id)

            logger.info(
                "Ingested: pipeline=%d bytes, build_log=%d bytes" % (
                    len(pipeline_yaml),
                    len(build_log) if build_log else 0
                ),
                correlation_id=correlation_id
            )
            return pipeline_yaml, build_log

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ingestion within workflow"""
        correlation_id = state.get("correlation_id")
        
        pipeline_yaml, build_log = self.run(
            repo_url=state["repo_url"],
            pipeline_path_in_repo=state["pipeline_path"],
            build_log_path_in_repo=state.get("build_log_path"),
            branch=state["branch"],
            correlation_id=correlation_id
        )
        
        state["pipeline_yaml"] = pipeline_yaml or ""
        state["build_log"] = build_log or ""
        
        if not pipeline_yaml:
            state["error"] = "Ingestor returned empty pipeline_yaml"
            logger.error("Empty pipeline YAML returned", correlation_id=correlation_id)
        
        return state

    def _get_artifact_key(self) -> Optional[str]:
        """Pipeline YAML should be saved as artifact"""
        return "pipeline_yaml"

    def _get_artifact_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Include build log in metadata"""
        return {"build_log": state.get("build_log", "")}

    def _clone_and_load_pipeline(
        self,
        repo_url: str,
        branch: str,
        tmpdir: str,
        pipeline_path_in_repo: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """Clone repository and load pipeline YAML file"""
        clone_cmd = ["git", "clone", "--branch", branch, "--depth", "1", repo_url, tmpdir]

        result = subprocess.run(clone_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr.strip().split('\n')[-1]  # Get last line only
            logger.error("Git clone failed: %s" % error_msg, correlation_id=correlation_id)
            raise RuntimeError(f"Repository not accessible: {error_msg}")

        pipeline_file = os.path.join(tmpdir, pipeline_path_in_repo)
        if not os.path.exists(pipeline_file):
            logger.error("Pipeline file not found: %s" % pipeline_path_in_repo, correlation_id=correlation_id)
            raise FileNotFoundError(f"Pipeline file not found: {pipeline_path_in_repo}")

        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipeline_yaml = f.read()
            return pipeline_yaml
        except Exception as e:
            logger.error("Failed to read pipeline file: %s" % str(e), correlation_id=correlation_id)
            raise

    def _load_build_log(
        self,
        tmpdir: str,
        build_log_path_in_repo: Optional[str],
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """Load build log file if specified"""
        if not build_log_path_in_repo:
            return None

        log_file = os.path.join(tmpdir, build_log_path_in_repo)
        if not os.path.exists(log_file):
            logger.debug(
                "Build log not found: %s (optional)" % build_log_path_in_repo,
                correlation_id=correlation_id
            )
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(
                "Failed to read build log: %s" % str(e),
                correlation_id=correlation_id
            )
            return None

    def _sanitize_url(self, url: str) -> str:
        """Remove credentials from URL for safe logging"""
        if "@" in url and "://" in url:
            protocol = url.split("://")[0]
            rest = url.split("@")[-1]
            return f"{protocol}://***@{rest}"
        return url