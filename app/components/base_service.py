"""
Base service class with common patterns for workflow integration
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from app.repository.pipeline_repository import PipelineRepository
from app.utils.logger import get_logger

logger = get_logger(__name__, "BaseService")


class BaseService(ABC):
    """
    Abstract base class for all pipeline services.
    
    Provides:
    - Workflow integration (execute_node pattern)
    - Completion tracking
    - Error handling
    - Logging
    - Artifact persistence
    
    Subclasses MUST implement:
    - run(**kwargs): Public API
    - _execute(state): Workflow integration
    
    Subclasses CAN optionally override:
    - _get_artifact_key(): Enable artifact saving
    - _get_artifact_metadata(): Add artifact metadata
    """

    def __init__(self, agent_name: str):
        """
        Initialize service.
        
        Args:
            agent_name: Service identifier (e.g., "ingest", "analyze")
        """
        self.agent_name = agent_name
        self.repository = PipelineRepository()

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """
        Public API for direct service usage (outside workflow).
        
        Subclass MUST implement this method.
        
        Example:
            ingestor = Ingestor()
            yaml, log = ingestor.run(repo_url="...", pipeline_path="...")
        """
        pass

    @abstractmethod
    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal execution logic for workflow integration.
        
        Subclass MUST implement this method.
        
        Should:
        1. Extract data from state
        2. Call self.run() or perform logic
        3. Update state with results
        4. Return modified state
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        pass

    def execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute service as a workflow node.
        
        Don't override this method in subclasses.
        
        Handles:
        - Skip if already completed
        - Skip if previous error
        - Call _execute()
        - Track completion
        - Save artifacts
        - Handle errors
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        correlation_id = state.get("correlation_id")
        
        # Check if already completed
        completed_tools = state.get("completed_tools", [])
        if self.agent_name in completed_tools:
            logger.debug(
                f"{self._format_agent_name()} already completed, skipping",
                correlation_id=correlation_id
            )
            return state

        # Check for blocking errors
        if state.get("error"):
            logger.debug(
                f"Skipping {self.agent_name} due to previous error: {state['error']}",
                correlation_id=correlation_id
            )
            return state

        try:
            # Invoke subclass implementation
            state = self._execute(state)

            if not state.get("error"):
                completed_tools = state.get("completed_tools", [])
                if self.agent_name not in completed_tools:
                    completed_tools.append(self.agent_name)
                    state["completed_tools"] = completed_tools
                
                logger.debug(
                    f"{self._format_agent_name()} completed successfully",
                    correlation_id=correlation_id
                )
                self._save_artifact(state, correlation_id)

        except Exception as e:
            error_msg = f"{self._format_agent_name()} failed: {e}"
            state["error"] = error_msg
            
            # Use appropriate logging level based on exception type
            if isinstance(e, (RuntimeError, FileNotFoundError, ValueError)):
                logger.error(error_msg, correlation_id=correlation_id)
            else:
                logger.exception(error_msg, correlation_id=correlation_id)

        return state

    def _save_artifact(self, state: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        """
        Save service output as artifact.
        
        Don't override this method. Override _get_artifact_key() instead.
        
        Args:
            state: Current workflow state
            correlation_id: Request correlation ID
        """
        artifact_key = self._get_artifact_key()
        if not artifact_key:
            return

        content = state.get(artifact_key)
        if not content:
            logger.debug(
                f"No content at key '{artifact_key}'",
                correlation_id=correlation_id
            )
            return

        try:
            # Convert content to string if needed
            if isinstance(content, dict):
                import json
                content = json.dumps(content, indent=2, ensure_ascii=False)
            elif not isinstance(content, str):
                content = str(content)
            
            # Save to repository
            self.repository.save_artifact(
                run_id=state["run_id"],
                stage=self.agent_name,
                content=content,
                metadata=self._get_artifact_metadata(state),
                correlation_id=correlation_id
            )
            
            logger.debug(
                f"Artifact saved for {self.agent_name}",
                correlation_id=correlation_id
            )
            
        except Exception as e:
            logger.warning(
                f"Failed to save artifact for {self.agent_name}: {e}",
                correlation_id=correlation_id
            )

    def _get_artifact_key(self) -> Optional[str]:
        """
        Return state key for artifact to save.
        
        Override in subclass to enable artifact saving.
        Default: None (no artifact saved)
        
        Returns:
            State key name, or None
            
        Example:
            def _get_artifact_key(self):
                return "pipeline_yaml"
        """
        return None

    def _get_artifact_metadata(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return metadata for artifact.
        
        Override in subclass to add context.
        Default: empty dict
        
        Args:
            state: Current workflow state
            
        Returns:
            Metadata dictionary
            
        Example:
            def _get_artifact_metadata(self, state):
                return {"repo_url": state["repo_url"]}
        """
        return {}

    def _format_agent_name(self) -> str:
        """
        Format agent name for display in logs.
        
        Returns:
            Formatted agent name (e.g., "ingest" -> "Ingest")
        """
        return self.agent_name.replace('_', ' ').title()