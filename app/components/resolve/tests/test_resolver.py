import pytest
from unittest.mock import patch, MagicMock

from app.components.resolve.resolver import Resolver, ResolverError

# Fixtures
@pytest.fixture
def resolver():
    # Patch Github before instantiation to avoid real API calls
    with patch("app.components.resolve.resolver.Github") as mock_gh:
        mock_gh.return_value = MagicMock()
        yield Resolver(gh_token="fake_token")


# Tests
def test_init_requires_token():
    """Resolver should raise if no token provided."""
    with patch("app.components.resolve.resolver.config") as mock_config:
        mock_config.GITHUB_TOKEN = None
        from app.components.resolve.resolver import Resolver
        with pytest.raises(ResolverError):
            Resolver()

def test_run_validates_inputs(resolver):
    """Resolver.run should validate required inputs."""
    with pytest.raises(ResolverError):
        resolver.run(repo_url="https://github.com/test/repo", optimised_yaml="", file_path="pipeline.yaml")
    with pytest.raises(ResolverError):
        resolver.run(repo_url="https://github.com/test/repo", optimised_yaml="valid_yaml", file_path="")

def test_extract_repo_name(resolver):
    """Extract repo name correctly."""
    url = "https://github.com/owner/repo.git"
    assert resolver._extract_repo_name(url) == "owner/repo"

    url_no_git = "https://github.com/owner/repo"
    assert resolver._extract_repo_name(url_no_git) == "owner/repo"

    with pytest.raises(ResolverError):
        resolver._extract_repo_name("invalid_url")

def test_build_pr_body_includes_sections(resolver):
    """Ensure PR body contains expected sections."""
    body = resolver._build_pr_body(
        file_path="pipeline.yaml",
        correlation_id="cid",
        analysis_result={"issues_detected": [{"description": "issue"}], "suggested_fixes": ["fix"], "expected_improvement": "better"},
        risk_assessment={"risk_score": 5, "overall_risk": "medium", "safe_to_auto_merge": True},
        critic_review={"fix_confidence": 0.9, "merge_confidence": 0.8, "quality_score": 9}
    )
    # Basic checks for presence of key sections
    assert "## Optimiser Summary" in body
    assert "## Critic Review" in body
    assert "## Risk Assessment" in body
    assert "pipeline.yaml" in body
    assert "Correlation ID: `cid`" in body

def test_execute_creates_pr():
    """_execute should create PR and set pr_url in state."""
    with patch("app.components.resolve.resolver.Github") as mock_gh:
        # Mock repo and PR creation
        mock_repo = MagicMock()
        mock_gh.return_value.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value.totalCount = 0
        mock_repo.create_pull.return_value.html_url = "http://fake.pr.url"

        resolver = Resolver(gh_token="fake_token")

        state = {
            "repo_url": "https://github.com/test/repo",
            "optimised_yaml": "pipeline: fixed",
            "pipeline_path": "pipeline.yaml",
            "pr_create": True,
            "run_id": "r1",
            "correlation_id": "cid"
        }

        updated_state = resolver._execute(state)
        assert updated_state.get("pr_url") == "http://fake.pr.url"
