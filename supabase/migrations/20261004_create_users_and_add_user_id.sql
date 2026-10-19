-- Migration: 20261004_create_users_and_add_user_id.sql
-- Implements multi-user architecture with users table, foreign keys, and Row-Level Security (RLS)

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- 2. Add user_id to pois
ALTER TABLE pois ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_pois_user_id ON pois (user_id);

-- 3. Add user_id to lists
ALTER TABLE lists ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_lists_user_id ON lists (user_id);

-- 4. Enable Row-Level Security (RLS)
ALTER TABLE pois ENABLE ROW LEVEL SECURITY;
ALTER TABLE lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE poi_access_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE poi_list_memberships ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies for Supabase / PostgreSQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'users_manage_own_pois' AND tablename = 'pois') THEN
        CREATE POLICY users_manage_own_pois ON pois
            FOR ALL
            USING (user_id = current_setting('request.jwt.claim.sub', true)::uuid OR user_id IS NULL OR current_user = 'postgres')
            WITH CHECK (user_id = current_setting('request.jwt.claim.sub', true)::uuid OR user_id IS NULL OR current_user = 'postgres');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'users_manage_own_lists' AND tablename = 'lists') THEN
        CREATE POLICY users_manage_own_lists ON lists
            FOR ALL
            USING (user_id = current_setting('request.jwt.claim.sub', true)::uuid OR user_id IS NULL OR current_user = 'postgres')
            WITH CHECK (user_id = current_setting('request.jwt.claim.sub', true)::uuid OR user_id IS NULL OR current_user = 'postgres');
    END IF;
END $$;
