-- Ensure uuid-ossp extension is enabled for uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables to recreate cleanly
DROP TABLE IF EXISTS ingestion_logs CASCADE;
DROP TABLE IF EXISTS opportunities CASCADE;
DROP TABLE IF EXISTS user_schedules CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;

-- user_profiles table
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) UNIQUE NOT NULL DEFAULT 'default_user',
    -- Legacy / Deprecated Columns
    goals TEXT,
    preferred_stipend_min INTEGER,
    learning_focus TEXT,
    resume_text TEXT,
    target_locations TEXT,
    tech_stack TEXT,
    active_commitments TEXT,
    
    -- V2 Columns
    raw_resume_text TEXT,
    form_preferences JSONB,
    ai_filter_directive TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- user_schedules table
CREATE TABLE user_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    event_name VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- opportunities table
CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    description TEXT,
    source_url TEXT,
    apply_url TEXT,
    match_score INTEGER,
    schedule_conflict BOOLEAN,
    schedule_conflict_reason TEXT,
    legitimacy_score INTEGER,
    pros JSONB,
    cons JSONB,
    raw_text TEXT NOT NULL,
    source_name VARCHAR(255),
    source_tier VARCHAR(50) CHECK (source_tier IN ('TIER_1_TRUSTED', 'TIER_2_GENERIC')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Phase 3.7: Sources Management
CREATE TABLE public.sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    url_or_identifier TEXT NOT NULL,
    source_type VARCHAR(50) CHECK (source_type IN ('WEB', 'TELEGRAM')),
    source_tier VARCHAR(50) CHECK (source_tier IN ('TIER_1_TRUSTED', 'TIER_2_GENERIC')),
    css_selector VARCHAR DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ingestion_logs table
CREATE TABLE ingestion_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
