import yaml
from pathlib import Path
from app.components.fixer import Fixer

# 🔧 Path to your YAML file (adjust as needed)
YAML_PATH = Path("tests/pipelines/pipeline1.yaml")

# Load the YAML content from file
with YAML_PATH.open("r") as f:
    pipeline_yaml = f.read()

# Suggested fixes from analyser
SUGGESTED_FIXES = [
    "Add dependency caching using GitHub Actions cache mechanism for pip dependencies",
    "Configure 'lint' job to run in parallel with 'build' job since it does not depend on the build output",
    "Pin action versions to specific releases (e.g., actions/checkout@v3.0.0, actions/setup-python@v4.0.0)"
]

# Initialise Fixer
fixer = Fixer(model="gpt-4o-mini", temperature=0)

# Apply fixes (actual LLM call)
optimised_yaml = fixer.run(pipeline_yaml, SUGGESTED_FIXES)

# Print output for inspection
print("\n===== Optimised YAML =====\n")
print(optimised_yaml)

# Optional: parse and validate
parsed = yaml.safe_load(optimised_yaml)
assert "on" in parsed, "Top-level 'on' key missing"
assert "jobs" in parsed, "'jobs' section missing"
