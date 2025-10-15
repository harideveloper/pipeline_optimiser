.PHONY: setup run-agent clean

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Setup environment (create venv + install dependencies)
setup:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	pip install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

# # # Run the pipeline optimizer agent
# run-agent:
# 	PYTHONPATH=. $(PYTHON) -m app.main 

run-agent:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8091 --reload



test-agent:
	PYTHONPATH=. $(PYTHON) -m tests.test_agent


# Clean environment
clean:
	rm -rf $(VENV) __pycache__ .pytest_cache
