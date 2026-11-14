with ranked as (
    select
        *,
        row_number() over (
            partition by provider, branch_id, source_item_id, coalesce(variant, ''), fulfillment_mode
            order by observed_at desc, run_id desc, observation_id desc
        ) as row_number
    from {{ ref('stg_menu_observations') }}
)
select
    observation_id,
    run_id,
    branch_id,
    provider,
    source_item_id,
    item_name,
    variant,
    price_cents,
    currency,
    fulfillment_mode,
    observed_at,
    timestamp_diff(current_timestamp(), observed_at, hour) as age_hours,
    source_url,
    raw_uri
from ranked
where row_number = 1
