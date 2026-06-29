-- [query_1]
SELECT COUNT(*) AS active_customers
FROM customers
WHERE status = 'active';

-- [query_2]
SELECT COUNT(*) AS active_customers
FROM accounts
WHERE status = 'active';

-- [query_3]
SELECT month, churn_rate
FROM monthly_metrics
WHERE month BETWEEN '2024-07-01' AND '2024-09-30';

-- [query_4]
SELECT 
  COUNT(*) AS churn_events,
  ROUND(COUNT(*) * 1.0 / (SELECT COUNT(*) FROM customers), 4) AS churn_rate
FROM churn_events
WHERE churn_date BETWEEN '2024-07-01' AND '2024-09-30';
