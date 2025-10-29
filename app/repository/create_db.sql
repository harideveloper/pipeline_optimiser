-- =====================================================
-- init_pipeline_db.sql
-- PostgreSQL setup for Pipeline Optimiser
-- Includes table ownership and grants
-- Updated with new fields for reviews, decisions, and tracking
-- =====================================================

-- 1. Create database and user
-- Run as postgres user or a superuser
CREATE USER pipeline_user WITH ENCRYPTED PASSWORD 'pipeline_pass';

-- Create database
CREATE DATABASE pipeline_db OWNER pipeline_user;

-- Grant privileges on database
GRANT ALL PRIVILEGES ON DATABASE pipeline_db TO pipeline_user;

-- Connect to the database
\c pipeline_db

-- =====================================================
-- 2. Drop existing tables (if any)
-- =====================================================
DROP TABLE IF EXISTS prs CASCADE;
DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS issues CASCADE;
DROP TABLE IF EXISTS artifacts CASCADE;
DROP TABLE IF EXISTS runs CASCADE;
DROP TABLE IF EXISTS repositories CASCADE;

-- =====================================================
-- 3. Create Tables
-- =====================================================

-- -----------------------
-- repositories table
-- -----------------------
CREATE TABLE repositories (
    id SERIAL PRIMARY KEY,
    repo_url TEXT UNIQUE NOT NULL,
    default_branch TEXT DEFAULT 'main',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------
-- runs table
-- -----------------------
CREATE TABLE runs (
    id SERIAL PRIMARY KEY,
    repo_id INT REFERENCES repositories(id) ON DELETE CASCADE,
    pipeline_path TEXT NOT NULL,
    branch TEXT DEFAULT 'main',
    commit_sha TEXT,
    correlation_id TEXT,
    trigger_source TEXT,
    workflow_type TEXT,
    risk_level TEXT,
    status TEXT CHECK (status IN ('started', 'completed', 'failed')) DEFAULT 'started',
    duration_seconds FLOAT,
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP
);

-- -----------------------
-- artifacts table
-- -----------------------
CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    stage TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------
-- issues table
-- -----------------------
CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    type TEXT,
    description TEXT,
    severity TEXT CHECK (severity IN ('low', 'medium', 'high')) DEFAULT 'medium',
    location TEXT,
    suggested_fix TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------
-- reviews table (NEW)
-- Stores critic, risk, and security reviews
-- -----------------------
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    review_type TEXT CHECK (review_type IN ('critic', 'risk', 'security')),
    fix_confidence FLOAT,
    merge_confidence FLOAT,
    quality_score INT,
    risk_score FLOAT,
    overall_risk TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------
-- decisions table (NEW)
-- Stores decision agent choices
-- -----------------------
CREATE TABLE decisions (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    tool_name TEXT,
    action TEXT CHECK (action IN ('run', 'skip')),
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -----------------------
-- prs table
-- -----------------------
CREATE TABLE prs (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    branch_name TEXT,
    pr_url TEXT,
    status TEXT CHECK (status IN ('created', 'merged', 'closed')) DEFAULT 'created',
    merged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- 4. Create Indexes for Performance
-- =====================================================
-- CREATE INDEX idx_runs_repo_pipeline ON runs(repo_id, pipeline_path);
-- CREATE INDEX idx_runs_correlation_id ON runs(correlation_id);
-- CREATE INDEX idx_runs_workflow ON runs(workflow_type, risk_level);
-- CREATE INDEX idx_runs_status ON runs(status);
-- CREATE INDEX idx_reviews_run_id ON reviews(run_id);
-- CREATE INDEX idx_reviews_type ON reviews(review_type);
-- CREATE INDEX idx_decisions_run_id ON decisions(run_id);
-- CREATE INDEX idx_issues_run_id ON issues(run_id);
-- CREATE INDEX idx_artifacts_run_id ON artifacts(run_id);
-- CREATE INDEX idx_prs_run_id ON prs(run_id);

-- =====================================================
-- 5. Set ownership and grant privileges
-- =====================================================
ALTER TABLE repositories OWNER TO pipeline_user;
ALTER TABLE runs OWNER TO pipeline_user;
ALTER TABLE artifacts OWNER TO pipeline_user;
ALTER TABLE issues OWNER TO pipeline_user;
ALTER TABLE reviews OWNER TO pipeline_user;
ALTER TABLE decisions OWNER TO pipeline_user;
ALTER TABLE prs OWNER TO pipeline_user;

GRANT ALL PRIVILEGES ON TABLE repositories TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE runs TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE artifacts TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE issues TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE reviews TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE decisions TO pipeline_user;
GRANT ALL PRIVILEGES ON TABLE prs TO pipeline_user;

-- Grant sequence privileges for SERIAL columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pipeline_user;

-- =====================================================
-- 6. Optional: Sample Data for Testing
-- =====================================================
-- INSERT INTO repositories (repo_url) VALUES ('https://github.com/example/repo1');
-- 
-- INSERT INTO runs (repo_id, pipeline_path, correlation_id, workflow_type, risk_level, status) 
-- VALUES (1, '.github/workflows/ci.yml', 'test-123', 'CI', 'LOW', 'completed');
--
-- INSERT INTO issues (run_id, type, description, severity, location) 
-- VALUES (1, 'caching', 'Missing npm cache', 'medium', 'build.steps[2]');
--
-- INSERT INTO reviews (run_id, review_type, fix_confidence, merge_confidence, risk_score, overall_risk) 
-- VALUES (1, 'critic', 0.85, 0.80, 3.5, 'low');

-- =====================================================
-- 7. Helpful Queries for Monitoring
-- =====================================================
-- View recent runs with details
-- SELECT r.id, repo.repo_url, r.pipeline_path, r.workflow_type, r.risk_level, r.status, r.duration_seconds
-- FROM runs r
-- JOIN repositories repo ON r.repo_id = repo.id
-- ORDER BY r.start_time DESC LIMIT 10;

-- View success rate by workflow type
-- SELECT workflow_type, risk_level, 
--        COUNT(*) as total,
--        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
-- FROM runs
-- GROUP BY workflow_type, risk_level;

-- View reviews summary
-- SELECT review_type, 
--        AVG(fix_confidence) as avg_fix_conf,
--        AVG(merge_confidence) as avg_merge_conf,
--        AVG(risk_score) as avg_risk
-- FROM reviews
-- GROUP BY review_type;

-- =====================================================
-- Script Complete
-- =====================================================