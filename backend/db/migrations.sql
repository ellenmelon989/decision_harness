-- Decision Harness — Supabase schema (ROADMAP §4)
-- Run in the Supabase SQL editor (or `supabase db push`). Idempotent-ish: safe to re-run after a reset.

create extension if not exists pgcrypto;   -- gen_random_uuid()

-- Users come from Supabase Auth (auth.users). We reference auth.uid().

create table if not exists orgs (
  id          uuid primary key default gen_random_uuid(),
  -- app-level owner (the JWT `sub`). NOT a FK to auth.users so the dev/seed
  -- DEMO_USER (a synthetic uuid) can own rows; RLS below still scopes by auth.uid().
  owner_id    uuid,
  name        text not null,
  description text,
  preset      text,                       -- 'vc' | 'board' | 'judges' | null
  created_at  timestamptz default now()
);

create table if not exists agents (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references orgs(id) on delete cascade,
  name          text not null,            -- "Ra'ad Siraj"
  role          text not null,            -- "Head of AI Governance"
  system_prompt text not null,
  model         text not null default 'claude-sonnet-4-6',
  provider      text not null default 'anthropic',   -- 'anthropic' | 'wandb'
  weight        numeric not null default 1.0,
  voice_id      text,                     -- ElevenLabs voice id
  tools         jsonb default '[]',       -- ["research","company_data","wandb"]
  position      int default 0,            -- seat order in the boardroom
  structural    boolean not null default false,  -- pinned seat (e.g. the Skeptic)
  veto          boolean not null default false,  -- can cap a clean YES to CONDITIONAL
  created_at    timestamptz default now()
);
-- Idempotent for DBs created before these columns existed (create-if-not-exists
-- above is a no-op once the table is present).
alter table agents add column if not exists structural boolean not null default false;
alter table agents add column if not exists veto       boolean not null default false;

create table if not exists sessions (
  id               uuid primary key default gen_random_uuid(),
  org_id           uuid not null references orgs(id) on delete cascade,
  created_by       uuid,                            -- app-level (JWT sub); not a FK (see orgs.owner_id)
  question         text not null,
  context          text,
  weights_override jsonb,                 -- {agent_id: weight} for HITL re-run
  status           text not null default 'pending',  -- pending|running|done|error
  rounds           int default 3,
  final_verdict    jsonb,
  weave_trace_url  text,
  parent_session   uuid references sessions(id) on delete set null,  -- re-runs / comparison
  created_at       timestamptz default now()
);

-- The inspectable transcript. Append-only, ordered by seq.
create table if not exists events (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid not null references sessions(id) on delete cascade,
  seq           bigint generated always as identity,
  round         int not null,
  agent_id      uuid references agents(id) on delete cascade,
  type          text not null,
  content       jsonb not null,
  parent_event  uuid references events(id) on delete set null,
  influenced_by jsonb default '[]',
  created_at    timestamptz default now()
);
create index if not exists events_session_seq_idx on events(session_id, seq);

-- Denormalized per-round stance for charts + influence graph.
create table if not exists positions (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references sessions(id) on delete cascade,
  round       int not null,
  agent_id    uuid not null references agents(id) on delete cascade,
  stance      text not null,              -- 'YES' | 'NO' | 'CONDITIONAL'
  score       numeric not null,           -- 0..10
  confidence  numeric not null,           -- 0..1
  rationale   text,
  unique (session_id, round, agent_id)
);

-- ─── RLS (ownership-scoped) ──────────────────────────────────────────────────
-- The service-key backend bypasses RLS; these protect any DIRECT client access
-- (frontend anon key + user JWT). A user may only touch rows in orgs they own.
alter table orgs      enable row level security;
alter table agents    enable row level security;
alter table sessions  enable row level security;
alter table events    enable row level security;
alter table positions enable row level security;

drop policy if exists org_owner on orgs;
create policy org_owner on orgs for all to authenticated
  using (owner_id = auth.uid()) with check (owner_id = auth.uid());

drop policy if exists agents_owner on agents;
create policy agents_owner on agents for all to authenticated
  using (exists (select 1 from orgs o where o.id = agents.org_id and o.owner_id = auth.uid()))
  with check (exists (select 1 from orgs o where o.id = agents.org_id and o.owner_id = auth.uid()));

drop policy if exists sessions_owner on sessions;
create policy sessions_owner on sessions for all to authenticated
  using (exists (select 1 from orgs o where o.id = sessions.org_id and o.owner_id = auth.uid()))
  with check (exists (select 1 from orgs o where o.id = sessions.org_id and o.owner_id = auth.uid()));

drop policy if exists events_owner on events;
create policy events_owner on events for all to authenticated
  using (exists (select 1 from sessions s join orgs o on o.id = s.org_id
                 where s.id = events.session_id and o.owner_id = auth.uid()))
  with check (exists (select 1 from sessions s join orgs o on o.id = s.org_id
                      where s.id = events.session_id and o.owner_id = auth.uid()));

drop policy if exists positions_owner on positions;
create policy positions_owner on positions for all to authenticated
  using (exists (select 1 from sessions s join orgs o on o.id = s.org_id
                 where s.id = positions.session_id and o.owner_id = auth.uid()))
  with check (exists (select 1 from sessions s join orgs o on o.id = s.org_id
                      where s.id = positions.session_id and o.owner_id = auth.uid()));

-- ─── self-heal FK delete rules on existing DBs (create-if-not-exists skips column defs) ───
alter table events drop constraint if exists events_agent_id_fkey;
alter table events add constraint events_agent_id_fkey
  foreign key (agent_id) references agents(id) on delete cascade;
alter table events drop constraint if exists events_parent_event_fkey;
alter table events add constraint events_parent_event_fkey
  foreign key (parent_event) references events(id) on delete set null;
alter table sessions drop constraint if exists sessions_parent_session_fkey;
alter table sessions add constraint sessions_parent_session_fkey
  foreign key (parent_session) references sessions(id) on delete set null;
