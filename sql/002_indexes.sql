-- SAIA V4 Database Indexes

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Audit Log indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_action ON audit_log(user_id, action);

-- Asset Registry indexes
CREATE INDEX IF NOT EXISTS idx_asset_registry_asset_name ON asset_registry(asset_name);
CREATE INDEX IF NOT EXISTS idx_asset_registry_criticality ON asset_registry(criticality_score);
CREATE INDEX IF NOT EXISTS idx_asset_registry_is_sensitive ON asset_registry(is_sensitive);

-- Log Events indexes
CREATE INDEX IF NOT EXISTS idx_log_events_timestamp ON log_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_log_events_principal ON log_events(principal);
CREATE INDEX IF NOT EXISTS idx_log_events_domain ON log_events(domain);
CREATE INDEX IF NOT EXISTS idx_log_events_upload_id ON log_events(upload_id);
CREATE INDEX IF NOT EXISTS idx_log_events_asset_id ON log_events(asset_id);
CREATE INDEX IF NOT EXISTS idx_log_events_is_quarantined ON log_events(is_quarantined);
CREATE INDEX IF NOT EXISTS idx_log_events_is_flagged ON log_events(is_flagged);
CREATE INDEX IF NOT EXISTS idx_log_events_event_type ON log_events(event_type);
CREATE INDEX IF NOT EXISTS idx_log_events_source_ip ON log_events(source_ip);
CREATE INDEX IF NOT EXISTS idx_log_events_search ON log_events USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_log_events_principal_domain_ts ON log_events(principal, domain, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_log_events_raw_log ON log_events USING GIN(raw_log);

-- Entity Baselines indexes
CREATE INDEX IF NOT EXISTS idx_entity_baselines_principal ON entity_baselines(principal);
CREATE INDEX IF NOT EXISTS idx_entity_baselines_domain ON entity_baselines(domain);
CREATE INDEX IF NOT EXISTS idx_entity_baselines_principal_domain ON entity_baselines(principal, domain);
CREATE INDEX IF NOT EXISTS idx_entity_baselines_risk_score ON entity_baselines(risk_score);

-- Rules indexes
CREATE INDEX IF NOT EXISTS idx_rules_name ON rules(name);
CREATE INDEX IF NOT EXISTS idx_rules_domain ON rules(domain);
CREATE INDEX IF NOT EXISTS idx_rules_is_active ON rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rules_severity ON rules(severity);
CREATE INDEX IF NOT EXISTS idx_rules_author_id ON rules(author_id);
CREATE INDEX IF NOT EXISTS idx_rules_clause_reference ON rules(clause_reference);
CREATE INDEX IF NOT EXISTS idx_rules_conditions ON rules USING GIN(conditions);

-- Alerts indexes
CREATE INDEX IF NOT EXISTS idx_alerts_alert_number ON alerts(alert_number);
CREATE INDEX IF NOT EXISTS idx_alerts_domain ON alerts(domain);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_entity_principal ON alerts(entity_principal);
CREATE INDEX IF NOT EXISTS idx_alerts_assigned_to ON alerts(assigned_to);
CREATE INDEX IF NOT EXISTS idx_alerts_case_id ON alerts(case_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_clause_reference ON alerts(clause_reference);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered_rule_ids ON alerts USING GIN(triggered_rule_ids);
CREATE INDEX IF NOT EXISTS idx_alerts_event_ids ON alerts USING GIN(event_ids);
CREATE INDEX IF NOT EXISTS idx_alerts_llm_assessment ON alerts USING GIN(llm_assessment);
CREATE INDEX IF NOT EXISTS idx_alerts_top_features ON alerts USING GIN(top_features);
CREATE INDEX IF NOT EXISTS idx_alerts_baseline_deviations ON alerts USING GIN(baseline_deviations);
CREATE INDEX IF NOT EXISTS idx_alerts_domain_status_severity ON alerts(domain, status, severity);

-- Cases indexes
CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_severity ON cases(severity);
CREATE INDEX IF NOT EXISTS idx_cases_assigned_to ON cases(assigned_to);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_narrative_approved_by ON cases(narrative_approved_by);
CREATE INDEX IF NOT EXISTS idx_cases_narrative_status ON cases(narrative_status);

-- LLM Queue indexes
CREATE INDEX IF NOT EXISTS idx_llm_queue_alert_id ON llm_queue(alert_id);
CREATE INDEX IF NOT EXISTS idx_llm_queue_status ON llm_queue(status);
CREATE INDEX IF NOT EXISTS idx_llm_queue_priority ON llm_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_llm_queue_status_priority ON llm_queue(status, priority DESC);

-- Chat Sessions indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_active_at ON chat_sessions(last_active_at);

-- Chat History indexes
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_history_role ON chat_history(role);

-- Control Signal Matrix indexes
CREATE INDEX IF NOT EXISTS idx_control_signal_matrix_domain ON control_signal_matrix(domain);
CREATE INDEX IF NOT EXISTS idx_control_signal_matrix_matrix_id ON control_signal_matrix(matrix_id);
CREATE INDEX IF NOT EXISTS idx_control_signal_matrix_anomaly_pattern ON control_signal_matrix USING GIN(anomaly_pattern);

-- Uploads indexes
CREATE INDEX IF NOT EXISTS idx_uploads_user_id ON uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_uploads_domain ON uploads(domain);
CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
CREATE INDEX IF NOT EXISTS idx_uploads_created_at ON uploads(created_at);
CREATE INDEX IF NOT EXISTS idx_uploads_filename ON uploads(filename);
