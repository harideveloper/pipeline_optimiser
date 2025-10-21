import os
import zipfile
from pathlib import Path
import requests
from github import Github, Auth

# --- CONFIG ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "harideveloper/pipeline-optimiser-test"  # Replace with your repo
BRANCH = "main"
WORKFLOW_NAME = "CI Test"  # <-- Set workflow name here

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")

# --- INIT GITHUB ---
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)

# --- GET REPO ---
repo = gh.get_repo(REPO)

# --- LIST WORKFLOWS ---
workflows = repo.get_workflows()
print("Available workflows:")
for wf in workflows:
    print(f"Workflow ID: {wf.id}, Name: {wf.name}")

# --- SELECT WORKFLOW ---
workflow = None
for wf in workflows:
    if wf.name == WORKFLOW_NAME:
        workflow = wf
        break

if not workflow:
    raise ValueError(f"Workflow '{WORKFLOW_NAME}' not found in repo.")

print(f"\nFetching runs for workflow: {workflow.name}")

# --- GET LATEST RUN ---
runs = workflow.get_runs(branch=BRANCH)
if runs.totalCount == 0:
    raise ValueError(f"No workflow runs found for branch '{BRANCH}'")

latest_run = runs[0]  # first/latest run
print(f"Latest Run ID: {latest_run.id}, Status: {latest_run.status}, Conclusion: {latest_run.conclusion}")

# --- GET LOGS URL ---
logs_url = latest_run.logs_url
print(f"Logs URL: {logs_url}")

# --- DOWNLOAD LOGS ---
headers = {"Authorization": f"token {GITHUB_TOKEN}"}
resp = requests.get(logs_url, headers=headers)

if resp.status_code == 200:
    # Save logs as zip
    log_zip_path = f"workflow_{latest_run.id}_logs.zip"
    with open(log_zip_path, "wb") as f:
        f.write(resp.content)
    print(f"Logs downloaded successfully: {log_zip_path}")

    # --- EXTRACT AND PRINT LOGS ---
    extract_dir = Path(f"workflow_{latest_run.id}_logs")
    with zipfile.ZipFile(log_zip_path, "r") as z:
        z.extractall(extract_dir)

    print(f"\n--- Logs extracted to {extract_dir} ---\n")
    for log_file in extract_dir.iterdir():
        if log_file.suffix == ".txt":
            print(f"\n--- Log: {log_file.name} ---\n")
            with open(log_file, "r") as f:
                for line in f:
                    print(line.strip())

else:
    print(f"Failed to download logs: {resp.status_code} - {resp.text}")
