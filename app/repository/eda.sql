-- =====================================================
-- Pipeline Optimiser Insights
-- =====================================================

-- -----------------------
-- 1. Repository-level Insights
-- -----------------------

-- a) List all active repositories and last run time
SELECT r.id, r.repo_url, r.default_branch, r.active,
       MAX(run.end_time) AS last_run_time
FROM repositories r
LEFT JOIN runs run ON r.id = run.repo_id
GROUP BY r.id, r.repo_url, r.default_branch, r.active
ORDER BY last_run_time DESC;


-- b) Count of runs per repository
SELECT r.repo_url, COUNT(run.id) AS total_runs
FROM repositories r
LEFT JOIN runs run ON r.id = run.repo_id
GROUP BY r.repo_url
ORDER BY total_runs DESC;


-- -----------------------
-- 2. Run-level Insights
-- -----------------------

-- a) Run success/failure statistics
SELECT status, COUNT(*) AS count
FROM runs
GROUP BY status;


-- b) Average run duration (seconds)
SELECT AVG(EXTRACT(EPOCH FROM (end_time - start_time))) AS avg_duration_seconds
FROM runs
WHERE status = 'completed';


-- c) Runs triggered by source
SELECT trigger_source, COUNT(*) AS count
FROM runs
GROUP BY trigger_source;


-- -----------------------
-- 3. Artifact Analysis
-- -----------------------

-- a) Count artifacts per stage
SELECT stage, COUNT(*) AS artifact_count
FROM artifacts
GROUP BY stage
ORDER BY artifact_count DESC;


-- b) Artifacts metadata inspection (JSON keys)
SELECT stage, jsonb_object_keys(metadata) AS metadata_keys, COUNT(*) AS count
FROM artifacts
GROUP BY stage, metadata_keys
ORDER BY count DESC;


-- -----------------------
-- 4. Issues Analysis
-- -----------------------

-- a) Count issues by severity
SELECT severity, COUNT(*) AS issue_count
FROM issues
GROUP BY severity
ORDER BY issue_count DESC;


-- b) Issues per repository
SELECT r.repo_url, i.severity, COUNT(i.id) AS issue_count
FROM issues i
JOIN runs run ON i.run_id = run.id
JOIN repositories r ON run.repo_id = r.id
GROUP BY r.repo_url, i.severity
ORDER BY r.repo_url, issue_count DESC;


-- c) Most common issue types
SELECT type, COUNT(*) AS count
FROM issues
GROUP BY type
ORDER BY count DESC
LIMIT 10;


-- -----------------------
-- 5. Pull Request (PR) Analysis
-- -----------------------

-- a) PR creation / merge stats
SELECT status, COUNT(*) AS count
FROM prs
GROUP BY status;


-- b) PRs per repository
SELECT r.repo_url, COUNT(pr.id) AS total_prs,
       SUM(CASE WHEN pr.merged THEN 1 ELSE 0 END) AS merged_prs
FROM prs pr
JOIN runs run ON pr.run_id = run.id
JOIN repositories r ON run.repo_id = r.id
GROUP BY r.repo_url
ORDER BY total_prs DESC;


-- -----------------------
-- 6. Combined Insights
-- -----------------------

-- a) Repositories with most failed runs
SELECT r.repo_url, COUNT(*) AS failed_runs
FROM runs run
JOIN repositories r ON run.repo_id = r.id
WHERE run.status = 'failed'
GROUP BY r.repo_url
ORDER BY failed_runs DESC;


-- b) Average number of issues per run per repository
SELECT r.repo_url, AVG(issue_count) AS avg_issues_per_run
FROM (
    SELECT run.id



Using Historical Data to Improve Workflow
1. Pattern Learning:
python# Query common issues by pipeline type
SELECT 
    workflow_type,
    type,
    description,
    COUNT(*) as frequency
FROM runs r
JOIN issues i ON r.id = i.run_id
WHERE r.workflow_type = 'CD'
GROUP BY workflow_type, type, description
ORDER BY frequency DESC;
2. Predictive Risk Assessment:
python# Learn: repos with certain patterns → high risk
SELECT 
    repo_url,
    AVG(risk_score) as avg_risk,
    COUNT(*) as run_count
FROM runs r
JOIN repositories repo ON r.repo_id = repo.id
JOIN reviews rev ON r.id = rev.run_id
WHERE rev.review_type = 'risk'
GROUP BY repo_url;
3. Critic Confidence Calibration:
python# Compare predicted vs actual merge success
SELECT 
    merge_confidence,
    pr.status,
    pr.merged,
    COUNT(*) as count
FROM runs r
JOIN reviews rev ON r.id = rev.run_id
JOIN prs pr ON r.id = pr.run_id
WHERE rev.review_type = 'critic'
GROUP BY merge_confidence, pr.status, pr.merged;
4. Decision Agent Learning:
python# Which decision patterns lead to successful PRs?
SELECT 
    tool_name,
    action,
    COUNT(*) as total,
    SUM(CASE WHEN pr.merged THEN 1 ELSE 0 END) as merged
FROM decisions d
JOIN runs r ON d.run_id = r.id
JOIN prs pr ON r.id = pr.run_id
GROUP BY tool_name, action;
5. Issue Recurrence Detection:
python# Has this repo/pipeline had this issue before?
SELECT 
    r.pipeline_path,
    i.type,
    i.description,
    COUNT(*) as occurrences,
    MAX(r.start_time) as last_seen
FROM runs r
JOIN issues i ON r.id = i.run_id
WHERE r.repo_id = :repo_id 
  AND r.pipeline_path = :pipeline_path
GROUP BY r.pipeline_path, i.type, i.description
HAVING COUNT(*) > 1;
6. Optimization Success Rate:
sql-- Track: workflow_type + risk_level → PR merge rate
SELECT 
    workflow_type,
    risk_level,
    COUNT(*) as total_runs,
    SUM(CASE WHEN pr.merged THEN 1 ELSE 0 END) as merged,
    AVG(duration_seconds) as avg_duration
FROM runs r
LEFT JOIN prs pr ON r.id = pr.run_id
GROUP BY workflow_type, risk_level;
Complete Updated Schema:
sqlALTER TABLE runs ADD COLUMN pipeline_path TEXT NOT NULL;
ALTER TABLE runs ADD COLUMN branch TEXT DEFAULT 'main';
ALTER TABLE runs ADD COLUMN correlation_id TEXT;
ALTER TABLE runs ADD COLUMN workflow_type TEXT;
ALTER TABLE runs ADD COLUMN risk_level TEXT;
ALTER TABLE runs ADD COLUMN duration_seconds FLOAT;

ALTER TABLE issues ADD COLUMN location TEXT;

CREATE INDEX idx_runs_pipeline ON runs(repo_id, pipeline_path);
CREATE INDEX idx_runs_correlation_id ON runs(correlation_id);
CREATE INDEX idx_runs_workflow ON runs(workflow_type, risk_level);
Future ML Opportunities:

Train models on historical issues → predict risk
Learn which fixes work best for specific issue types
Recommend skipping tools based on past patterns
Auto-adjust critic thresholds per repository
Detect anomalies (new issue types never seen before)
