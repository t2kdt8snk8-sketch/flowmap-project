-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

----------------------------------------------------------------
-- 1. Utility Functions
----------------------------------------------------------------

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------
-- 2. Essential System Tables
----------------------------------------------------------------

-- 2.1 Users (Public Profile)
-- Automatically managed via triggers from auth.users (to be implemented if needed, manual insert for now)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    display_name VARCHAR(100),
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2.2 Common Codes (System Constants)
CREATE TABLE common_codes (
    group_code VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order SMALLINT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    PRIMARY KEY (group_code, code)
);

-- 2.3 Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id UUID,
    action VARCHAR(10) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data JSONB,
    new_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

----------------------------------------------------------------
-- 3. Core Domain Tables
----------------------------------------------------------------

-- 3.1 Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    summary TEXT,
    role VARCHAR(50), -- Persona used
    is_archived BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3.2 Flow Steps
CREATE TABLE flow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    step_order SMALLINT NOT NULL CHECK (step_order BETWEEN 1 AND 4),
    title VARCHAR(255) NOT NULL,
    goal TEXT,
    rationale TEXT,
    cognitive_focus VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT flow_steps_order_unique UNIQUE (project_id, step_order)
);

-- 3.3 Step Prompts
CREATE TABLE step_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id UUID NOT NULL REFERENCES flow_steps(id) ON DELETE CASCADE,
    prompt_text TEXT NOT NULL,
    prompt_type VARCHAR(50),
    order_index SMALLINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT step_prompts_order_unique UNIQUE (step_id, order_index)
);

----------------------------------------------------------------
-- 4. Triggers
----------------------------------------------------------------

-- updated_at triggers
CREATE TRIGGER handle_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER handle_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER handle_flow_steps_updated_at BEFORE UPDATE ON flow_steps FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER handle_step_prompts_updated_at BEFORE UPDATE ON step_prompts FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

----------------------------------------------------------------
-- 5. RLS Policies
----------------------------------------------------------------

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE common_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE step_prompts ENABLE ROW LEVEL SECURITY;

-- Users
CREATE POLICY "Users can manage own profile" ON users
    FOR ALL USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

-- Common Codes (Public Read)
CREATE POLICY "Public read common codes" ON common_codes
    FOR SELECT USING (true);

-- Projects
CREATE POLICY "Users manage own projects" ON projects
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Flow Steps
CREATE POLICY "Users manage own steps" ON flow_steps
    FOR ALL USING (
        EXISTS (SELECT 1 FROM projects WHERE projects.id = flow_steps.project_id AND projects.user_id = auth.uid())
    );

-- Step Prompts
CREATE POLICY "Users manage own prompts" ON step_prompts
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM flow_steps 
            JOIN projects ON projects.id = flow_steps.project_id 
            WHERE flow_steps.id = step_prompts.step_id AND projects.user_id = auth.uid()
        )
    );
