# Pipeline Optimiser

## Overview

The Pipeline Optimiser automates CI/CD pipeline improvements by ingesting pipeline YAMLs, validating them, analyzing for inefficiencies, applying fixes, and optionally raising pull requests. All stages log artifacts and results in a PostgreSQL database to support historical tracking, caching, and quality improvements.

---

## 1. High-Level Flow

## Flow Diagram

HTTP Request → Orchestrator
     │
     ├─> DB: repositories (get_or_create_repo)
     ├─> DB: runs (insert_run)
     │
     ├─> IngestorAgent → artifacts(stage='ingestor')
     ├─> ValidatorAgent → artifacts(stage='validator')
     ├─> AnalyserAgent → artifacts(stage='analyzer') + issues
     ├─> FixerAgent → artifacts(stage='fixer')
     ├─> PRHandlerAgent → artifacts(stage='pr_handler') + prs
     │
     └─> Orchestrator → runs (update_run_status)



- Each agent performs its task and writes relevant outputs to the database.  
- Historical runs are stored for auditing, caching, and ML/LLM-based quality improvements.  

---

##  Database Design

We store data across **5 core tables**:

| Table        | Purpose                                         | Key Fields |
|-------------|-------------------------------------------------|------------|
| repositories | Metadata about connected repos               | id, repo_url, default_branch, active |
| runs        | One end-to-end optimisation run               | id, repo_id, start_time, end_time, status, trigger_source, commit_sha |
| artifacts   | Inputs & outputs from each stage (YAMLs, logs, analysis, fixes) | id, run_id, stage, content, metadata (JSONB) |
| issues      | Issues found during analysis                  | id, run_id, type, description, severity, suggested_fix |
| prs         | Info about PRs created                        | id, run_id, branch_name, pr_url, status, merged |

---

### Table Details

**repositories**
```sql
id SERIAL PRIMARY KEY
repo_url TEXT UNIQUE NOT NULL
default_branch TEXT DEFAULT 'main'
active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP DEFAULT NOW()
updated_at TIMESTAMP DEFAULT NOW()
```


**runs**
```sql
id SERIAL PRIMARY KEY
repo_id INT REFERENCES repositories(id)
commit_sha TEXT
trigger_source TEXT  -- e.g. "API", "Webhook", "Schedule"
status TEXT CHECK (status IN ('started', 'completed', 'failed'))
start_time TIMESTAMP DEFAULT NOW()
end_time TIMESTAMP
```

**artifacts**
```sql
id SERIAL PRIMARY KEY
run_id INT REFERENCES runs(id)
stage TEXT  -- e.g. "ingestor", "validator", "analyzer", "fixer", "pr_handler"
content TEXT  -- YAML, JSON, or text
metadata JSONB
created_at TIMESTAMP DEFAULT NOW()


```
**issues**
```sql
id SERIAL PRIMARY KEY
run_id INT REFERENCES runs(id)
type TEXT
description TEXT
severity TEXT CHECK (severity IN ('low', 'medium', 'high'))
suggested_fix TEXT
created_at TIMESTAMP DEFAULT NOW()


```

**prs**
```sql
id SERIAL PRIMARY KEY
run_id INT REFERENCES runs(id)
branch_name TEXT
pr_url TEXT
status TEXT CHECK (status IN ('created', 'merged', 'closed'))
merged BOOLEAN DEFAULT FALSE
created_at TIMESTAMP DEFAULT NOW()

```