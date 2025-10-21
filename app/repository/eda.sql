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
