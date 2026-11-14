-- SCAFFOLD ONLY: requires a chosen, mapped dataset; not executed by the app.
-- Create benchmark_staging and benchmarks datasets in the project's US location first.
-- Expected input columns are documented in benchmark_data/README.md.
CREATE OR REPLACE TABLE `{project}.benchmarks.order_metrics` AS
SELECT dataset_version, category, currency, COUNT(*) sample_size,
AVG(total_cents) average_total_cents,
APPROX_QUANTILES(total_cents,100)[OFFSET(50)] median_total_cents
FROM `{project}.benchmark_staging.orders`
WHERE total_cents >= 0 AND currency IS NOT NULL
GROUP BY dataset_version, category, currency;
