-- AI Study Assistant — Supabase Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ── Users profile (extends Supabase Auth) ──────────────────────────────────
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  full_name   text,
  created_at  timestamptz default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Documents ───────────────────────────────────────────────────────────────
create table if not exists public.documents (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid references public.profiles(id) on delete cascade,
  filename    text not null,
  file_size   bigint,
  created_at  timestamptz default now()
);

-- ── Results (cached summaries + MCQs) ───────────────────────────────────────
create table if not exists public.results (
  id              uuid primary key default uuid_generate_v4(),
  document_id     uuid references public.documents(id) on delete cascade,
  user_id         uuid references public.profiles(id) on delete cascade,
  action          text not null check (action in ('summary', 'mcqs')),
  summary         text,
  overview_blocks jsonb default '[]',
  sections        jsonb default '[]',
  key_points      jsonb default '[]',
  key_terms       jsonb default '[]',
  study_tips      jsonb default '[]',
  mcqs            jsonb default '[]',
  created_at      timestamptz default now()
);

-- ── Quiz attempts ────────────────────────────────────────────────────────────
create table if not exists public.quiz_attempts (
  id          uuid primary key default uuid_generate_v4(),
  result_id   uuid references public.results(id) on delete cascade,
  user_id     uuid references public.profiles(id) on delete cascade,
  score       integer not null,
  total       integer not null,
  answers     jsonb default '[]',
  attempted_at timestamptz default now()
);

-- ── Row Level Security ───────────────────────────────────────────────────────
alter table public.profiles       enable row level security;
alter table public.documents      enable row level security;
alter table public.results        enable row level security;
alter table public.quiz_attempts  enable row level security;

-- Profiles: users can only see/edit their own
create policy "profiles_select" on public.profiles for select using (auth.uid() = id);
create policy "profiles_update" on public.profiles for update using (auth.uid() = id);

-- Documents: users can only see/insert their own
create policy "documents_select" on public.documents for select using (auth.uid() = user_id);
create policy "documents_insert" on public.documents for insert with check (auth.uid() = user_id);
create policy "documents_delete" on public.documents for delete using (auth.uid() = user_id);

-- Results: users can only see/insert their own
create policy "results_select" on public.results for select using (auth.uid() = user_id);
create policy "results_insert" on public.results for insert with check (auth.uid() = user_id);

-- Quiz attempts: users can only see/insert their own
create policy "quiz_select" on public.quiz_attempts for select using (auth.uid() = user_id);
create policy "quiz_insert" on public.quiz_attempts for insert with check (auth.uid() = user_id);
