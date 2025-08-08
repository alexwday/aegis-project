-- Sample data for AEGIS development and testing

-- Insert sample agents
INSERT INTO agents (agent_name, agent_type, description, configuration) VALUES
('Router Agent', 'router', 'Routes conversations to appropriate specialized agents', '{"model": "gpt-4", "temperature": 0.3}'),
('Clarifier Agent', 'clarifier', 'Clarifies ambiguous user requests', '{"model": "gpt-4", "temperature": 0.5}'),
('Planner Agent', 'planner', 'Creates execution plans for complex tasks', '{"model": "gpt-4", "temperature": 0.4}'),
('Summarizer Agent', 'summarizer', 'Summarizes long conversations and documents', '{"model": "gpt-3.5-turbo", "temperature": 0.3}'),
('Database Agent', 'database', 'Handles database queries and operations', '{"model": "gpt-4", "temperature": 0.2}'),
('Report Agent', 'report', 'Generates various types of reports', '{"model": "gpt-4", "temperature": 0.4}');

-- Insert sample conversations
INSERT INTO conversations (conversation_id, user_id, status, metadata) VALUES
('conv_001', 'user_123', 'completed', '{"topic": "database query", "satisfaction": 5}'),
('conv_002', 'user_456', 'completed', '{"topic": "report generation", "satisfaction": 4}'),
('conv_003', 'user_123', 'active', '{"topic": "general inquiry"}');

-- Insert sample agent responses
INSERT INTO agent_responses (conversation_id, agent_id, request_text, response_text, tokens_used, response_time_ms, metadata) VALUES
('conv_001', 1, 'How can I query the user database?', 'I''ll route you to our Database Agent who can help with database queries.', 45, 230, '{"confidence": 0.95}'),
('conv_001', 5, 'Show me all active users', 'Here are the active users in the system: [query results]', 120, 450, '{"query_type": "select", "rows_returned": 25}'),
('conv_002', 1, 'Generate monthly report', 'I''ll connect you with our Report Agent for report generation.', 38, 180, '{"confidence": 0.98}'),
('conv_002', 6, 'Create financial summary for March', 'I''ve generated the March financial summary report. [report details]', 250, 1200, '{"report_type": "financial", "pages": 5}');

-- Insert sample documents
INSERT INTO documents (document_id, title, content, source, document_type, metadata) VALUES
('doc_001', 'AEGIS System Overview', 'AEGIS is an advanced AI system designed for enterprise conversations...', 'internal', 'documentation', '{"version": "1.0", "author": "Team AEGIS"}'),
('doc_002', 'Database Best Practices', 'When working with databases in AEGIS, follow these guidelines...', 'internal', 'guide', '{"category": "technical", "last_reviewed": "2024-01-15"}'),
('doc_003', 'Q4 2023 Report', 'Quarterly performance metrics and analysis...', 'reports', 'report', '{"quarter": "Q4", "year": 2023, "department": "all"}');

-- Insert sample document chunks (without embeddings for now)
INSERT INTO document_embeddings (document_id, chunk_index, chunk_text, metadata) VALUES
('doc_001', 0, 'AEGIS is an advanced AI system designed for enterprise conversations.', '{"section": "introduction"}'),
('doc_001', 1, 'The system uses multiple specialized agents to handle different types of requests.', '{"section": "architecture"}'),
('doc_002', 0, 'Always use parameterized queries to prevent SQL injection.', '{"section": "security"}'),
('doc_002', 1, 'Index frequently queried columns for better performance.', '{"section": "performance"}');

-- Summary statistics
SELECT 'Data Import Summary' as info;
SELECT 'Agents:' as table_name, COUNT(*) as count FROM agents
UNION ALL
SELECT 'Conversations:', COUNT(*) FROM conversations
UNION ALL
SELECT 'Agent Responses:', COUNT(*) FROM agent_responses
UNION ALL
SELECT 'Documents:', COUNT(*) FROM documents
UNION ALL
SELECT 'Document Chunks:', COUNT(*) FROM document_embeddings;