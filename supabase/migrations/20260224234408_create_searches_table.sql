-- =============================================================================
-- Migration: create_searches_table
-- Stores every postcode recommendation search submitted by a user session.
-- Captures the five token allocations, optional free-text context, and the
-- top-5 postcode results produced by the agent.
-- =============================================================================

CREATE TABLE searches (
  -- Primary key
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Anonymous session identifier
  session_id  text        NOT NULL,

  -- Token allocations — each column must be between 0 and 100
  token_safety      integer NOT NULL CHECK (token_safety      BETWEEN 0 AND 100),
  token_green       integer NOT NULL CHECK (token_green       BETWEEN 0 AND 100),
  token_nightlife   integer NOT NULL CHECK (token_nightlife   BETWEEN 0 AND 100),
  token_transport   integer NOT NULL CHECK (token_transport   BETWEEN 0 AND 100),
  token_rent        integer NOT NULL CHECK (token_rent        BETWEEN 0 AND 100),

  -- All five tokens must sum to exactly 100
  CONSTRAINT tokens_sum_to_100
    CHECK (token_safety + token_green + token_nightlife + token_transport + token_rent = 100),

  -- Optional context from the user (max 500 Unicode characters)
  context_text  text
    CHECK (char_length(context_text) <= 500),

  -- Agent output: top-5 postcodes with scores and rationale (null until resolved)
  results  jsonb,

  -- Record timestamp
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Fast lookups of all searches belonging to a session
CREATE INDEX idx_searches_session_id ON searches (session_id);

COMMENT ON TABLE searches IS
  'Each row is one postcode recommendation search. Stores the user''s five '
  'token allocations (must sum to 100), an optional context string, and the '
  'JSONB results payload containing the top-5 recommended postcodes.';
