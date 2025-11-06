"""
CI/CD Pipeline Optimisation FastAPI App
"""

import os
import certifi
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager

from app.utils.logger import setup_logging, get_logger
from app.orchestrator.orchestrator import PipelineOrchestrator
from app.config import config

setup_logging()
logger = get_logger(__name__, "OptimiserAPI")


def configure_ssl_certificates() -> str:
    """
    Configure SSL certificates for HTTPS requests (dev/local only).
    """
    homebrew_cert_path = "/opt/homebrew/etc/ca-certificates/cert.pem"
    cert_path = homebrew_cert_path if os.path.exists(homebrew_cert_path) else certifi.where()

    os.environ["SSL_CERT_FILE"] = cert_path
    os.environ["REQUESTS_CA_BUNDLE"] = cert_path

    logger.info(f"Using SSL certificates from: {cert_path}", correlation_id="SYSTEM")
    return cert_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    """
    logger.info("Pipeline Optimiser API starting...", correlation_id="SYSTEM")
    logger.info(f"Version: {app.version}", correlation_id="SYSTEM")
    logger.info(f"Log Level: {config.LOG_LEVEL}", correlation_id="SYSTEM")

    if config.IS_LOCAL:
        cert_path = configure_ssl_certificates()
        logger.info(f"App is running in develop environment, loaded relevant ssl certs required: {cert_path}", correlation_id="SYSTEM")

    logger.info("Pipeline Optimier app is running and ready to serve requests", correlation_id="SYSTEM")
    yield
    logger.info("Pipeline Optimiser API shutting down", correlation_id="SYSTEM")


# FastAPI Application
app = FastAPI(
    title="Pipeline Optimiser Agent API",
    description="Agentic CI/CD pipeline optimisation",
    version="1.0.0",
    lifespan=lifespan,
)


class OptimiseRequest(BaseModel):
    """Request model for pipeline optimisation."""
    repo_url: str
    pipeline_path_in_repo: str
    build_log_path_in_repo: Optional[str] = None
    branch: Optional[str] = "main"
    pr_create: Optional[bool] = False


@app.get("/")
async def root():
    return {
        "name": "Pipeline Optimiser API",
        "version": app.version,
        "status": "running",
        "features": [
            "Workflow classification (CI/CD/Release/Scheduled)",
            "Risk-based tool selection",
            "Adaptive optimisation strategies",
            "Security scanning",
            "Automated PR creation",
        ],
        "endpoints": {
            "root": "/",
            "health": "/health",
            "optimise": "/optimise",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version}

@app.post("/optimise")
async def optimise_pipeline(request: OptimiseRequest):
    logger.info(
        f"Optimisation request received | "
        f"Repository: {request.repo_url} | "
        f"Pipeline: {request.pipeline_path_in_repo} | "
        f"Branch: {request.branch} | "
        f"PR: {request.pr_create}",
        correlation_id="REQUEST",
    )

    try:
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(
            repo_url=request.repo_url,
            pipeline_path=request.pipeline_path_in_repo,
            build_log_path=request.build_log_path_in_repo,
            branch=request.branch,
            pr_create=request.pr_create,
        )

        correlation_id = result.get("correlation_id", "UNKNOWN")

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Optimisation failed: {error_msg}", correlation_id=correlation_id)
            return {
                "status": "error",
                "correlation_id": correlation_id,
                "error": error_msg,
                "message": "Pipeline optimisation failed. Please check the error details.",
            }

        workflow_type = result.get("workflow_type", "UNKNOWN")
        risk_level = result.get("risk_level", "UNKNOWN")
        completed_tools = result.get("completed_tools", [])
        pr_url = result.get("pr_url")
        duration = result.get("duration", 0)

        if pr_url:
            logger.info(f"PR created: {pr_url}", correlation_id=correlation_id)

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
        return {"status": "error", "error": str(e), "message": "An unexpected error occurred during optimisation."}


def start_server():
    uvicorn.run(
        "app.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL,
    )


if __name__ == "__main__":
    logger.info("Starting Pipeline Optimiser server", correlation_id="SYSTEM")
    start_server()

