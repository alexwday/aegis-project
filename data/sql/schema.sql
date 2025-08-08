-- AEGIS Project Database Schema
-- This file defines the core tables for the AEGIS system

-- Drop existing tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS agent_responses CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS document_embeddings CASCADE;

-- Conversations table
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agents table
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(100) NOT NULL,
    description TEXT,
    configuration JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent responses table
CREATE TABLE agent_responses (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) REFERENCES conversations(conversation_id),
    agent_id INTEGER REFERENCES agents(id),
    request_text TEXT,
    response_text TEXT,
    tokens_used INTEGER,
    response_time_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents table (for RAG)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500),
    content TEXT,
    source VARCHAR(255),
    document_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document embeddings table
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) REFERENCES documents(document_id),
    chunk_index INTEGER,
    chunk_text TEXT,
    embedding VECTOR(1536),  -- Requires pgvector extension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_agent_responses_conversation ON agent_responses(conversation_id);
CREATE INDEX idx_agent_responses_agent ON agent_responses(agent_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_document_embeddings_document ON document_embeddings(document_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();