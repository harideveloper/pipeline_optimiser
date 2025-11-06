import pytest
from unittest.mock import patch
from app.components.ingest.ingestor import Ingestor
from app.exceptions import IngestionError


@pytest.fixture
def ingestor():
    return Ingestor()


def test_run_success(monkeypatch, ingestor):
    """Should clone repo and return pipeline + log."""
    monkeypatch.setattr(ingestor, "_clone_and_load_pipeline", lambda *a, **k: "yaml")
    monkeypatch.setattr(ingestor, "_load_build_log", lambda *a, **k: "log")

    result = ingestor.run("https://repo", "pipeline.yaml")
    assert result == ("yaml", "log")


def test_run_invalid_inputs_raise_error(ingestor):
    """Invalid inputs should raise IngestionError."""
    with pytest.raises(IngestionError):
        ingestor.run("", "p.yaml")
    with pytest.raises(IngestionError):
        ingestor.run("https://repo", "")


@patch("app.components.ingest.ingestor.subprocess.run")
def test_clone_and_load_pipeline_handles_git_and_file(mock_run, tmp_path, ingestor):
    """Covers clone success and missing file errors."""
    # successful clone but missing file
    mock_run.return_value.returncode = 0
    with pytest.raises(FileNotFoundError):
        ingestor._clone_and_load_pipeline("https://repo", "main", str(tmp_path), "missing.yaml")

    # git failure
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "fatal: not found"
    with pytest.raises(RuntimeError):
        ingestor._clone_and_load_pipeline("https://repo", "main", str(tmp_path), "p.yaml")


@patch.object(Ingestor, "run", side_effect=IngestionError("fail"))
def test_execute_handles_failure(mock_run, ingestor):
    """Should handle ingestion error gracefully."""
    state = {"repo_url": "u", "pipeline_path": "p"}
    result = ingestor._execute(state)
    assert "error" in result
    assert "Ingestion failed" in result["error"]


def test_sanitise_url_masks_credentials(ingestor):
    """Should remove credentials from URL."""
    url = "https://user:token@github.com/org/repo.git"
    out = ingestor._sanitise_url(url)
    assert "***@" in out and "user" not in out
