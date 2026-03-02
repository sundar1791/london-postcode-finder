-- =============================================================================
-- Migration: add_rent_data_table
-- Stores median monthly rent per district, sourced from the ONS Price Index
-- of Private Rents. One row per district code; borough is denormalised for
-- easy querying without a join.
-- =============================================================================

CREATE TABLE rent_data (
  id          integer      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  borough     text         NOT NULL,
  district    text         NOT NULL UNIQUE,
  median_rent numeric      NOT NULL,
  created_at  timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE rent_data IS
  'ONS median monthly private rent per London postcode district. '
  'borough is the ONS area name; district is the outward postcode (e.g. E1). '
  'median_rent is in GBP per month.';
