-- KarirFit – Supabase schema. Run once in Supabase Dashboard -> SQL Editor.
-- Accounts use Supabase Auth (email + password, hashed by Supabase). Registration stores
-- name, status, major, cohort, semester and consent in auth.users.raw_user_meta_data.

-- 1) Test history: one row per finished test, readable only by its owner (row-level security)
create table if not exists public.assessments (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at  timestamptz not null default now(),
  answers     jsonb not null,          -- interests, skills, soft skills, experience, courses, major
  top         jsonb not null           -- top-5 careers with fit score at the time of the test
);
create index if not exists assessments_user_created on public.assessments (user_id, created_at desc);

alter table public.assessments enable row level security;

drop policy if exists "own rows: select" on public.assessments;
drop policy if exists "own rows: insert" on public.assessments;
drop policy if exists "own rows: delete" on public.assessments;
create policy "own rows: select" on public.assessments for select to authenticated using ((select auth.uid()) = user_id);
create policy "own rows: insert" on public.assessments for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own rows: delete" on public.assessments for delete to authenticated using ((select auth.uid()) = user_id);

-- 2) Evaluation log used by the FastAPI backend (created automatically on first start when
--    DATABASE_URL points to this database; listed here for reference). Not exposed to the browser.
create table if not exists public.log (
  id       serial primary key,
  ts       double precision,
  kind     text,
  session  text,                         -- Supabase user id (pseudonymous)
  payload  text
);
alter table public.log enable row level security;   -- no policies: only the backend's DB user can access it

-- Browser access matches the application operations. Evaluation logs stay backend-only.
revoke all on public.log from anon, authenticated;
revoke all on sequence public.log_id_seq from anon, authenticated;
revoke all on public.assessments from anon, authenticated;
grant select, insert, delete on public.assessments to authenticated;
