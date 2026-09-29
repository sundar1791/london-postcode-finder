-- The synthesiser prompt and all project code use British spelling
-- ("synthesiser"), but this table's category CHECK constraint was created with
-- the American spelling ("synthesizer_insight"), causing every synthesiser_insight
-- learning to be rejected. Align the constraint to the codebase's British spelling.
alter table learnings drop constraint learnings_category_check;
alter table learnings add constraint learnings_category_check
  check (category in ('context_methodology', 'token_pattern', 'synthesiser_insight'));