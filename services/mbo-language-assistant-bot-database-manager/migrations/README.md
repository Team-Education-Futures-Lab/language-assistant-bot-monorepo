# Prompts Table Migration Instructions

## Step 1: Create the Prompts Table in Supabase

You need to run the SQL migration in your Supabase database to create the prompts table.

### Option A: Using Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Click on "SQL Editor" in the left sidebar
3. Click "New Query"
4. Copy and paste the SQL from `migrations/001_create_prompts_table.sql`
5. Click "Run" to execute the migration

### Option B: Using Supabase CLI

```bash
# If you have Supabase CLI installed
supabase db push
```

### Option C: Manual SQL Execution

Run the following SQL in Supabase SQL Editor:

```sql
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prompts_subject_id ON prompts(subject_id);
CREATE INDEX IF NOT EXISTS idx_prompts_is_active ON prompts(is_active);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_prompts_updated_at BEFORE UPDATE ON prompts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Step 2: Verify the Table

After running the migration, verify the table was created:

```sql
SELECT * FROM prompts;
```

## Step 3: Test with Sample Data (Optional)

You can add a test prompt to verify everything works:

```sql
-- First, get a subject_id from your subjects table
SELECT id, name FROM subjects LIMIT 1;

-- Then insert a test prompt (replace 1 with your actual subject_id)
INSERT INTO prompts (subject_id, title, content, is_active) 
VALUES (
    1, 
    'System Prompt', 
    'Je bent een behulpzame assistent voor MBO-studenten. Geef altijd duidelijke, educatieve antwoorden in het Nederlands.',
    TRUE
);
```

## Next Steps

After creating the table:
1. The API endpoints are ready to use
2. The dashboard UI will be updated to manage prompts
3. The LLM services will be updated to use prompts

## API Endpoints Available

Once the table is created, these endpoints are available:

- `GET /api/subjects/{subject_id}/prompts` - Get all prompts for a subject
- `POST /api/subjects/{subject_id}/prompts` - Create a new prompt
- `GET /api/prompts/{prompt_id}` - Get a specific prompt
- `PUT /api/prompts/{prompt_id}` - Update a prompt
- `DELETE /api/prompts/{prompt_id}` - Delete a prompt
- `GET /api/subjects/{subject_id}/prompts/active` - Get active prompts (used by LLM)
