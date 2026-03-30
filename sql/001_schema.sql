-- SAIA V4 Database Schema

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Users Table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL,
  data_scope TEXT[] DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT role_valid CHECK (role IN ('admin', 'analyst', 'viewer'))
);

-- Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(50) NOT NULL,
  resource VARCHAR(255) NOT NULL,
  details JSONB,
  ip_address INET,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enable RLS on audit_log
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_log_insert_policy ON audit_log
  FOR INSERT WITH CHECK (true);

-- Action Privilege Levels Table
CREATE TABLE IF NOT EXISTS action_privilege_levels (
  action VARCHAR(100) PRIMARY KEY,
  privilege_level INTEGER NOT NULL,
  CONSTRAINT privilege_level_valid CHECK (privilege_level >= 1 AND privilege_level <= 5)
);

-- Asset Registry Table
CREATE TABLE IF NOT EXISTS asset_registry (
  asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  asset_name VARCHAR(255) NOT NULL,
  criticality_score INTEGER NOT NULL,
  is_sensitive BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT criticality_valid CHECK (criticality_score >= 1 AND criticality_score <= 5)
);

-- Log Events Table
CREATE TABLE IF NOT EXISTS log_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  upload_id UUID,
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
  source VARCHAR(255),
  event_type VARCHAR(100) NOT NULL,
  principal VARCHAR(255) NOT NULL,
  action VARCHAR(255) NOT NULL,
  resource VARCHAR(500),
  result VARCHAR(50),
  source_ip INET,
  asset_id UUID REFERENCES asset_registry(asset_id) ON DELETE SET NULL,
  domain VARCHAR(100),
  raw_log JSONB,
  quality_score FLOAT DEFAULT 0.0,
  is_quarantined BOOLEAN DEFAULT false,
  anomaly_score FLOAT DEFAULT 0.0,
  is_flagged BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  search_vector TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('english', COALESCE(principal, '') || ' ' ||
                           COALESCE(action, '') || ' ' ||
                           COALESCE(resource, ''))
  ) STORED
);

-- Entity Baselines Table
CREATE TABLE IF NOT EXISTS entity_baselines (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  principal VARCHAR(255) NOT NULL,
  domain VARCHAR(100) NOT NULL,
  hourly_medians JSONB,
  daily_medians JSONB,
  behavioral_medians JSONB,
  known_patterns TEXT[],
  risk_score FLOAT DEFAULT 0.0,
  sample_count INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(principal, domain)
);

-- Rules Table
CREATE TABLE IF NOT EXISTS rules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  domain VARCHAR(100) NOT NULL,
  clause_reference VARCHAR(255),
  severity VARCHAR(50) NOT NULL,
  conditions JSONB NOT NULL,
  is_active BOOLEAN DEFAULT true,
  version INTEGER DEFAULT 1,
  author_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT severity_valid CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info'))
);

-- Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  alert_number VARCHAR(50) UNIQUE NOT NULL,
  domain VARCHAR(100) NOT NULL,
  severity VARCHAR(50) NOT NULL,
  status VARCHAR(50) NOT NULL,
  source VARCHAR(100) NOT NULL,
  entity_principal VARCHAR(255),
  clause_reference VARCHAR(255),
  anomaly_score FLOAT,
  top_features JSONB,
  baseline_deviations JSONB,
  triggered_rule_ids UUID[],
  event_ids UUID[],
  llm_assessment JSONB,
  assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
  case_id UUID,
  analyst_verdict VARCHAR(50),
  analyst_comment TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT severity_valid CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  CONSTRAINT status_valid CHECK (status IN ('open', 'acknowledged', 'investigating', 'resolved', 'false_positive', 'closed')),
  CONSTRAINT source_valid CHECK (source IN ('rule', 'anomaly', 'manual', 'integrated')),
  CONSTRAINT verdict_valid CHECK (analyst_verdict IS NULL OR analyst_verdict IN ('true_positive', 'false_positive', 'benign', 'escalate'))
);

-- Cases Table
CREATE TABLE IF NOT EXISTS cases (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  case_number VARCHAR(50) UNIQUE NOT NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  status VARCHAR(50) NOT NULL,
  severity VARCHAR(50),
  assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
  narrative_draft TEXT,
  narrative_approved TEXT,
  narrative_approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  narrative_approved_at TIMESTAMP WITH TIME ZONE,
  narrative_status VARCHAR(50),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT status_valid CHECK (status IN ('open', 'in_progress', 'pending_review', 'closed', 'archived')),
  CONSTRAINT narrative_status_valid CHECK (narrative_status IS NULL OR narrative_status IN ('draft', 'pending_review', 'approved', 'rejected'))
);

-- LLM Queue Table
CREATE TABLE IF NOT EXISTS llm_queue (
  id BIGSERIAL PRIMARY KEY,
  alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
  priority INTEGER DEFAULT 0,
  status VARCHAR(50) NOT NULL,
  attempts INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'retrying'))
);

-- Chat Sessions Table
CREATE TABLE IF NOT EXISTS chat_sessions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Chat History Table
CREATE TABLE IF NOT EXISTS chat_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(50) NOT NULL,
  content TEXT NOT NULL,
  sources JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT role_valid CHECK (role IN ('user', 'assistant', 'system'))
);

-- Control Signal Matrix Table
CREATE TABLE IF NOT EXISTS control_signal_matrix (
  id SERIAL PRIMARY KEY,
  matrix_id VARCHAR(255) UNIQUE NOT NULL,
  domain VARCHAR(100) NOT NULL,
  anomaly_pattern JSONB NOT NULL,
  primary_clause VARCHAR(255),
  secondary_clauses TEXT[],
  severity_guidance VARCHAR(255),
  explanation_template TEXT
);

-- Uploads Table
CREATE TABLE IF NOT EXISTS uploads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  source_name VARCHAR(255) NOT NULL,
  domain VARCHAR(100),
  filename VARCHAR(255) NOT NULL,
  events_parsed INTEGER DEFAULT 0,
  events_accepted INTEGER DEFAULT 0,
  events_quarantined INTEGER DEFAULT 0,
  status VARCHAR(50) DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
