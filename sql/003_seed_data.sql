-- SAIA V4 Seed Data

-- Insert default admin user (password: admin123)
-- Password hash generated using passlib with bcrypt
INSERT INTO users (username, password_hash, role, data_scope, is_active)
VALUES (
  'admin',
  '$2b$12$GRLdNijSQMUvqfAHXVl.U.2gZfU6z2t1FZJm0aMF8gKFGXQmWW3mK',
  'admin',
  ARRAY['*'],
  true
)
ON CONFLICT (username) DO NOTHING;

-- Insert action privilege levels
INSERT INTO action_privilege_levels (action, privilege_level) VALUES
  ('read', 1),
  ('write', 2),
  ('delete', 3),
  ('configure', 4),
  ('admin', 5)
ON CONFLICT (action) DO NOTHING;

-- Insert asset registry seed data
INSERT INTO asset_registry (asset_name, criticality_score, is_sensitive) VALUES
  ('Production Database', 5, true),
  ('Authentication Service', 5, true),
  ('API Gateway', 4, false),
  ('Web Server', 3, false),
  ('Backup Storage', 4, true),
  ('Cache Service', 2, false),
  ('Message Queue', 3, false),
  ('Logging Service', 2, false),
  ('DNS Server', 5, true),
  ('Firewall', 5, true)
ON CONFLICT DO NOTHING;

-- Insert some default control signal patterns
INSERT INTO control_signal_matrix (matrix_id, domain, anomaly_pattern, primary_clause, secondary_clauses, severity_guidance)
VALUES
  ('CSM-001', 'windows',
   '{"pattern": "multiple_failed_logins", "threshold": 5, "time_window": "300s"}',
   'A3',
   ARRAY['A1', 'A2'],
   'Monitor for credential stuffing or brute force attempts'),
  ('CSM-002', 'linux',
   '{"pattern": "privilege_escalation", "patterns": ["sudo", "su"], "frequency_threshold": 10}',
   'B2',
   ARRAY['B1', 'B3'],
   'Escalate immediately for privilege elevation attempts'),
  ('CSM-003', 'network',
   '{"pattern": "data_exfiltration", "data_volume_threshold": "1GB", "time_window": "3600s"}',
   'C1',
   ARRAY['C2', 'C3'],
   'Critical - potential data breach in progress'),
  ('CSM-004', 'application',
   '{"pattern": "sql_injection_attempt", "regex_patterns": ["UNION", "SELECT", "DROP"]}',
   'A4',
   ARRAY['A1'],
   'Potential SQL injection attack detected')
ON CONFLICT (matrix_id) DO NOTHING;
