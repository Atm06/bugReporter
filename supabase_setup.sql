-- Run this in Supabase SQL Editor (https://supabase.com/dashboard → SQL Editor)

-- 1. Create the bugs table
CREATE TABLE IF NOT EXISTS bugs (
    id              BIGINT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'Medium',
    category        TEXT NOT NULL DEFAULT 'Other',
    subcategory     TEXT NOT NULL DEFAULT '',
    steps           TEXT NOT NULL DEFAULT '',
    screenshot      TEXT NOT NULL DEFAULT '',
    reporter_name   TEXT NOT NULL DEFAULT '',
    reporter_email  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'Open',
    created_at      TEXT NOT NULL,
    page_url        TEXT NOT NULL DEFAULT '',
    page_title      TEXT NOT NULL DEFAULT ''
);

-- 2. Grant table access to API roles (required for PostgREST)
GRANT ALL ON bugs TO anon;
GRANT ALL ON bugs TO authenticated;

-- 3. Enable RLS and allow full access via anon key
ALTER TABLE bugs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow full access via anon key" ON bugs
    FOR ALL TO anon
    USING (true)
    WITH CHECK (true);

-- 4. Create a public storage bucket for screenshots
INSERT INTO storage.buckets (id, name, public)
VALUES ('screenshots', 'screenshots', true)
ON CONFLICT (id) DO NOTHING;

-- 5. Allow public uploads and reads on the screenshots bucket
CREATE POLICY "Allow public uploads" ON storage.objects
    FOR INSERT TO anon
    WITH CHECK (bucket_id = 'screenshots');

CREATE POLICY "Allow public reads" ON storage.objects
    FOR SELECT TO anon
    USING (bucket_id = 'screenshots');
