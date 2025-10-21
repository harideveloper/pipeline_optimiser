"""
Ingestor Agent - Retrieves pipeline YAML and build logs from GitHub repositories.
TBU - Ingestor will use LLM to extract important info from the raw log and store in the db (To be revisted later)
"""

import os
import tempfile
import subprocess
from typing import Optional, Tuple, Dict, Any
from app.components.base_service import BaseService
from app.utils.logger import get_logger
from app.config import config
from app.exceptions import IngestionError

logger = get_logger(__name__, "Ingestor")


class Ingestor(BaseService):
    """ Ingests a GitHub repository to retrieve the pipeline YAML and optional build log."""

    def __init__(self):
        """Initialize Ingestor."""
        super().__init__(agent_name="ingest")
        logger.debug("Initialized Ingestor", correlation_id="INIT")

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
        
        Args:
            repo_url: GitHub repository URL
            pipeline_path_in_repo: Path to pipeline YAML file in repo
            build_log_path_in_repo: Optional path to build log file in repo
            branch: Git branch to clone (default: main)
            correlation_id: Request correlation ID
            
        Returns:
            Tuple of (pipeline_yaml, build_log)
            
        Raises:
            IngestionError: If cloning or file reading fails
        """
        # Validate inputs
        if not repo_url or not isinstance(repo_url, str):
            raise IngestionError("repo_url must be a non-empty string")
        
        if not pipeline_path_in_repo or not isinstance(pipeline_path_in_repo, str):
            raise IngestionError("pipeline_path_in_repo must be a non-empty string")
        
        logger.debug(
            f"Cloning repo: {self._sanitize_url(repo_url)} (branch={branch}, file={pipeline_path_in_repo})",
            correlation_id=correlation_id
        )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone and load pipeline
                pipeline_yaml = self._clone_and_load_pipeline(
                    repo_url, branch, tmpdir, pipeline_path_in_repo, correlation_id
                )
                
                # Load optional build log
                build_log = self._load_build_log(tmpdir, build_log_path_in_repo, correlation_id)

                logger.info(
                    f"Ingested: pipeline={len(pipeline_yaml)} bytes, build_log={len(build_log) if build_log else 0} bytes",
                    correlation_id=correlation_id
                )
                
                return pipeline_yaml, build_log
                
        except (RuntimeError, FileNotFoundError) as e:
            # Re-raise as IngestionError
            raise IngestionError(f"Failed to ingest repository: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during ingestion: {e}", correlation_id=correlation_id)
            raise IngestionError(f"Unexpected error during ingestion: {e}") from e

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute ingestion within workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with pipeline_yaml and build_log
        """
        correlation_id = state.get("correlation_id")
        
        try:
            pipeline_yaml, build_log = self.run(
                repo_url=state["repo_url"],
                pipeline_path_in_repo=state["pipeline_path"],
                build_log_path_in_repo=state.get("build_log_path"),
                branch=state.get("branch", "main"),
                correlation_id=correlation_id
            )
            
            state["pipeline_yaml"] = pipeline_yaml or ""
            state["build_log"] = build_log or ""
            
            if not pipeline_yaml:
                state["error"] = "Ingestor returned empty pipeline_yaml"
                logger.error("Empty pipeline YAML returned", correlation_id=correlation_id)
                
        except IngestionError as e:
            state["error"] = f"Ingestion failed: {e}"
            logger.error(f"Ingestion failed: {e}", correlation_id=correlation_id)
        
        return state

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact saving.
        
        Returns:
            Key name for pipeline YAML in state
        """
        return "pipeline_yaml"

    def _get_artifact_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return metadata for artifact.
        
        Args:
            state: Current workflow state
            
        Returns:
            Metadata dictionary with build_log
        """
        return {"build_log": state.get("build_log", "")}

    def _clone_and_load_pipeline(
        self,
        repo_url: str,
        branch: str,
        tmpdir: str,
        pipeline_path_in_repo: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Clone repository and load pipeline YAML file.
        
        Args:
            repo_url: GitHub repository URL
            branch: Git branch to clone
            tmpdir: Temporary directory for cloning
            pipeline_path_in_repo: Path to pipeline file in repo
            correlation_id: Request correlation ID
            
        Returns:
            Pipeline YAML content as string
            
        Raises:
            RuntimeError: If git clone fails
            FileNotFoundError: If pipeline file not found
        """
        # Build git clone command with depth from config
        clone_cmd = [
            "git", "clone",
            "--branch", branch,
            "--depth", str(config.GIT_CLONE_DEPTH),
            repo_url,
            tmpdir
        ]

        # Execute clone with timeout
        try:
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=config.GIT_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            logger.error(
                f"Git clone timeout after {config.GIT_TIMEOUT}s",
                correlation_id=correlation_id
            )
            raise RuntimeError(f"Git clone timeout after {config.GIT_TIMEOUT}s")
        
        # Check for clone errors
        if result.returncode != 0:
            error_msg = result.stderr.strip().split('\n')[-1] if result.stderr else "Unknown error"
            logger.error(f"Git clone failed: {error_msg}", correlation_id=correlation_id)
            raise RuntimeError(f"Repository not accessible: {error_msg}")

        # Locate pipeline file
        pipeline_file = os.path.join(tmpdir, pipeline_path_in_repo)
        if not os.path.exists(pipeline_file):
            logger.error(f"Pipeline file not found: {pipeline_path_in_repo}", correlation_id=correlation_id)
            raise FileNotFoundError(f"Pipeline file not found: {pipeline_path_in_repo}")

        # Read pipeline file
        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipeline_yaml = f.read()
            
            logger.debug(f"Successfully loaded pipeline file: {pipeline_path_in_repo}", correlation_id=correlation_id)
            return pipeline_yaml
            
        except Exception as e:
            logger.error(f"Failed to read pipeline file: {e}", correlation_id=correlation_id)
            raise RuntimeError(f"Failed to read pipeline file: {e}") from e

    def _load_build_log(
        self,
        tmpdir: str,
        build_log_path_in_repo: Optional[str],
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Load build log file if specified.
        
        Args:
            tmpdir: Temporary directory containing cloned repo
            build_log_path_in_repo: Optional path to build log file in repo
            correlation_id: Request correlation ID
            
        Returns:
            Build log content as string, or None if not found/specified
        """
        if not build_log_path_in_repo:
            logger.debug("No build log path specified", correlation_id=correlation_id)
            return None

        log_file = os.path.join(tmpdir, build_log_path_in_repo)
        
        if not os.path.exists(log_file):
            logger.debug(
                f"Build log not found: {build_log_path_in_repo} (optional)",
                correlation_id=correlation_id
            )
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                build_log = f.read()
            
            logger.debug(f"Successfully loaded build log: {build_log_path_in_repo}", correlation_id=correlation_id)
            return build_log
            
        except Exception as e:
            logger.warning(
                f"Failed to read build log: {e}",
                correlation_id=correlation_id
            )
            return None

    def _sanitize_url(self, url: str) -> str:
        """
        Remove credentials from URL for safe logging.
        
        Args:
            url: Git repository URL (may contain credentials)
            
        Returns:
            Sanitized URL with credentials masked
        """
        if "@" in url and "://" in url:
            protocol = url.split("://")[0]
            rest = url.split("@")[-1]
            return f"{protocol}://***@{rest}"
        return url