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
        "pipeline_path_in_repo": ".github/workflows/pipeline1.yaml",
        "build_log_path_in_repo": ".github/workflows/pipeline1.log",
        "branch": "main",
        "pr_create": True  # create PR
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
    
    # Handle None values properly
    analysis = result.get("analysis") or {}
    optimised_yaml = result.get("optimised_yaml")
    pr_url = result.get("pr_url")
    
    # Print analysis
    print("━" * 60)
    print("📊 ANALYSIS RESULTS")
    print("━" * 60)
    
    issues = analysis.get("issues_detected", []) if isinstance(analysis, dict) else []
    if issues:
        print(f"\n🔍 Found {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\n✅ No issues detected")
    
    fixes = analysis.get("suggested_fixes", []) if isinstance(analysis, dict) else []
    if fixes:
        print(f"\n💡 Suggested {len(fixes)} fixes:")
        for i, fix in enumerate(fixes, 1):
            print(f"  {i}. {fix}")
    
    improvement = analysis.get("expected_improvement", "") if isinstance(analysis, dict) else ""
    if improvement:
        print(f"\n📈 Expected improvement: {improvement}")
    
    print("\n" + "━" * 60)
    print("📄 OPTIMISED YAML")
    print("━" * 60)
    
    if optimised_yaml:
        lines = optimised_yaml.split('\n')
        preview_lines = min(30, len(lines))
        print('\n'.join(lines[:preview_lines]))
        if len(lines) > preview_lines:
            print(f"\n... ({len(lines) - preview_lines} more lines)")
    else:
        print("\n⚠️  No optimised YAML generated")
    
    # Print PR info
    print("\n" + "━" * 60)
    print("🔗 PULL REQUEST")
    print("━" * 60)
    
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