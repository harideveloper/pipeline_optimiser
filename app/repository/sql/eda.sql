-- Data Sampling
SELECT * FROM runs LIMIT 10;
SELECT * FROM issues LIMIT 10;
SELECT * FROM reviews LIMIT 10;
SELECT * FROM repositories LIMIT 10;
SELECT * FROM decisions LIMIT 10;
SELECT * FROM prs LIMIT 10;
SELECT * FROM artifacts LIMIT 10;

--- filter runs by run id
SELECT pipeline_path, correlation_id, workflow_type, risk_level, status, duration_seconds
FROM runs WHERE id = 23;

--- filter issues by run id
SELECT 
    type,
    severity,
    description,
    location,
    suggested_fix
FROM issues 
WHERE run_id = 23
ORDER BY severity;

--- filter reviews by run id
SELECT 
    review_type,
    fix_confidence,
    merge_confidence,
    quality_score,
    risk_score,
    overall_risk,
    data
FROM reviews 
WHERE run_id = 23;

--- filter decsions by run id
SELECT 
    run_id,
    tool_name,
    reasoning
FROM decisions 
WHERE run_id = 23;
ORDER BY severity;


-- dashboard summary
SELECT 
    DATE(r.start_time) AS date,
    COUNT(*) AS total_runs,
    COUNT(CASE WHEN r.status = 'completed' THEN 1 END) AS successful_runs,
    COUNT(CASE WHEN r.status = 'failed' THEN 1 END) AS failed_runs,
    COUNT(DISTINCT pr.id) AS prs_created,
    ROUND(AVG(r.duration_seconds)::numeric, 2) AS avg_duration_seconds,
    COUNT(DISTINCT i.id) AS total_issues_found,
    ROUND(AVG(CASE WHEN rev.review_type = 'critic' THEN rev.merge_confidence END)::numeric, 2) AS avg_merge_confidence
FROM runs r
LEFT JOIN issues i ON r.id = i.run_id
LEFT JOIN reviews rev ON r.id = rev.run_id
LEFT JOIN prs pr ON r.id = pr.run_id
GROUP BY DATE(r.start_time)
ORDER BY date DESC
LIMIT 30;

--- Recurring Issue Count
SELECT 
    i.type,
    i.severity,
    i.description,
    COUNT(*) AS occurence_count,
    STRING_AGG(DISTINCT CONCAT(i.run_id), ', ') AS occurence_in_runs
FROM issues i
GROUP BY i.type, i.severity, i.description
ORDER BY occurence_count DESC
LIMIT 15;


-- Common Issues group by pipeline/ runs
SELECT 
    i.type AS issue_type,
    i.description,
    COUNT(*) AS times_seen,
    COUNT(DISTINCT r.pipeline_path) AS pipelines_affected,
    STRING_AGG(DISTINCT r.pipeline_path, ' | ') AS affected_pipelines
FROM issues i
LEFT JOIN runs r ON i.run_id = r.id
GROUP BY i.type, i.description
ORDER BY times_seen DESC
LIMIT 15;

--- Check if same issues persist over time
SELECT 
    r.id AS run_id,
    r.start_time,
    r.pipeline_path,
    COUNT(i.id) AS issues_found,
    STRING_AGG(i.type, ', ') AS issue_types,
    EXISTS(SELECT 1 FROM artifacts WHERE run_id = r.id AND stage = 'optimise') AS has_optimised_yaml,
    EXISTS(SELECT 1 FROM prs WHERE run_id = r.id) AS has_pr
FROM runs r
LEFT JOIN issues i ON r.id = i.run_id
WHERE r.pipeline_path LIKE '%pipeline2%'
GROUP BY r.id, r.start_time, r.pipeline_path
ORDER BY r.start_time;
