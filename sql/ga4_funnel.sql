-- Google Merchandise Store GA4 public sample funnel.
-- Run in BigQuery, then export the result to data/processed/ga4_funnel.csv.

DECLARE start_date STRING DEFAULT '20210101';
DECLARE end_date STRING DEFAULT '20210131';

WITH base_events AS (
  SELECT
    user_pseudo_id,
    event_name,
    TIMESTAMP_MICROS(event_timestamp) AS event_ts
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_date AND end_date
    AND event_name IN ('view_item', 'add_to_cart', 'begin_checkout', 'purchase')
),
first_stage_touch AS (
  SELECT
    user_pseudo_id,
    event_name AS stage,
    MIN(event_ts) AS first_stage_ts
  FROM base_events
  GROUP BY 1, 2
),
funnel AS (
  SELECT 'view_item' AS stage, 1 AS stage_order, COUNT(DISTINCT user_pseudo_id) AS users
  FROM first_stage_touch
  WHERE stage = 'view_item'

  UNION ALL

  SELECT 'add_to_cart' AS stage, 2 AS stage_order, COUNT(DISTINCT user_pseudo_id) AS users
  FROM first_stage_touch
  WHERE stage = 'add_to_cart'

  UNION ALL

  SELECT 'begin_checkout' AS stage, 3 AS stage_order, COUNT(DISTINCT user_pseudo_id) AS users
  FROM first_stage_touch
  WHERE stage = 'begin_checkout'

  UNION ALL

  SELECT 'purchase' AS stage, 4 AS stage_order, COUNT(DISTINCT user_pseudo_id) AS users
  FROM first_stage_touch
  WHERE stage = 'purchase'
)
SELECT
  stage,
  users,
  SAFE_DIVIDE(users, LAG(users) OVER (ORDER BY stage_order)) AS step_conversion_rate,
  1 - SAFE_DIVIDE(users, LAG(users) OVER (ORDER BY stage_order)) AS dropoff_rate
FROM funnel
ORDER BY stage_order;

