-- Migration: Add structured summary columns to public.results
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- Add columns if they don't already exist
ALTER TABLE public.results
  ADD COLUMN IF NOT EXISTS overview_blocks jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS sections jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS key_terms jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS study_tips jsonb DEFAULT '[]';

-- Verify
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'results'
ORDER BY ordinal_position;
