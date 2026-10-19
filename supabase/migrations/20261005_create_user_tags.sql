-- Migration: Create user_tags table for custom user tags
CREATE TABLE IF NOT EXISTS user_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_tags_user_id_lower_name ON user_tags (user_id, LOWER(name));
CREATE INDEX IF NOT EXISTS idx_user_tags_user_id ON user_tags (user_id);
