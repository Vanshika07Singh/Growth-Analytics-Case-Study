-- Simple day-1/day-7 cohort retention from the GA4 public ecommerce sample.
-- Run in BigQuery, then export the result to data/processed/ga4_retention.csv.

DECLARE start_date STRING DEFAULT '20210101';
DECLARE end_date STRING DEFAULT '20210131';

WITH daily_user_activity AS (
  SELECT DISTINCT
    user_pseudo_id,
    PARSE_DATE('%Y%m%d', event_date) AS activity_date
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_date AND end_date
),
cohorts AS (
  SELECT
    user_pseudo_id,
    MIN(activity_date) AS cohort_date
  FROM daily_user_activity
  GROUP BY 1
),
retention AS (
  SELECT
    cohorts.cohort_date,
    DATE_DIFF(daily_user_activity.activity_date, cohorts.cohort_date, DAY) AS days_since_first_visit,
    COUNT(DISTINCT cohorts.user_pseudo_id) AS retained_users
  FROM cohorts
  JOIN daily_user_activity
    USING (user_pseudo_id)
  WHERE DATE_DIFF(daily_user_activity.activity_date, cohorts.cohort_date, DAY) IN (0, 1, 7)
  GROUP BY 1, 2
),
cohort_sizes AS (
  SELECT
    cohort_date,
    COUNT(DISTINCT user_pseudo_id) AS cohort_users
  FROM cohorts
  GROUP BY 1
)
SELECT
  retention.cohort_date,
  retention.days_since_first_visit,
  cohort_sizes.cohort_users,
  retention.retained_users,
  SAFE_DIVIDE(retention.retained_users, cohort_sizes.cohort_users) AS retention_rate
FROM retention
JOIN cohort_sizes
  USING (cohort_date)
ORDER BY cohort_date, days_since_first_visit;

