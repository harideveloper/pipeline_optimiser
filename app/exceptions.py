"""
Custom exceptions for Pipeline Optimiser
"""

class PipelineOptimiserError(Exception):
    """Base exception for all pipeline optimizer errors"""
    pass

class DecisionError(PipelineOptimiserError):
    """Raised when decisioning fails"""
    pass

class ClassificationError(PipelineOptimiserError):
    """Raised when classification fails"""
    pass

class ValidationError(PipelineOptimiserError):
    """Raised when validation fails"""
    pass

class IngestionError(PipelineOptimiserError):
    """Raised when ingestion fails"""
    pass

class AnalysisError(PipelineOptimiserError):
    """Raised when analysis fails"""
    pass

class FixerError(PipelineOptimiserError):
    """Raised when fixer fails"""
    pass

class ResolverError(PipelineOptimiserError):
    """Raised when PR creation fails"""
    pass

class ReviewError(PipelineOptimiserError):
    """Raised when ReviewError fails"""
    pass

class RiskAssessorError(PipelineOptimiserError):
    """Raised when risk assessor fails"""
    pass

class SecurityScanError(PipelineOptimiserError):
    """Raised when security scann fails"""
    pass

class ConfigurationError(PipelineOptimiserError):
    """Raised when configuration is invalid"""
    pass

class DatabaseError(PipelineOptimiserError):
    """Raised when database operations fail"""
    pass