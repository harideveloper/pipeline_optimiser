-- =====================================================
-- init_pipeline_db.sql
-- PostgreSQL setup for Pipeline Optimiser
-- =====================================================

-- 1. Create database and user
-- Run as postgres user or a superuser
CREATE USER pipeline_user WITH ENCRYPTED PASSWORD 'pipeline_pass';

-- Create database
CREATE DATABASE pipeline_db OWNER pipeline_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE pipeline_db TO pipeline_user;

-- Connect to the database
\c pipeline_db

-- =====================================================
-- 2. Create Tables
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
    commit_sha TEXT,
    trigger_source TEXT,  -- e.g., "API", "Webhook", "Schedule"
    status TEXT CHECK (status IN ('started', 'completed', 'failed')) DEFAULT 'started',
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP
);

-- -----------------------
-- artifacts table
-- -----------------------
CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES runs(id) ON DELETE CASCADE,
    stage TEXT,  -- e.g., "ingestor", "validator", "analyzer", "fixer", "pr_handler"
    content TEXT,  -- YAML, JSON, or text
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
    suggested_fix TEXT,
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
-- 3. Optional: Test connection
-- =====================================================
-- INSERT INTO repositories (repo_url) VALUES ('https://github.com/example/repo1');

-- =====================================================
-- Script Complete
-- =====================================================
