-- =============================================================================
-- Migration: create_agent_config_table
-- Singleton table holding the agent's long-term distilled memory.
-- Enforced to exactly one row (id must equal 1). distilled_brain starts
-- NULL and is populated after the first distillation run. query_count
-- tracks total searches processed and drives distillation scheduling.
-- =============================================================================

CREATE TABLE agent_config (
  -- Fixed primary key — only the value 1 is permitted
  id  integer  PRIMARY KEY DEFAULT 1,

  -- Prevents any row other than id = 1 from being inserted
  CONSTRAINT single_row CHECK (id = 1),

  -- The agent's synthesised knowledge string, written by the distillation
  -- process. NULL until the first distillation has run.
  distilled_brain  text,

  -- Timestamp of the most recent distillation run (NULL initially)
  last_distilled  timestamptz,

  -- Running count of searches processed; used to trigger distillation
  query_count  integer  NOT NULL DEFAULT 0
);

COMMENT ON TABLE agent_config IS
  'Singleton configuration and long-term memory for the recommendation agent. '
  'distilled_brain holds synthesised knowledge built from the learnings table. '
  'query_count is incremented on each search and drives automatic distillation '
  'scheduling. Only one row (id = 1) is ever permitted.';

-- =============================================================================
-- Seed: insert the single config row
-- =============================================================================

INSERT INTO agent_config (id, query_count)
VALUES (1, 0);
