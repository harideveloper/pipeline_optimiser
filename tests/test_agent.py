import json
import requests
from app.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__, "PipelineTestAgent")

# env vars
endpoint = "http://localhost:8091/optimise"
repo_url = "https://github.com/harideveloper/multi-tech-test-repo"
pipeline_path_in_repo = ".github/workflows/pipeline1.yaml"
build_log_path_in_repo = ".github/workflows/pipeline2.log"
branch = "main"
pr_create = True


def test_optimise_pipeline():

    payload = {
        "repo_url": repo_url,
        "pipeline_path_in_repo": pipeline_path_in_repo,
        "build_log_path_in_repo": build_log_path_in_repo,
        "branch": branch,
        "pr_create": pr_create
    }
    logger.info("Starting pipeline optimisation...", correlation_id="SYSTEM")

    try:
        res = requests.post("http://localhost:8091/optimise", json=payload)
        result = res.json()
    except json.JSONDecodeError:
        logger.error(
            f"API did not return valid JSON. Response: {res.text}",
            correlation_id="SYSTEM"
        )
        return
    except requests.RequestException as e:
        logger.error(f"Error making request to API: {str(e)}", correlation_id="SYSTEM")
        return

    if result.get("status") != "success":
        logger.error(
            f"API returned error: {json.dumps(result, indent=2)}",
            correlation_id="SYSTEM"
        )
        return

    workflow_type = result.get("workflow_type", "UNKNOWN")
    risk_level = result.get("risk_level", "UNKNOWN")
    duration = result.get("duration", 0)
    tools_executed = result.get("tools_executed", 0)
    tools = result.get("tools", [])
    pr_url = result.get("pr_url")

    logger.info(
        f"Workflow Type: {workflow_type} | Risk Level: {risk_level} | "
        f"Duration: {duration:.2f}s | Tools Executed: {tools_executed}",
        correlation_id="SYSTEM"
    )

    if tools:
        logger.info(f"Execution Flow: {' → '.join(tools)}", correlation_id="SYSTEM")

    if pr_url:
        logger.info(f"PR successfully created: {pr_url}", correlation_id="SYSTEM")
    else:
        logger.info("No PR created.", correlation_id="SYSTEM")

if __name__ == "__main__":
    test_optimise_pipeline()
