#!/usr/bin/env python3
"""
Build Metrics Extractor - Uses GitHub Actions API for accurate timings
"""

import os
import sys
import json
import requests
from typing import Dict, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


# =====================================================
# CONFIGURATION
# =====================================================

REPO_URL = "https://github.com/harideveloper/pipeline-optimiser-test"
BRANCH = "optimise-pipeline-23777200"
PIPELINE_PATH = ".github/workflows/lint-ci.yml"

# =====================================================


@dataclass
class BuildMetrics:
    """Build performance metrics"""
    total_duration_seconds: int = None
    job_durations: Dict[str, int] = None
    step_durations: Dict[str, int] = None
    cache_hits: int = 0
    cache_misses: int = 0
    cache_efficiency: float = None
    parallel_jobs_count: int = 0
    total_steps: int = 0
    failed_steps: int = 0
    
    def __post_init__(self):
        if self.job_durations is None:
            self.job_durations = {}
        if self.step_durations is None:
            self.step_durations = {}


class GitHubActionsAPI:
    """GitHub Actions API client"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        """Parse repo URL."""
        repo_url = repo_url.rstrip('/').replace('.git', '')
        if 'github.com' in repo_url:
            parts = repo_url.split('github.com/')[-1].split('/')
        else:
            parts = repo_url.split('/')
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Invalid repo format: {repo_url}")
    
    def get_workflow_filename(self, pipeline_path: str) -> str:
        """Extract workflow filename."""
        return pipeline_path.split('/')[-1]
    
    def fetch_metrics(self, owner: str, repo: str, workflow_file: str, branch: str) -> BuildMetrics:
        """Fetch build metrics using GitHub Actions API."""
        
        print(f"🔍 Fetching workflows for {owner}/{repo}...")
        
        # Get workflow
        workflows_url = f"{self.base_url}/repos/{owner}/{repo}/actions/workflows"
        response = requests.get(workflows_url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch workflows: {response.status_code}")
        
        workflows = response.json().get("workflows", [])
        workflow = next((w for w in workflows if w["path"].endswith(workflow_file)), None)
        if not workflow:
            raise Exception(f"Workflow '{workflow_file}' not found")
        
        print(f"✅ Found workflow: {workflow['name']}")
        
        # Get latest run
        print(f"🔍 Fetching latest run for branch '{branch}'...")
        runs_url = f"{self.base_url}/repos/{owner}/{repo}/actions/workflows/{workflow['id']}/runs"
        params = {"branch": branch, "per_page": 1, "status": "completed"}
        
        response = requests.get(runs_url, headers=self.headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch runs: {response.status_code}")
        
        runs = response.json().get("workflow_runs", [])
        if not runs:
            raise Exception(f"No completed runs found for branch '{branch}'")
        
        run = runs[0]
        run_id = run['id']
        
        print(f"✅ Found run #{run['run_number']} (ID: {run_id}, Status: {run['conclusion']})")
        
        # Get jobs for this run
        print(f"📊 Fetching job details...\n")
        jobs_url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        response = requests.get(jobs_url, headers=self.headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch jobs: {response.status_code}")
        
        jobs_data = response.json().get("jobs", [])
        
        # Extract metrics
        metrics = BuildMetrics()
        
        # Calculate workflow duration from run times
        run_started = datetime.fromisoformat(run['run_started_at'].replace('Z', '+00:00'))
        run_updated = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
        metrics.total_duration_seconds = int((run_updated - run_started).total_seconds())
        
        # Process each job
        for job in jobs_data:
            job_name = job['name']
            
            # Calculate job duration
            if job['started_at'] and job['completed_at']:
                started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
                completed = datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00'))
                duration = int((completed - started).total_seconds())
                metrics.job_durations[job_name] = duration
            
            # Process steps
            for step in job['steps']:
                step_name = step['name']
                
                if step['started_at'] and step['completed_at']:
                    started = datetime.fromisoformat(step['started_at'].replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(step['completed_at'].replace('Z', '+00:00'))
                    duration = int((completed - started).total_seconds())
                    
                    full_step_name = f"{job_name}: {step_name}"
                    metrics.step_durations[full_step_name] = duration
                
                # Check for cache in step name
                step_name_lower = step_name.lower()
                if 'cache' in step_name_lower:
                    if step['conclusion'] == 'success':
                        metrics.cache_hits += 1
                    else:
                        metrics.cache_misses += 1
                
                # Track failures
                if step['conclusion'] in ['failure', 'cancelled']:
                    metrics.failed_steps += 1
        
        metrics.parallel_jobs_count = len(metrics.job_durations)
        metrics.total_steps = len(metrics.step_durations)
        
        # Calculate cache efficiency
        if metrics.cache_hits + metrics.cache_misses > 0:
            metrics.cache_efficiency = round(
                (metrics.cache_hits / (metrics.cache_hits + metrics.cache_misses)) * 100, 2
            )
        
        return metrics


def main():
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ Error: GITHUB_TOKEN not set")
        sys.exit(1)
    
    try:
        api = GitHubActionsAPI(token)
        owner, repo = api.parse_repo_url(REPO_URL)
        workflow_file = api.get_workflow_filename(PIPELINE_PATH)
        
        print("="*80)
        print("🚀 BUILD METRICS EXTRACTION")
        print("="*80)
        print(f"Repository:  {owner}/{repo}")
        print(f"Branch:      {BRANCH}")
        print(f"Workflow:    {workflow_file}")
        print("="*80)
        print()
        
        # Fetch metrics
        metrics = api.fetch_metrics(owner, repo, workflow_file, BRANCH)
        
        # Display results
        print("="*80)
        print("📊 EXTRACTED METRICS")
        print("="*80)
        print(json.dumps(asdict(metrics), indent=2))
        print("="*80)
        
        # Formatted summary
        if metrics.total_duration_seconds:
            mins = metrics.total_duration_seconds // 60
            secs = metrics.total_duration_seconds % 60
            print(f"\n⏱️  Total Duration: {mins}m {secs}s")
        
        if metrics.job_durations:
            print(f"\n📊 Job Breakdown:")
            for job, duration in sorted(metrics.job_durations.items(), key=lambda x: x[1], reverse=True):
                mins = duration // 60
                secs = duration % 60
                pct = (duration / metrics.total_duration_seconds * 100) if metrics.total_duration_seconds else 0
                print(f"   {job:15s} {mins:3d}m {secs:2d}s ({pct:5.1f}%)")
        
        if metrics.step_durations:
            print(f"\n⚙️  Top 10 Slowest Steps:")
            sorted_steps = sorted(metrics.step_durations.items(), key=lambda x: x[1], reverse=True)[:10]
            for step, duration in sorted_steps:
                mins = duration // 60
                secs = duration % 60
                print(f"   {step[:55]:55s} {mins:2d}m {secs:2d}s")
        
        if metrics.cache_hits or metrics.cache_misses:
            print(f"\n💾 Cache: {metrics.cache_hits} hits, {metrics.cache_misses} misses ({metrics.cache_efficiency}% efficiency)")
        
        print("\n✅ Complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()