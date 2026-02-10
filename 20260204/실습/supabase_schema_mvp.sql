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
-- 2. Core Domain Tables
----------------------------------------------------------------

-- 2.1 Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    summary TEXT,
    role VARCHAR(50), 
    is_archived BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2.2 Flow Steps
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

-- 2.3 Step Prompts
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
-- 3. Triggers
----------------------------------------------------------------

CREATE TRIGGER handle_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER handle_flow_steps_updated_at BEFORE UPDATE ON flow_steps FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
CREATE TRIGGER handle_step_prompts_updated_at BEFORE UPDATE ON step_prompts FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

----------------------------------------------------------------
-- 4. RLS Policies
----------------------------------------------------------------

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE step_prompts ENABLE ROW LEVEL SECURITY;

-- Projects
CREATE POLICY "Users manage own projects" ON projects
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Flow Steps
CREATE POLICY "Users manage own steps" ON flow_steps
    FOR ALL USING (
        EXISTS (SELECT 1 FROM projects WHERE projects.id = flow_steps.project_id AND projects.user_id = auth.uid())
    )
    WITH CHECK (
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
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM flow_steps 
            JOIN projects ON projects.id = flow_steps.project_id 
            WHERE flow_steps.id = step_prompts.step_id AND projects.user_id = auth.uid()
        )
    );
