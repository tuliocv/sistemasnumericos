-- =============================================================
-- SCHEMA PÚBLICO (pode ir para o GitHub)
-- App: Sistemas Numéricos
-- =============================================================

create extension if not exists pgcrypto;

create table if not exists public.activities (
    code text primary key,
    title text not null,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.questions (
    id text primary key,
    activity_code text not null references public.activities(code) on delete cascade,
    position integer not null,
    level text not null,
    prompt text not null,
    options jsonb not null,
    correct_answer text not null,
    explanation text not null,
    active boolean not null default true,
    unique(activity_code, position)
);

create table if not exists public.students (
    id uuid primary key default gen_random_uuid(),
    ra text not null unique,
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.attempts (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.students(id) on delete cascade,
    activity_code text not null references public.activities(code) on delete cascade,
    started_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    submitted_at timestamptz,
    unique(student_id, activity_code)
);

create table if not exists public.responses (
    attempt_id uuid not null references public.attempts(id) on delete cascade,
    question_id text not null references public.questions(id) on delete cascade,
    answer text not null,
    is_correct boolean not null,
    answered_at timestamptz not null default now(),
    primary key(attempt_id, question_id)
);

create index if not exists idx_questions_activity
    on public.questions(activity_code, position);

create index if not exists idx_attempts_activity
    on public.attempts(activity_code);

create index if not exists idx_responses_attempt
    on public.responses(attempt_id);

-- O app usa uma Secret Key somente no backend do Streamlit.
-- Mantemos RLS ativo e NÃO criamos políticas públicas.
alter table public.activities enable row level security;
alter table public.questions enable row level security;
alter table public.students enable row level security;
alter table public.attempts enable row level security;
alter table public.responses enable row level security;
