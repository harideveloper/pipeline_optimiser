# agents/agent.py
class Agent:
    """
    Base class for all agents.
    Each agent must implement the `run` method.
    """
    def run(self, **kwargs):
        raise NotImplementedError("Subclasses must implement the run() method")
