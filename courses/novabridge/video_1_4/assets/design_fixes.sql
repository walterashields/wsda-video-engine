-- [view_revenue]
-- ╔══════════════════════════════════════════════════════════════╗
-- ║  VIEW: canonical_revenue                                     ║
-- ║  CANONICAL SOURCE — use this for all revenue queries         ║
-- ╚══════════════════════════════════════════════════════════════╝
--
-- Source:      orders table (full order total, includes tax)
-- DO NOT USE:  order_summary  — excludes returns, different scope
-- DO NOT USE:  order_details  — pre-tax line items, different granularity
-- Owner:       data-engineering@novabridge.com
-- Updated:     2024-01-15

CREATE VIEW IF NOT EXISTS canonical_revenue AS
SELECT
    region,
    SUM(order_total)  AS total_revenue,
    COUNT(*)          AS order_count
FROM orders
GROUP BY region
ORDER BY total_revenue DESC;

-- [view_churn]
-- ╔══════════════════════════════════════════════════════════════╗
-- ║  VIEW: canonical_churn                                       ║
-- ║  CANONICAL SOURCE — use this for all churn rate queries      ║
-- ╚══════════════════════════════════════════════════════════════╝
--
-- Methodology: distinct churned customers / total active at period start
-- Source:      churn_events table (raw events, exact date precision)
-- DO NOT USE:  monthly_metrics.churn_rate
--              Reason: pre-aggregated, rolling 30-day window,
--                      different denominator than point-in-time count
-- Owner:       analytics@novabridge.com

CREATE VIEW IF NOT EXISTS canonical_churn AS
SELECT
    strftime('%Y-%m', churn_date)  AS month,
    COUNT(*)                        AS churned_customers,
    ROUND(COUNT(*) * 1.0 /
        (SELECT COUNT(*) FROM customers WHERE status = 'active'), 4)
                                    AS churn_rate
FROM churn_events
GROUP BY strftime('%Y-%m', churn_date)
ORDER BY month;

-- [view_customers]
-- ╔══════════════════════════════════════════════════════════════╗
-- ║  VIEW: canonical_customers                                   ║
-- ║  CANONICAL SOURCE — use this for active customer counts      ║
-- ╚══════════════════════════════════════════════════════════════╝
--
-- Definition:  paying customers with status = 'active' ONLY
-- Source:      customers table
-- DO NOT USE:  prospects table
--              Reason: includes leads and trials, not paying customers
-- Owner:       revenue@novabridge.com

CREATE VIEW IF NOT EXISTS canonical_customers AS
SELECT COUNT(*) AS active_customers
FROM customers
WHERE status = 'active';

-- [query_revenue]
SELECT region, total_revenue, order_count
FROM canonical_revenue;
