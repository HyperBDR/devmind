-- Note: This script runs AFTER PostgreSQL Docker image creates the superuser
-- The superuser is created by POSTGRES_USER and POSTGRES_PASSWORD environment variables
-- This script only handles additional database setup if needed

-- Create database if not exists (if POSTGRES_DB doesn't match what we need)
-- PostgreSQL doesn't support CREATE DATABASE IF NOT EXISTS directly
-- So we use a DO block to check and create
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'devmind') THEN
        CREATE DATABASE devmind;
    END IF;
END
$$;

-- Grant privileges on database to the superuser (created by POSTGRES_USER)
-- The superuser already has all privileges, but we ensure it explicitly
-- This is useful if POSTGRES_USER is different from 'postgres'
DO $$
DECLARE
    superuser_name TEXT := current_user;
BEGIN
    -- Grant all privileges on the database to the superuser
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE devmind TO %I', superuser_name);
END
$$;

