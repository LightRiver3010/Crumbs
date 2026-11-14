CREATE SCHEMA IF NOT EXISTS `{project}.receipts` OPTIONS(location='US');
CREATE TABLE IF NOT EXISTS `{project}.receipts.upload_extractions` (
 session_id STRING, upload_id STRING, raw_uri STRING, confirmed_payload STRING, saved_at TIMESTAMP
) CLUSTER BY session_id;
CREATE TABLE IF NOT EXISTS `{project}.receipts.user_orders` (
 session_id STRING, upload_id STRING, order_id STRING, restaurant STRING,
 provider STRING, order_reference STRING, order_date DATE, total_cents INT64,
 currency STRING, items_json STRING, saved_at TIMESTAMP
) CLUSTER BY session_id;
