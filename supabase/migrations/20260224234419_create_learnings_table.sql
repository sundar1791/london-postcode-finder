-- =============================================================================
-- Migration: create_learnings_table
-- Raw material for the agent's periodic distillation process. Each row
-- captures a structured observation extracted from a completed search:
-- what the user wanted, how the agent responded, the token pattern used,
-- and the outcome. These rows are consumed to update agent_config.distilled_brain.
-- =============================================================================

CREATE TABLE learnings (
  -- Primary key
  id  uuid  PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Categorises the learning so distillation can weight it appropriately
  category  text  NOT NULL
    CHECK (category IN ('context_methodology', 'token_pattern', 'synthesizer_insight')),

  -- Full sentence describing what the user was trying to achieve
  context_intent  text  NOT NULL,

  -- Full sentence describing the method or approach the agent applied
  methodology  text  NOT NULL,

  -- Full sentence describing the token allocation pattern that was observed
  token_pattern  text  NOT NULL,

  -- Full sentence summarising the top result and why it ranked first
  outcome_summary  text  NOT NULL,

  -- Record timestamp
  created_at  timestamptz  NOT NULL DEFAULT now()
);

-- Filtered queries by category during distillation runs
CREATE INDEX idx_learnings_category ON learnings (category);

-- Recency-ordered fetches (newest learnings processed first)
CREATE INDEX idx_learnings_created_at ON learnings (created_at);

COMMENT ON TABLE learnings IS
  'Raw learning records extracted from completed searches. Each row is a '
  'structured observation about user intent, agent methodology, token '
  'allocation patterns, and outcomes. These records are the raw material '
  'consumed by the distillation process that writes agent_config.distilled_brain.';
