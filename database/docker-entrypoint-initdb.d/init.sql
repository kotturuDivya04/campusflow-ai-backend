-- CampusFlow AI - Database Initialization Orchestration
-- This file runs first alphabetically: init.sql -> schema.sql -> seed.sql

SELECT 'Initializing CampusFlow AI Database...' AS progress_message;

-- Enable standard enterprise extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist"; -- Optional, useful for advanced range checks if needed in the future

-- Perform any initial administrative configuration if required
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET work_mem = '16MB';

SELECT 'Extensions and performance variables initialized. Moving to Schema execution...' AS progress_message;
