"""
Base agent class with common patterns for workflow integration
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from app.db import db
from app.utils.logger import get_logger

logger = get_logger(__name__, "BaseAgent")


class BaseAgent(ABC):
    """
    Base class for all agents with workflow integration
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """
        Main execution method - must be implemented by subclass
        This is for direct usage outside the workflow
        """
        pass

    def execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute this agent as a workflow node
        Handles completion checks, error handling, logging, and artifacts
        """
        correlation_id = state.get("correlation_id")
        
        # Check if already completed
        if self.agent_name in state.get("completed_steps", []):
            logger.info("%s already completed, skipping" % self.agent_name.title(), correlation_id=correlation_id)
            return state

        # Check for blocking errors
        if state.get("error"):
            return state

        logger.debug("Executing: %s" % self.agent_name.replace("_", " ").title(), correlation_id=correlation_id)

        try:
            # Call the subclass implementation
            state = self._execute(state)

            # Mark as completed if no error occurred
            if not state.get("error"):
                if self.agent_name not in state.get("completed_steps", []):
                    state["completed_tools"].append(self.agent_name)
                logger.debug("%s completed successfully" % self.agent_name.title(), correlation_id=correlation_id)

                # Save artifact if configured
                self._save_artifact(state, correlation_id)

        except Exception as e:
            error_msg = f"{self.agent_name.title()} failed: {e}"
            state["error"] = error_msg
            
            # Log exception with traceback only for unexpected errors
            # For expected errors (RuntimeError, FileNotFoundError, ValueError), just log error
            if isinstance(e, (RuntimeError, FileNotFoundError, ValueError)):
                logger.error(error_msg, correlation_id=correlation_id)
            else:
                logger.exception(error_msg, correlation_id=correlation_id)

        return state

    @abstractmethod
    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal execution - must be implemented by subclass
        This is called by execute_node() within the workflow
        """
        pass

    def _save_artifact(self, state: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        """
        Save artifact to database - can be overridden by subclass
        """
        artifact_key = self._get_artifact_key()
        if not artifact_key:
            return

        content = state.get(artifact_key)
        if not content:
            return

        try:
            # Convert content to string if needed
            if isinstance(content, dict):
                import json
                content = json.dumps(content, indent=2)
            elif not isinstance(content, str):
                content = str(content)

            db.insert_artifact(
                run_id=state["run_id"],
                stage=self.agent_name,
                content=content,
                metadata=self._get_artifact_metadata(state)
            )
        except Exception as e:
            logger.warning("Failed to save artifact for %s: %s" % (self.agent_name, e), correlation_id=correlation_id)

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return the state key that contains the artifact to save
        Override in subclass if artifact should be saved
        """
        return None

    def _get_artifact_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return metadata to save with artifact
        Override in subclass if needed
        """
        return {}