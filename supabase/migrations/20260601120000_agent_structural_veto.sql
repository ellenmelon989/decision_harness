-- Agent governance flags (ROADMAP §7.4 cap rule).
--   structural — a pinned seat that can't be removed/re-weighted away (the Skeptic)
--   veto       — can cap a clean YES verdict down to CONDITIONAL when not itself convinced
-- Mirrors backend/db/migrations.sql and backend/schemas.py (the frozen contract).
alter table agents add column if not exists structural boolean not null default false;
alter table agents add column if not exists veto       boolean not null default false;
