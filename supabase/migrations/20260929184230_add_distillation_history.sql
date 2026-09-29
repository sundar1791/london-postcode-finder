-- One row per distillation run: the brain before and after, how many raw
-- learnings were consumed, and a short summary of what changed. Powers the
-- distillation timeline on the /learning page.
create table distillation_history (
  id                  uuid         primary key default gen_random_uuid(),
  created_at          timestamptz  not null default now(),
  query_count         integer      not null,
  learnings_consumed  integer      not null,
  previous_brain      text,
  new_brain           text         not null,
  change_summary      text
);

create index idx_distillation_history_created_at on distillation_history (created_at desc);
