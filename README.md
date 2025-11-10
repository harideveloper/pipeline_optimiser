# 🚀 Pipeline Optimiser

<div align="center">

**An AI-powered CI/CD pipeline optimisation system that automatically analyses GitHub Actions workflows, identifies performance bottlenecks, and generates optimised configurations.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 14+](https://img.shields.io/badge/postgresql-14+-blue.svg)](https://www.postgresql.org/)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Database Design](#-database-design)
- [Setup](#-setup)
- [Design Patterns](#-design-patterns)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## 🎯 Overview

Pipeline Optimiser uses Claude AI to intelligently analyse your CI/CD pipelines and suggest improvements for:

- 📦 **Missing dependency caching** (npm, pip, Maven, Docker layers)
- ⚡ **Parallelisation opportunities** (removing unnecessary job dependencies)
- 🔄 **Redundant steps** and inefficient configurations
- 🔒 **Security vulnerabilities**

The system follows a multi-agent architecture where specialised agents collaborate to analyse, optimise, review, and optionally create pull requests with fixes.

---

## 🏗️ Architecture

### 📐 Detailed Design

<div align="center">
<img alt="Detailed Architecture Design" src="https://github.com/user-attachments/assets/3c816b33-1d59-4a17-b794-db4b41605980" />
</div>

---
### ☁️ Hosting Design

<div align="center">
<img alt="Hosting Architecture Design" src="https://github.com/user-attachments/assets/06874466-4df2-44ef-8417-8160a538fb26" />
</div>

### 🧩 Core Components

#### **Agents/Tools:**

- **🔍 Ingestor** - Fetches pipeline YAML and build logs from GitHub
- **🏷️ Classifier** - Determines workflow type (CI/CD/Both) and risk level (LOW/MEDIUM/HIGH)
- **🧭 Decision** - LLM based routing, decides which agents to run based on context
- **✅ Validator** - Validates pipeline syntax and structure (Mode = input/output for pre and post validation)
- **⚙️ Optimiser** - Two-stage analysis and LLM based optimisation
- **🎭 Critic** - Reviews proposed changes for safety and quality
- **⚠️ Risk Assessment** - Scores the risk of applying changes
- **🔒 Security Scanner** - Detects security issues in pipelines
- **🔧 Resolver** - Creates GitHub pull requests with optimised YAML

#### **📝 Plan & Execution Logic:**

The Classifier classifies the pipeline based on the risk profile and generates an execution plan:

| Risk Profile | Execution Flow |
|--------------|----------------|
| **High** | Validate → Optimise → Post Validate → Critic → Risk Assess → Security Scan → Resolve |
| **Medium** | Validate → Optimise → Post Validate → Critic → Security Scan → Resolve |
| **Low** | Validate → Optimise → Post Validate → Critic → Resolve |

#### **🎯 Decision Logic:**

- ✓ Validation must pass before optimisation
- ✓ Critic only runs if optimised YAML exists
- ✓ Risk assessment skipped for LOW risk workflows
- ✓ PR creation requires critic confidence >= 0.5

---

## 🗄️ Database Design

### Schema Overview

#### **Core Tables:**

- **`repositories`** - Repository metadata and tracking
- **`runs`** - Optimisation execution records with correlation IDs
- **`issues`** - Detected pipeline problems (type, severity, location, fix)
- **`decisions`** - Agent execution decisions (which tools ran and why)
- **`reviews`** - Critic, risk, and security assessment results
- **`artifacts`** - Generated YAML and intermediate analysis data
- **`prs`** - Pull request tracking (URL, status, merge state)

#### **Relationships:**

```
repositories (1) ──> (N) runs
runs (1) ──> (N) issues
runs (1) ──> (N) decisions
runs (1) ──> (N) reviews
runs (1) ──> (N) artifacts
runs (1) ──> (1) prs
```

> 📄 **See** `app/repository/sql/create.sql` for complete schema definition.

---

## 🛠️ Setup

### Prerequisites

- 🐍 Python 3.11+
- 🐘 PostgreSQL 14+
- 🤖 Anthropic API key
- 🔑 GitHub Personal Access Token
- 🛠️ Make

### Installation

#### **1. Clone and configure:**

```bash
git clone https://github.com/yourusername/pipeline-optimiser.git
cd pipeline-optimiser
cp .env-example .env
# Edit .env with your API keys
```

#### **2. Setup everything using Make:**

```bash
# Install dependencies and setup database
make setup

# Start the API server
make run

# Run unit tests
make test-all
make test-components

# Run sample tests (actual llm call)
# Edit the app/tests/pipeline_test.py with your test repo, pipeline_path
# Run the below make command to test few sample requests making actual llm call
make optimise
```

---

## 🧩 Design Patterns

This section outlines the core software design patterns implemented in the **Pipeline Optimiser**, ensuring scalability, maintainability, and clean separation of concerns.

---

### ⚙️ Application Design Patterns

#### 🗂️ Repository Pattern

All database operations are abstracted through the `PipelineRepository` class.

This separates **business logic** from **data persistence**, making testing easier and allowing database layer changes without impacting the application logic.

> **✨ Benefit:** Enables a clean separation of concerns and flexible database implementations.

---

#### 🔁 Singleton Pattern

The database connection pool is implemented as a **singleton**, ensuring all components reuse the same connection instance.

This prevents connection exhaustion and optimizes resource management.

> **✨ Benefit:** Efficient connection reuse with centralized and controlled resource management.

---

#### 🎭 Facade Pattern

The `LLMClient` serves as a **facade** for the Anthropic API, providing a simplified interface that hides low-level complexity.

This centralizes error handling and makes it easy to switch between LLM providers.

> **✨ Benefit:** Simplified API usage with centralized error handling and flexible provider integration.

---

#### 🧱 Template Pattern

The `BaseService` class defines a **common execution flow**—including logging, validation, and error handling—while subclasses implement their specific `_execute()` logic.

This ensures consistency across all agent services.

> **✨ Benefit:** Consistent execution flow with reusable logging and error handling.

---

#### 🧩 Dependency Injection

Dependencies (e.g., `LLMClient`, `PipelineRepository`) are injected through constructors, enabling components to operate independently of specific implementations.

This improves testability and supports flexible configuration.

> **✨ Benefit:** Loose coupling and easy unit testing using mocks or alternate implementations.

---

#### 👁️ Observer Pattern

A **correlation ID** is propagated through all components, ensuring each log entry and database operation can be traced back to the original request.

This enables distributed tracing and full visibility across the pipeline.

> **✨ Benefit:** End-to-end traceability for debugging, auditing, and monitoring.

---

### 🤖 Agent Design Patterns

#### 🧭 Plan–Execute Pattern

The agent pipeline follows a sequential **plan–execute flow**, where each stage processes input and passes results downstream:

`Ingestor → Classifier → Decision → Validator → Optimiser → Critic → Resolver`

The **Decision Agent** dynamically routes requests based on contextual rules.

> **✨ Benefit:** Flexible, loosely coupled agent interactions with dynamic routing.

---

#### ⚖️ Two-Phase Commit Pattern

The Optimiser runs in two distinct stages:

1. **Analysis Phase** – Identifies issues and determines required changes.
2. **Execution Phase** – Applies the fixes safely and reliably.

This structure supports rollback and improves reliability.

> **✨ Benefit:** Safe, reversible changes with clear separation of analysis and execution.

---

#### 🧠 Critic Pattern

The **Critic Agent** reviews all Optimiser-generated YAML configurations for safety, quality, and correctness before they are merged.

It acts as a **quality gate**, assigning confidence scores and blocking unsafe updates.

> **✨ Benefit:** Ensures output integrity, prevents unsafe changes, and supports automated decision-making.

---

## 📄 License

This project is licensed under the MIT License - see LICENSE for details.

---

## 🙏 Acknowledgments

**Questions or Issues?** Open an issue on GitHub.

---

<div align="center">
</div>
