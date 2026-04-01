-- Migration: Create prompts table
-- Description: Add prompts table linked to subjects for LLM system prompts
-- Date: 2026-03-04

-- Create prompts table
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on subject_id for faster queries
CREATE INDEX IF NOT EXISTS idx_prompts_subject_id ON prompts(subject_id);

-- Create index on is_active for filtering active prompts
CREATE INDEX IF NOT EXISTS idx_prompts_is_active ON prompts(is_active);

-- Create updated_at trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_prompts_updated_at BEFORE UPDATE ON prompts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add some example prompts for testing (optional)
-- INSERT INTO prompts (subject_id, title, content, is_active) VALUES
-- (1, 'System Prompt', 'You are a helpful assistant for haircutting students. Always provide clear, educational responses in Dutch.', TRUE);
