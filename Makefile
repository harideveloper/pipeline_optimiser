.PHONY: setup run-agent clean

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# setup
setup:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	pip install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

load-env:
	export $(grep -v '^#' .env | xargs)

run-agent:
# 	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8091
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8091 --reload

test-agent:
	PYTHONPATH=. $(PYTHON) -m tests.test_agent

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache


## db create
# psql -h localhost -p 5432 -U postgres -f app/repository/db.sql

# docker build 
# docker build -t pipeline-optimiser:0.0.1 .

# docker start container 
# docker run --env-file .env-docker -p 8000:8000 pipeline-optimiser:0.0.1
# docker run --env-file .env-docker -p 8000:8091 pipeline-optimiser:0.0.1