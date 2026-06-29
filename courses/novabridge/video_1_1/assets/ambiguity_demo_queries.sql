-- NovaBridge Analytics — Ambiguity Demo Queries
-- Video 1.1: Three Tables, One Question
-- DO NOT EDIT — exercise file for automated playback

-- [query_1] Revenue by region from orders table
SELECT
    region,
    SUM(order_total) AS total_revenue
FROM orders
GROUP BY region
ORDER BY total_revenue DESC;

-- [query_2] Revenue by region from order_summary table
SELECT
    region,
    SUM(summary_total) AS total_revenue
FROM order_summary
GROUP BY region
ORDER BY total_revenue DESC;

-- [query_3] Revenue by region from order_details table
SELECT
    region,
    SUM(unit_price * quantity) AS total_revenue
FROM order_details od
JOIN orders o ON od.order_id = o.order_id
GROUP BY region
ORDER BY total_revenue DESC;
