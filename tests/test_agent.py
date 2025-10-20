# tests/test_agent.py
import requests
import json
import os

def test_optimise_pipeline():
    # Check if GitHub token is set
    gh_token = os.getenv("GITHUB_TOKEN")
    if not gh_token:
        print("⚠️  Warning: GITHUB_TOKEN not set. PR creation will be skipped.")
    
    payload = {
        "repo_url": "https://github.com/harideveloper/multi-tech-test-repo",
        "pipeline_path_in_repo": ".github/workflows/docs-ci.yaml",
        "build_log_path_in_repo": ".github/workflows/docs-ci.log",
        "branch": "main",
        "pr_create": True
    }
    
    print("🚀 Starting pipeline optimisation...\n")
    res = requests.post("http://localhost:8091/optimise", json=payload)
    
    try:
        result = res.json()
    except json.JSONDecodeError:
        print("❌ API did not return valid JSON")
        print(res.text)
        return
    
    if result.get("status") != "success":
        print("❌ API returned error:", json.dumps(result, indent=2))
        return
    
    print("✅ API returned success.\n")
    
    # Print workflow info
    print("━" * 60)
    print("📊 WORKFLOW ANALYSIS")
    print("━" * 60)
    print(f"\n🔍 Workflow Type: {result.get('workflow_type', 'UNKNOWN')}")
    print(f"⚠️  Risk Level: {result.get('risk_level', 'UNKNOWN')}")
    print(f"⏱️  Duration: {result.get('duration', 0):.2f}s")
    print(f"🔧 Tools Executed: {result.get('tools_executed', 0)}")
    
    tools = result.get('tools', [])
    if tools:
        print(f"\n📝 Execution Flow:")
        print(f"   {' → '.join(tools)}")
    
    # Print PR info
    print("\n" + "━" * 60)
    print("🔗 PULL REQUEST")
    print("━" * 60)
    
    pr_url = result.get("pr_url")
    if pr_url:
        print(f"\n✅ PR successfully created!")
        print(f"   {pr_url}")
    else:
        print("\nℹ️  No PR created")
        if not gh_token:
            print("   Reason: GITHUB_TOKEN not configured")
    
    print("\n" + "━" * 60)

if __name__ == "__main__":
    test_optimise_pipeline()