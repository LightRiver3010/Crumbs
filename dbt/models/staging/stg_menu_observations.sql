select
    observation_id,
    run_id,
    branch_id,
    provider,
    source_item_id,
    nullif(trim(item_name), '') as item_name,
    nullif(trim(variant), '') as variant,
    price_cents,
    currency,
    fulfillment_mode,
    observed_at,
    source_url,
    raw_uri
from {{ source('raw', 'menu_observations') }}
where observation_id is not null
  and run_id is not null
  and price_cents >= 0
  and currency = 'USD'
