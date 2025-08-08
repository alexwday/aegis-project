-- Test pgvector capabilities and create appropriate tables
-- This script tests what vector features are available and adapts accordingly

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop test tables if they exist
DROP TABLE IF EXISTS vector_capability_test CASCADE;
DROP TABLE IF EXISTS vector_capabilities CASCADE;

-- Create a table to store our capability test results
CREATE TABLE IF NOT EXISTS vector_capabilities (
    capability VARCHAR(100) PRIMARY KEY,
    supported BOOLEAN,
    details TEXT,
    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clear previous test results
DELETE FROM vector_capabilities;

-- Test 1: Check pgvector version
DO $$
DECLARE
    version_str TEXT;
    version_num NUMERIC;
BEGIN
    SELECT extversion INTO version_str 
    FROM pg_extension 
    WHERE extname = 'vector';
    
    IF version_str IS NOT NULL THEN
        -- Extract numeric version for comparison
        version_num := CAST(SPLIT_PART(version_str, '.', 1) || '.' || SPLIT_PART(version_str, '.', 2) AS NUMERIC);
        
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('pgvector_installed', true, 'Version ' || version_str);
        
        -- Check if version supports halfvec (>= 0.5)
        IF version_num >= 0.5 THEN
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('halfvec_available', true, 'halfvec type available (v0.5.0+ feature)');
        ELSE
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('halfvec_available', false, 'Requires pgvector v0.5.0+ (current: ' || version_str || ')');
        END IF;
    ELSE
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('pgvector_installed', false, 'Extension not found');
    END IF;
END $$;

-- Test 2: Can we create a table with vector(3072)?
DO $$
BEGIN
    -- Try to create table with 3072 dimensions
    BEGIN
        CREATE TABLE vector_capability_test (
            id SERIAL PRIMARY KEY,
            embedding vector(3072)
        );
        
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('vector_3072', true, 'Standard vector with 3072 dimensions supported');
        
        DROP TABLE vector_capability_test;
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('vector_3072', false, 'Error: ' || SQLERRM);
    END;
END $$;

-- Test 3: Can we create a table with halfvec(3072)?
DO $$
BEGIN
    -- Try to create table with halfvec type
    BEGIN
        CREATE TABLE vector_capability_test (
            id SERIAL PRIMARY KEY,
            embedding halfvec(3072)
        );
        
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('halfvec_3072', true, 'halfvec with 3072 dimensions supported (50% storage savings)');
        
        DROP TABLE vector_capability_test;
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('halfvec_3072', false, 'Not supported: ' || SUBSTRING(SQLERRM, 1, 100));
    END;
END $$;

-- Test 4: Can we create a table with vector(1536)?
DO $$
BEGIN
    -- Try standard embedding size
    BEGIN
        CREATE TABLE vector_capability_test (
            id SERIAL PRIMARY KEY,
            embedding vector(1536)
        );
        
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('vector_1536', true, 'Standard vector with 1536 dimensions supported');
        
        DROP TABLE vector_capability_test;
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO vector_capabilities (capability, supported, details)
        VALUES ('vector_1536', false, 'Error: ' || SQLERRM);
    END;
END $$;

-- Test 5: Check for IVFFlat index support
DO $$
BEGIN
    BEGIN
        -- Check if ivfflat access method exists
        IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'ivfflat') THEN
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('ivfflat_index', true, 'IVFFlat indexing available for similarity search');
        ELSE
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('ivfflat_index', false, 'IVFFlat indexing not available');
        END IF;
    END;
END $$;

-- Test 6: Check for HNSW index support
DO $$
BEGIN
    BEGIN
        -- Check if hnsw access method exists
        IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'hnsw') THEN
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('hnsw_index', true, 'HNSW indexing available (better performance)');
        ELSE
            INSERT INTO vector_capabilities (capability, supported, details)
            VALUES ('hnsw_index', false, 'HNSW indexing not available');
        END IF;
    END;
END $$;

-- Display test results
SELECT 
    capability,
    CASE WHEN supported THEN '✅' ELSE '❌' END as status,
    details
FROM vector_capabilities
ORDER BY 
    CASE capability
        WHEN 'pgvector_installed' THEN 1
        WHEN 'vector_1536' THEN 2
        WHEN 'vector_3072' THEN 3
        WHEN 'halfvec_available' THEN 4
        WHEN 'halfvec_3072' THEN 5
        WHEN 'ivfflat_index' THEN 6
        WHEN 'hnsw_index' THEN 7
        ELSE 8
    END;

-- Create recommendation based on capabilities
DO $$
DECLARE
    has_halfvec BOOLEAN;
    has_3072 BOOLEAN;
    recommendation TEXT;
BEGIN
    SELECT supported INTO has_halfvec 
    FROM vector_capabilities 
    WHERE capability = 'halfvec_3072';
    
    SELECT supported INTO has_3072 
    FROM vector_capabilities 
    WHERE capability = 'vector_3072';
    
    IF has_halfvec THEN
        recommendation := 'Use halfvec(3072) for document_embeddings table - 50% storage savings';
    ELSIF has_3072 THEN
        recommendation := 'Use vector(3072) for document_embeddings table - full precision';
    ELSE
        recommendation := 'Use vector(1536) for document_embeddings table - smaller model only';
    END IF;
    
    INSERT INTO vector_capabilities (capability, supported, details)
    VALUES ('recommendation', true, recommendation);
END $$;

-- Show final recommendation
SELECT '📝 RECOMMENDATION:' as info, details as message
FROM vector_capabilities
WHERE capability = 'recommendation';