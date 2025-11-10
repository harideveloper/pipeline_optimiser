.PHONY: setup run-agent clean test-agent load-env docker-build docker-run docker-push-hub docker-push-gar

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Docker Configuration
IMAGE_NAME := pipeline-optimiser
VERSION ?= 0.0.1
DOCKER_HUB_USERNAME ?= your-dockerhub-username
GCP_PROJECT ?= dev1-bfa7
GAR_REGION ?= europe-west2
GAR_REPO ?= optimiser

setup:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

load-env:
	@export $$(grep -v '^#' .env | xargs)

# App
start:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8091 --reload

optimise:
	PYTHONPATH=. $(PYTHON) -m app.tests.pipeline_test

test-components:
	PYTHONPATH=. $(PYTHON) -m pytest app/components -v

test-evaluation:
	PYTHONPATH=. $(PYTHON) -m pytest app/tests/evaluation -v

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache

# Docker
docker-build:
	docker build -t $(IMAGE_NAME):$(VERSION) .

docker-run:
	docker run --env-file .env-docker -p 8000:8091 $(IMAGE_NAME):$(VERSION)

# Push to Docker Hub
docker-push-hub:
	docker tag $(IMAGE_NAME):$(VERSION) $(DOCKER_HUB_USERNAME)/$(IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME):$(VERSION) $(DOCKER_HUB_USERNAME)/$(IMAGE_NAME):latest
	docker push $(DOCKER_HUB_USERNAME)/$(IMAGE_NAME):$(VERSION)
	docker push $(DOCKER_HUB_USERNAME)/$(IMAGE_NAME):latest
	@echo "Pushed to Docker Hub: $(DOCKER_HUB_USERNAME)/$(IMAGE_NAME):$(VERSION)"

# Push to Google Artifact Registry
docker-push-gar:
	gcloud auth configure-docker $(GAR_REGION)-docker.pkg.dev
	docker tag $(IMAGE_NAME):$(VERSION) $(GAR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GAR_REPO)/$(IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME):$(VERSION) $(GAR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GAR_REPO)/$(IMAGE_NAME):latest
	docker push $(GAR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GAR_REPO)/$(IMAGE_NAME):$(VERSION)
	docker push $(GAR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GAR_REPO)/$(IMAGE_NAME):latest
	@echo "Pushed to GAR: $(GAR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GAR_REPO)/$(IMAGE_NAME):$(VERSION)"