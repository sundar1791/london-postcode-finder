-- The v1 synthesiser produces a single narrative sentence per learning, stored
-- in outcome_summary. The decomposed columns (context_intent, methodology,
-- token_pattern) are populated only when the synthesiser is later enriched to
-- emit the full decomposition (Milestone 7). Until then they must be nullable.
alter table learnings alter column context_intent drop not null;
alter table learnings alter column methodology drop not null;
alter table learnings alter column token_pattern drop not null;