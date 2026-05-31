-- Add ON DELETE rules to event/session FKs so deleting an org/session/agent
-- cascades cleanly (see backend/db/migrations.sql, kept in sync).
alter table events drop constraint if exists events_agent_id_fkey;
alter table events add constraint events_agent_id_fkey
  foreign key (agent_id) references agents(id) on delete cascade;
alter table events drop constraint if exists events_parent_event_fkey;
alter table events add constraint events_parent_event_fkey
  foreign key (parent_event) references events(id) on delete set null;
alter table sessions drop constraint if exists sessions_parent_session_fkey;
alter table sessions add constraint sessions_parent_session_fkey
  foreign key (parent_session) references sessions(id) on delete set null;
