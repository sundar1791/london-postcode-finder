-- Spawn cache: Context Sub-Agent results keyed by the Overpass tag (or web
-- search intent). Entries younger than SPAWN_CACHE_MAX_AGE_DAYS are reused so
-- repeat queries ("I need a nursery nearby") skip the slow live Overpass run.
create table spawn_cache (
  overpass_query  text         primary key,
  scores          jsonb        not null,
  created_at      timestamptz  not null default now()
);

-- Richer search persistence for the API layer.
alter table searches add column adjusted_allocation jsonb;
alter table searches add column top_5 jsonb;
alter table searches add column duration_ms integer;
alter table searches add column status text not null default 'complete'
  check (status in ('complete', 'error', 'timeout'));

-- Daily cap counts searches since midnight UTC.
create index idx_searches_created_at on searches (created_at);
