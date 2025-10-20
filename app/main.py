"""
FastAPI application for CI/CD Pipeline Optimisation.
"""

import os
import certifi
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from app.utils.logger import setup_logging, get_logger
from app.agents.orchestrator import PipelineOrchestrator

setup_logging()
logger = get_logger(__name__, "MainAPI")


def configure_ssl_certificates() -> str:
    """Configure SSL certificates for local dev or production."""
    cert_path = '/opt/homebrew/etc/ca-certificates/cert.pem'
    if not os.path.exists(cert_path):
        cert_path = certifi.where()
        logger.info("Using certifi certificates: %s" % cert_path, correlation_id="SYSTEM")
    else:
        logger.info("Using Homebrew certificates: %s" % cert_path, correlation_id="SYSTEM")

    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    return cert_path


CERT_PATH = configure_ssl_certificates()


def validate_environment():
    """Check for required environment variables."""
    required_vars = ["OPENAI_API_KEY", "GITHUB_TOKEN"]
    for var in required_vars:
        if not os.getenv(var):
            logger.warning("%s not set - some functionality may fail" % var, correlation_id="SYSTEM")
        else:
            logger.info("%s configured" % var, correlation_id="SYSTEM")


async def run_pipeline_orchestration(request: "OptimiseRequest") -> dict:
    """Run the pipeline orchestration workflow."""
    pipeline = PipelineOrchestrator(
        model_name="gpt-4o-mini",
        temperature=0.1,
    )
    
    result = pipeline.run(
        repo_url=request.repo_url,
        pipeline_path=request.pipeline_path_in_repo,
        build_log_path=request.build_log_path_in_repo,
        branch=request.branch,
        pr_create=request.pr_create
    )
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Pipeline Optimiser API Starting (Hybrid Plan-Based)", correlation_id="SYSTEM")
    logger.info("Environment: %s" % os.getenv("ENV", "development"), correlation_id="SYSTEM")
    logger.info("Log Level: %s" % os.getenv("LOG_LEVEL", "INFO"), correlation_id="SYSTEM")
    logger.info("SSL Certificates: %s" % CERT_PATH, correlation_id="SYSTEM")
    validate_environment()
    logger.info("Application ready to receive requests", correlation_id="SYSTEM")
    
    yield
    
    logger.info("Pipeline Optimiser API shutting down", correlation_id="SYSTEM")


app = FastAPI(
    title="Pipeline Optimiser Agent API (Hybrid Plan-Based)",
    description="AI-powered CI/CD pipeline optimization with adaptive strategies",
    version="2.0.0",
    lifespan=lifespan
)


class OptimiseRequest(BaseModel):
    """Request model for pipeline optimisation."""
    repo_url: str
    pipeline_path_in_repo: str
    build_log_path_in_repo: Optional[str] = None
    branch: Optional[str] = "main"
    pr_create: Optional[bool] = False
    verbose: Optional[bool] = False 


@app.get("/")
async def root():
    """API information."""
    return {
        "name": "Pipeline Optimiser API (Hybrid Plan-Based)",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "Workflow classification (CI/CD/Release)",
            "Risk-based tool selection",
            "Adaptive optimization strategies",
            "Safety guardrails"
        ],
        "endpoints": {
            "optimise": "/optimise",
            "health": "/health"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "mode": "Hybrid Plan-Based",
        "checks": {
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "github_configured": bool(os.getenv("GITHUB_TOKEN")),
            "ssl_configured": bool(os.getenv("SSL_CERT_FILE"))
        }
    }


@app.post("/optimise")
async def optimise_pipeline(request: OptimiseRequest):
    """
    Optimise a CI/CD pipeline using Hybrid Plan-Based pattern.
    """
    logger.info(
        "Optimisation request received | Repository: %s | Pipeline: %s | Branch: %s | PR: %s" % (
            request.repo_url,
            request.pipeline_path_in_repo,
            request.branch,
            request.pr_create
        ),
        correlation_id="REQUEST"
    )

    try:
        result = await run_pipeline_orchestration(request)
        
        correlation_id = result.get("correlation_id", "UNKNOWN")

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            logger.error("Optimisation failed: %s" % error_msg, correlation_id=correlation_id)
            
            # Return user-friendly error response
            return {
                "status": "error",
                "correlation_id": correlation_id,
                "error": error_msg,
                "message": "Pipeline optimisation failed. Please check the error details."
            }

        workflow_type = result.get("workflow_type", "UNKNOWN")
        risk_level = result.get("risk_level", "UNKNOWN")
        completed_tools = result.get("completed_tools", [])
        pr_url = result.get("pr_url")
        duration = result.get("duration", 0)
    
        if pr_url:
            logger.info("PR created: %s" % pr_url, correlation_id=correlation_id)

        return {
            "status": "success",
            "correlation_id": correlation_id,
            "workflow_type": workflow_type,
            "risk_level": risk_level,
            "tools_executed": len(completed_tools),
            "tools": completed_tools,
            "duration": duration,
            "pr_url": pr_url,
        }

    except Exception as e:
        logger.exception("Exception during pipeline optimisation", correlation_id="ERROR")
        return {
            "status": "error",
            "error": str(e),
            "message": "An unexpected error occurred during optimisation."
        }


def start_server():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8091,
        log_level="info"
    )


if __name__ == "__main__":
    logger.info("Starting Pipeline Optimiser server", correlation_id="SYSTEM")
    start_server()