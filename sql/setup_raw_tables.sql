CREATE TABLE IF NOT EXISTS `hackumass26.raw.ingestion_runs` (
  run_id STRING NOT NULL,
  source STRING NOT NULL,
  requested_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  status STRING,
  raw_uri STRING,
  row_count INT64,
  error_message STRING
);

CREATE TABLE IF NOT EXISTS `hackumass26.raw.menu_observations` (
  observation_id STRING NOT NULL,
  run_id STRING NOT NULL,
  branch_id STRING,
  provider STRING,
  source_item_id STRING,
  item_name STRING,
  variant STRING,
  price_cents INT64,
  currency STRING,
  fulfillment_mode STRING,
  observed_at TIMESTAMP,
  source_url STRING,
  raw_uri STRING
);