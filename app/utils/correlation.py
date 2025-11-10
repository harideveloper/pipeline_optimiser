"""
Orchestrator utility functions
"""
import random


def generate_correlation_id() -> str:
    """
    Generate a numeric correlation ID for request tracking
    
    Format: 8-digit number (e.g., '48273945')
    
    Returns:
        str: Unique correlation ID (8 digits)
    """
    return str(random.randint(10000000, 99999999))