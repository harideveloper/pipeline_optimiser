# Pipeline Optimiser

An AI-powered CI/CD pipeline optimisation system that automatically analyses GitHub Actions workflows, identifies performance bottlenecks, and generates optimised configurations.

## Overview

Pipeline Optimiser uses Claude AI to intelligently analyse your CI/CD pipelines and suggest improvements for:
- Missing dependency caching (npm, pip, Maven, Docker layers)
- Parallelisation opportunities (removing unnecessary job dependencies)
- Redundant steps and inefficient configurations
- Security vulnerabilities

The system follows a multi-agent architecture where specialised agents collaborate to analyse, optimise, review, and optionally create pull requests with fixes.

## Architecture

### Agent Pipeline
     TBU 

### Core Components

**Agents:**
- **Ingestor**: Fetches pipeline YAML and build logs from GitHub
- **Classifier**: Determines workflow type (CI/CD/Both) and risk level (LOW/MEDIUM/HIGH)
- **Decision**: Intelligent routing - decides which agents to run based on context
- **Validator**: Validates pipeline syntax and structure (Mode =input/output for pre and post validation)
- **Optimiser**: Two-stage analysis and LLM bases optimisation
- **Critic**: Reviews proposed changes for safety and quality
- **Risk Assessment**: Scores the risk of applying changes
- **Security Scanner**: Detects security issues in pipelines
- **Resolver**: Creates GitHub pull requests with optimised YAML

**Decision Logic:**
- Validation must pass before optimisation
- Critic only runs if optimised YAML exists
- Risk assessment skipped for LOW risk workflows
- PR creation requires critic confidence >= 0.5

## Database Design

### Schema Overview

**Core Tables:**
- `repositories`: Repository metadata and tracking
- `runs`: Optimisation execution records with correlation IDs
- `issues`: Detected pipeline problems (type, severity, location, fix)
- `decisions`: Agent execution decisions (which tools ran and why)
- `reviews`: Critic, risk, and security assessment results
- `artifacts`: Generated YAML and intermediate analysis data
- `prs`: Pull request tracking (URL, status, merge state)

**Relationships:**
```
repositories (1) ──> (N) runs
runs (1) ──> (N) issues
runs (1) ──> (N) decisions
runs (1) ──> (N) reviews
runs (1) ──> (N) artifacts
runs (1) ──> (1) prs
```

See `app/repository/sql/create.sql` for complete schema definition.

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Anthropic API key
- GitHub Personal Access Token
- Make

### Installation

1. **Clone and configure:**
```bash
git clone https://github.com/yourusername/pipeline-optimiser.git
cd pipeline-optimiser
cp .env-example .env
# Edit .env with your API keys
```

2. **Setup everything using Make:**
```bash
# Install dependencies and setup database
make setup

# Start the API server
make run

# Run unit tests
make test-all
make test-components

# Run sample tests (actual llm call)
# Edit the app/tests/pipeline_test.py with your test repo, pipeline_path, run the below make command to test few sample request making actual llm call
make optimise
```

## Design Patterns

### Application Design Patterns

#### Repository Pattern
Database operations abstracted through `PipelineRepository` class, separating business logic from data persistence. Makes testing easier and allows database changes without affecting agents.

**Benefit:** Clean separation of concerns and database implementation can change without affecting business logic.

#### Singleton Pattern
Database connection pool implemented as singleton to reuse connections efficiently and prevent connection exhaustion.

**Benefit:** Efficient connection reuse and prevents resource exhaustion with centralized pool management.

#### Facade Pattern
`LLMClient` provides simplified interface to Anthropic API, hiding complexity and centralising error handling. Makes it easy to swap LLM providers.

**Benefit:** Simple interface for agents with centralized error handling and easy provider switching.

#### Template Pattern
`BaseService` base class defines common execution flow (logging, error handling), while subclasses implement specific `_execute()` logic. Ensures consistent behavior across agents.

**Benefit:** Consistent execution flow and reusable logging/error handling across all agents.

#### Dependency Injection
Services receive dependencies (LLMClient, Repository) through constructor injection, enabling loose coupling and easy testing with mocks.

**Benefit:** Loose coupling enables easy testing with mocks and configurable behavior.

#### Observer Pattern
Correlation IDs propagate through all components for distributed tracing. Every log and database operation includes correlation_id for end-to-end request tracking.

**Benefit:** End-to-end request tracking across all components for easier debugging and audit trails.


### Agent Design Patterns

#### Plan/Execute Pattern
Agent pipeline where each component processes the request and passes to the next. Decision agent dynamically routes based on context (`Ingestor → Classifier → Decision → Validator → Optimiser → Critic → Resolver`).

**Benefit:** Loose coupling between agents with dynamic execution flow based on rules.

#### Two-Phase Commit
Optimiser uses two stages: Analysis phase (identify issues) followed by Execution phase (apply fixes). Enables better error handling and rollback capabilities.

**Benefit:** Clear separation between analysis and modification with better error handling and rollback support.

#### Critic Pattern
Critic agent reviews Optimiser's generated YAML for safety, quality, and correctness before allowing PR creation. Acts as a quality gate with confidence scoring.

**Benefit:** Prevents unsafe changes from being applied and provides confidence scoring for automated decision-making.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

**Questions or Issues?** Open an issue on GitHub.