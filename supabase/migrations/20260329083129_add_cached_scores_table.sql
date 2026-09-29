create table cached_scores (
  id uuid primary key default gen_random_uuid(),
  district text not null,
  dimension text not null,
  raw_value numeric,
  score numeric not null,
  needs_retry boolean default false,
  last_updated timestamptz default now(),
  unique (district, dimension)
);