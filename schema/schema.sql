-- Engagement Analytics Database Schema
-- Optimized for time-series queries and aggregations

-- Authors table
CREATE TABLE IF NOT EXISTS authors (
    author_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    joined_date DATE NOT NULL,
    author_category VARCHAR(100) NOT NULL
);

CREATE INDEX idx_authors_category ON authors(author_category);
CREATE INDEX idx_authors_joined_date ON authors(joined_date);

-- Posts table
CREATE TABLE IF NOT EXISTS posts (
    post_id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(author_id),
    category VARCHAR(100) NOT NULL,
    publish_timestamp TIMESTAMP NOT NULL,
    title VARCHAR(500) NOT NULL,
    content_length INTEGER NOT NULL,
    has_media BOOLEAN DEFAULT FALSE
);

-- Composite index for author + category aggregations
CREATE INDEX idx_posts_author_category ON posts(author_id, category);

-- Index for time-based queries
CREATE INDEX idx_posts_publish_timestamp ON posts(publish_timestamp DESC);

-- Covering index for common query pattern
CREATE INDEX idx_posts_category_timestamp ON posts(category, publish_timestamp);

-- Engagements table (time-series optimized)
CREATE TABLE IF NOT EXISTS engagements (
    engagement_id BIGSERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(post_id),
    type VARCHAR(20) NOT NULL CHECK (type IN ('view', 'like', 'comment', 'share')),
    user_id INTEGER,
    engaged_timestamp TIMESTAMP NOT NULL
);

-- Critical composite index for engagement queries
CREATE INDEX idx_engagements_post_timestamp ON engagements(post_id, engaged_timestamp DESC);

-- Index for engagement type filtering
CREATE INDEX idx_engagements_type ON engagements(type);

-- Index for time-based aggregations
CREATE INDEX idx_engagements_timestamp ON engagements(engaged_timestamp DESC);

-- Index for user engagement history
CREATE INDEX idx_engagements_user ON engagements(user_id) WHERE user_id IS NOT NULL;

-- Post metadata table
CREATE TABLE IF NOT EXISTS post_metadata (
    post_id INTEGER PRIMARY KEY REFERENCES posts(post_id),
    tags TEXT[] DEFAULT '{}',
    is_promoted BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en'
);

-- GIN index for array operations on tags
CREATE INDEX idx_post_metadata_tags ON post_metadata USING GIN(tags);

-- Partial index for promoted posts (queries often filter by this)
CREATE INDEX idx_post_metadata_promoted ON post_metadata(post_id) WHERE is_promoted = TRUE;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    signup_date DATE NOT NULL,
    country VARCHAR(2),
    user_segment VARCHAR(50) NOT NULL
);

CREATE INDEX idx_users_segment ON users(user_segment);
CREATE INDEX idx_users_country ON users(country);

-- Materialized view for frequently accessed engagement stats
CREATE MATERIALIZED VIEW IF NOT EXISTS engagement_stats AS
SELECT
    p.post_id,
    p.author_id,
    p.category,
    p.publish_timestamp,
    COUNT(CASE WHEN e.type = 'view' THEN 1 END) AS view_count,
    COUNT(CASE WHEN e.type = 'like' THEN 1 END) AS like_count,
    COUNT(CASE WHEN e.type = 'comment' THEN 1 END) AS comment_count,
    COUNT(CASE WHEN e.type = 'share' THEN 1 END) AS share_count,
    COUNT(e.engagement_id) AS total_engagements
FROM posts p
LEFT JOIN engagements e ON p.post_id = e.post_id
GROUP BY p.post_id, p.author_id, p.category, p.publish_timestamp;

CREATE INDEX idx_engagement_stats_author ON engagement_stats(author_id);
CREATE INDEX idx_engagement_stats_category ON engagement_stats(category);

-- Function to refresh materialized view (call periodically in production)
CREATE OR REPLACE FUNCTION refresh_engagement_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW engagement_stats;
END;
$$ LANGUAGE plpgsql;
