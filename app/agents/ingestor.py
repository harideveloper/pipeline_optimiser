"""
Ingestor Agent - Retrieves pipeline YAML and build logs from GitHub repositories.
Refactored for clarity, maintainability, and coding standards.
"""

import os
import tempfile
import subprocess
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class IngestorAgent():
    """
    Ingests a GitHub repository to retrieve the pipeline YAML and optional build log.
    """

    def run(
        self,
        repo_url: str,
        pipeline_path_in_repo: str,
        build_log_path_in_repo: Optional[str] = None,
        branch: str = "main"
    ) -> Tuple[str, Optional[str]]:
        """
        Clone repository and extract pipeline configuration and build logs.

        Args:
            repo_url: GitHub repository URL to clone
            pipeline_path_in_repo: Path to pipeline YAML file within repository
            build_log_path_in_repo: Optional path to build log file
            branch: Git branch to clone (default: "main")

        Returns:
            Tuple of (pipeline_yaml, build_log) where build_log may be None
        """
        logger.info(
            "Ingesting repository: repo=%s, branch=%s, pipeline_path=%s",
            self._sanitize_url(repo_url),
            branch,
            pipeline_path_in_repo
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_yaml = self._clone_and_load_pipeline(
                repo_url, branch, tmpdir, pipeline_path_in_repo
            )
            build_log = self._load_build_log(tmpdir, build_log_path_in_repo)

            logger.info(
                "Ingestion complete: pipeline_size=%d bytes, build_log_size=%s bytes",
                len(pipeline_yaml),
                len(build_log) if build_log else 0
            )
            return pipeline_yaml, build_log

    # ---------------------------
    # Internal helpers
    # ---------------------------
    def _clone_and_load_pipeline(
        self,
        repo_url: str,
        branch: str,
        tmpdir: str,
        pipeline_path_in_repo: str
    ) -> str:
        """
        Clone repository and load pipeline YAML file.
        """
        clone_cmd = ["git", "clone", "--branch", branch, "--depth", "1", repo_url, tmpdir]

        result = subprocess.run(clone_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("Git clone failed: %s", result.stderr.strip())
            raise RuntimeError(f"Git clone failed: {result.stderr.strip()}")

        pipeline_file = os.path.join(tmpdir, pipeline_path_in_repo)
        if not os.path.exists(pipeline_file):
            raise FileNotFoundError(f"Pipeline file not found: {pipeline_path_in_repo}")

        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipeline_yaml = f.read()
            logger.info("Pipeline loaded: size=%d bytes", len(pipeline_yaml))
            return pipeline_yaml
        except Exception as e:
            logger.error("Failed to read pipeline file: %s", str(e))
            raise

    def _load_build_log(
        self,
        tmpdir: str,
        build_log_path_in_repo: Optional[str]
    ) -> Optional[str]:
        """
        Load build log file if specified.
        """
        if not build_log_path_in_repo:
            return None

        log_file = os.path.join(tmpdir, build_log_path_in_repo)
        if not os.path.exists(log_file):
            logger.warning(
                "Build log not found: %s (optional, continuing without it)",
                build_log_path_in_repo
            )
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                build_log = f.read()
            logger.info("Build log loaded: size=%d bytes", len(build_log))
            return build_log
        except Exception as e:
            logger.warning("Failed to read build log (continuing without it): %s", str(e))
            return None

    def _sanitize_url(self, url: str) -> str:
        """
        Remove credentials from URL for safe logging.
        """
        if "@" in url and "://" in url:
            protocol = url.split("://")[0]
            rest = url.split("@")[-1]
            return f"{protocol}://***@{rest}"
        return url
