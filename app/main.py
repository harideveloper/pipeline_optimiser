# """
# FastAPI application for CI/CD Pipeline Optimisation.
# """

# import os
# import certifi
# import uvicorn
# from fastapi import FastAPI
# from pydantic import BaseModel
# from typing import Optional
# from app.utils.logger import setup_logging, get_logger
# from app.agents.orchestrator import PipelineOrchestrator


# setup_logging()
# logger = get_logger(__name__)

# # ssl certs for local dev only
# CERT_PATH = '/opt/homebrew/etc/ca-certificates/cert.pem'
# if not os.path.exists(CERT_PATH):
#     CERT_PATH = certifi.where()
#     logger.info("Using certifi certificates: %s", CERT_PATH)
# else:
#     logger.info("Using Homebrew certificates: %s", CERT_PATH)

# os.environ['SSL_CERT_FILE'] = CERT_PATH
# os.environ['REQUESTS_CA_BUNDLE'] = CERT_PATH

# # app 
# app = FastAPI(
#     title="Pipeline Optimiser Agent API",
#     description="AI-powered CI/CD pipeline Optimisation service",
#     version="1.0.0"
# )


# class OptimiseRequest(BaseModel):
#     """Request model for pipeline Optimisation."""
#     repo_url: str
#     pipeline_path_in_repo: str
#     build_log_path_in_repo: Optional[str] = None
#     branch: Optional[str] = "main"
#     pr_create: Optional[bool] = False  # create PR if True
#     verbose: Optional[bool] = False


# @app.on_event("startup")
# async def startup_event():
#     """Application startup event handler."""
#     logger.info("Pipeline Optimiser API Starting")
#     logger.info("Environment: %s", os.getenv("ENV", "development"))
#     logger.info("Log Level: %s", os.getenv("LOG_LEVEL", "INFO"))
#     logger.info("SSL Certificates: %s", CERT_PATH)
    
#     # Check for required environment variables
#     if not os.getenv("OPENAI_API_KEY"):
#         logger.warning("OPENAI_API_KEY not set - Optimisation will fail")
#     else:
#         logger.info("OpenAI API key configured")
    
#     if not os.getenv("GITHUB_TOKEN"):
#         logger.warning("GITHUB_TOKEN not set - PR creation will be disabled")
#     else:
#         logger.info("GitHub token configured")
    
#     logger.info("Application ready to receive requests")
#     logger.info("=" * 60)


# @app.on_event("shutdown")
# async def shutdown_event():
#     """Application shutdown event handler."""
#     logger.info("Pipeline Optimiser API shutting down")


# @app.get("/")
# async def root():
#     """ API information."""
#     logger.debug("API Info accessed through root endpoint")
#     return {
#         "name": "Pipeline Optimiser API",
#         "version": "1.0.0",
#         "status": "running",
#         "endpoints": {
#             "Optimise": "/optimise",
#             "health": "/health"
#         }
#     }


# @app.get("/health")
# def health_check():
#     """Health check endpoint."""
#     logger.debug("Pipeline Optimiser Health Check endpoint requested")
    
#     health_status = {
#         "status": "healthy",
#         "checks": {
#             "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
#             "github_configured": bool(os.getenv("GITHUB_TOKEN")),
#             "ssl_configured": bool(os.getenv("SSL_CERT_FILE"))
#         }
#     }
    
#     return health_status


# @app.post("/optimise")
# def Optimise_pipeline(request: OptimiseRequest):
#     """
#     Optimise a CI/CD pipeline by analysing it and suggesting improvements.
    
#     Requires:
#     - OPENAI_API_KEY environment variable for LLM calls
#     - GITHUB_TOKEN environment variable for PR creation (if pr_create=True)
    
#     Args:
#         request: Optimisation request containing repository details
        
#     Returns:
#         Optimisation results including analysis, Optimised YAML, and PR URL
#     """
#     logger.info("Optimisation request received")
#     logger.info("Repository: %s | Pipeline path: %s | Branch: %s | PR creation: %s | Verbose mode: %s ", request.repo_url, request.pipeline_path_in_repo, request.branch, request.pr_create,request.verbose )
    
#     try:
#         pipeline = PipelineOrchestrator(verbose=request.verbose)
#         logger.info("Starting pipeline Optimisation workflow")
#         result = pipeline.run(
#             repo_url=request.repo_url,
#             pipeline_path=request.pipeline_path_in_repo,
#             build_log_path=request.build_log_path_in_repo,
#             branch=request.branch,
#             pr_create=request.pr_create
#         )
#         if result.get("error"):
#             logger.error("Optimisation failed: %s", result["error"])
#             return {
#                 "status": "error",
#                 "error": result["error"],
#                 "analysis": result.get("analysis"),
#                 "Optimised_yaml": result.get("Optimised_yaml"),
#                 "pr_url": result.get("pr_url")
#             }
#         else:
#             analysis = result.get("analysis", {})
#             issues_count = len(analysis.get("issues_detected", []))
#             yaml_size = len(result.get("Optimised_yaml", ""))
#             pr_url = result.get("pr_url")
            
#             logger.info("Optimisation completed successfully")
#             logger.info("Issues detected: %d", issues_count)
#             logger.info("Optimised YAML size: %d bytes", yaml_size)
            
#             if pr_url:
#                 logger.info("PR created: %s", pr_url)
#             elif request.pr_create:
#                 logger.warning("PR creation was requested but not completed")
            
#             return {
#                 "status": "success",
#                 "analysis": result.get("analysis"),
#                 "Optimised_yaml": result.get("Optimised_yaml"),
#                 "pr_url": result.get("pr_url")
#             }
    
#     except Exception as e:
#         logger.error("Exception during pipeline Optimisation: %s", str(e), exc_info=True)
        
#         import traceback
#         error_trace = traceback.format_exc()
        
#         return {
#             "status": "error",
#             "error": str(e) or "Unknown error",
#             "traceback": error_trace
#         }


# if __name__ == "__main__":
#     logger.info("Starting Pipeline Optimiser server")
#     logger.info("Host: 0.0.0.0")
#     logger.info("Port: 8091")
    
#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=8091,
#         log_level="info"
#     )


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

# ----------------------------
# Logging setup
# ----------------------------
setup_logging()
logger = get_logger(__name__)

# ----------------------------
# SSL Certificate Configuration
# ----------------------------
def configure_ssl_certificates() -> str:
    """Configure SSL certificates for local dev or production."""
    cert_path = '/opt/homebrew/etc/ca-certificates/cert.pem'
    if not os.path.exists(cert_path):
        cert_path = certifi.where()
        logger.info("Using certifi certificates: %s", cert_path)
    else:
        logger.info("Using Homebrew certificates: %s", cert_path)

    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    return cert_path

CERT_PATH = configure_ssl_certificates()

# ----------------------------
# Helper Functions
# ----------------------------
def validate_environment():
    """Check for required environment variables."""
    required_vars = ["OPENAI_API_KEY", "GITHUB_TOKEN"]
    for var in required_vars:
        if not os.getenv(var):
            logger.warning("%s not set - some functionality may fail", var)
        else:
            logger.info("%s configured", var)

async def run_pipeline_orchestration(request: "OptimiseRequest") -> dict:
    """Run the pipeline orchestration workflow."""
    pipeline = PipelineOrchestrator(verbose=request.verbose)
    result = pipeline.run(
        repo_url=request.repo_url,
        pipeline_path=request.pipeline_path_in_repo,
        build_log_path=request.build_log_path_in_repo,
        branch=request.branch,
        pr_create=request.pr_create
    )
    return result

# ----------------------------
# Lifespan Handler
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Pipeline Optimiser API Starting")
    logger.info("Environment: %s", os.getenv("ENV", "development"))
    logger.info("Log Level: %s", os.getenv("LOG_LEVEL", "INFO"))
    logger.info("SSL Certificates: %s", CERT_PATH)
    validate_environment()
    logger.info("Application ready to receive requests")
    logger.info("=" * 60)
    
    yield # app startup
    
    # Shutdown logic to be added 
    logger.info("Pipeline Optimiser API shutting down")

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(
    title="Pipeline Optimiser Agent API",
    description="AI-powered CI/CD pipeline Optimisation service",
    version="1.0.0",
    lifespan=lifespan
)

# ----------------------------
# Request Models
# ----------------------------
class OptimiseRequest(BaseModel):
    """Request model for pipeline optimisation."""
    repo_url: str
    pipeline_path_in_repo: str
    build_log_path_in_repo: Optional[str] = None
    branch: Optional[str] = "main"
    pr_create: Optional[bool] = False  # restored for PR creation
    verbose: Optional[bool] = False

# ----------------------------
# Endpoints
# ----------------------------
@app.get("/")
async def root():
    """API information."""
    logger.debug("API Info accessed through root endpoint")
    return {
        "name": "Pipeline Optimiser API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "optimise": "/optimise",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint (does not expose secrets)."""
    logger.debug("Pipeline Optimiser Health Check endpoint requested")
    return {
        "status": "healthy",
        "checks": {
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "github_configured": bool(os.getenv("GITHUB_TOKEN")),
            "ssl_configured": bool(os.getenv("SSL_CERT_FILE"))
        }
    }

@app.post("/optimise")
async def optimise_pipeline(request: OptimiseRequest):
    """
    Optimise a CI/CD pipeline by analysing it and suggesting improvements.
    
    Requires:
    - OPENAI_API_KEY environment variable for LLM calls
    - GITHUB_TOKEN environment variable for PR creation (if pr_create=True)
    """
    logger.info(
        "Optimisation request received | Repository: %s | Pipeline path: %s | Branch: %s | PR creation: %s | Verbose: %s",
        request.repo_url, request.pipeline_path_in_repo, request.branch, request.pr_create, request.verbose
    )

    try:
        result = await run_pipeline_orchestration(request)

        if result.get("error"):
            logger.error("Optimisation failed: %s", result["error"])
            return {"status": "error", **result}

        analysis = result.get("analysis", {})
        issues_count = len(analysis.get("issues_detected", []))
        yaml_size = len(result.get("Optimised_yaml", ""))
        pr_url = result.get("pr_url")

        logger.info("Optimisation completed successfully")
        logger.info("Issues detected: %d", issues_count)
        logger.info("Optimised YAML size: %d bytes", yaml_size)
        if pr_url:
            logger.info("PR created: %s", pr_url)
        elif request.pr_create:
            logger.warning("PR creation was requested but not completed")

        return {"status": "success", **result}

    except Exception as e:
        logger.exception("Exception during pipeline optimisation")
        return {"status": "error", "error": str(e)}

# ----------------------------
# Run Server
# ----------------------------
def start_server():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8091,
        log_level="info"
    )

if __name__ == "__main__":
    logger.info("Starting Pipeline Optimiser server")
    start_server()
