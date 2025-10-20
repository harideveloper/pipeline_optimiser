"""
Debug script to test workflow classification
Run this to see exactly what's happening with your YAML
"""

import yaml
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)

# Your simple CI YAML
test_yaml = """
name: Simple CI Tests
on:
  pull_request:
    branches: [main]
  push:
    branches: [dev, feature/*]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: npm ci
      - name: Run tests
        run: npm test
      - name: Run linter
        run: npm run lint
"""

print("=" * 60)
print("YAML PARSING TEST")
print("=" * 60)

# Parse the YAML
workflow = yaml.safe_load(test_yaml)

print(f"\n1. Parsed workflow keys: {list(workflow.keys())}")
print(f"\n2. 'on' key value: {workflow.get('on')}")
print(f"   Type: {type(workflow.get('on'))}")
print(f"\n3. Boolean True key value: {workflow.get(True)}")
print(f"   Type: {type(workflow.get(True))}")

# ✅ USE THE FIX
triggers = workflow.get('on', workflow.get(True, {}))
print(f"\n4. Triggers (using fix): {triggers}")
print(f"   Type: {type(triggers)}")

if isinstance(triggers, dict):
    print(f"\n5. Trigger keys: {list(triggers.keys())}")
    print(f"   'pull_request' in triggers: {'pull_request' in triggers}")
    print(f"   'push' in triggers: {'push' in triggers}")
else:
    print(f"\n5. ERROR: Triggers is not a dict! It's: {type(triggers)}")
    print(f"   Value: {triggers}")

# Check jobs
jobs = workflow.get('jobs', {})
print(f"\n5. Jobs: {list(jobs.keys())}")

for job_name, job in jobs.items():
    print(f"\n6. Job '{job_name}':")
    print(f"   Has 'deploy' in name: {'deploy' in job_name.lower()}")
    print(f"   Has 'release' in name: {'release' in job_name.lower()}")
    print(f"   Has 'environment' key: {'environment' in job}")

print("\n" + "=" * 60)
print("CLASSIFICATION LOGIC TEST")
print("=" * 60)

has_pr = 'pull_request' in triggers if isinstance(triggers, dict) else False
has_push = 'push' in triggers if isinstance(triggers, dict) else False
has_deployment = False  # We know it's False

print(f"\nhas_pr: {has_pr}")
print(f"has_push: {has_push}")
print(f"has_deployment: {has_deployment}")

print("\nChecking conditions:")
print(f"1. has_pr and not has_deployment: {has_pr and not has_deployment}")
print(f"2. has_pr and has_push and not has_deployment: {has_pr and has_push and not has_deployment}")
print(f"3. has_push and not has_deployment: {has_push and not has_deployment}")

if has_pr and not has_deployment:
    print("\n✅ SHOULD BE CLASSIFIED AS: CI (condition 1)")
elif has_pr and has_push and not has_deployment:
    print("\n✅ SHOULD BE CLASSIFIED AS: CI (condition 2)")
elif has_push and not has_deployment:
    print("\n✅ SHOULD BE CLASSIFIED AS: CI (condition 3)")
else:
    print("\n❌ WOULD BE CLASSIFIED AS: UNKNOWN")

print("\n" + "=" * 60)
print("YAML PARSER CHECK")
print("=" * 60)

# Check if YAML parser has any special behavior with 'on' key
print(f"\nChecking if 'on' is a reserved word in PyYAML...")
print(f"workflow.get('on'): {workflow.get('on')}")
print(f"workflow.get('true'): {workflow.get('true')}")  # Sometimes YAML parsers convert 'on' to True

# Check all keys
print(f"\nAll top-level keys in workflow:")
for key in workflow.keys():
    print(f"  - '{key}': {type(workflow[key])}")