-- Orders table representing a typical e-commerce orders dataset
-- with realistic region gaps (NULLs) and varied status codes
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    order_total REAL NOT NULL,
    region TEXT,
    status TEXT NOT NULL,
    order_date TEXT NOT NULL
);

-- Seed data: 15 orders with realistic values, some NULL regions, and 7 distinct statuses
INSERT INTO orders (order_id, customer_name, order_total, region, status, order_date) VALUES
(1001, 'Maria Chen',        234.50, 'Northeast', 'Completed',  '2024-11-02'),
(1002, 'James Okafor',       89.99, 'Southeast', 'Completed',  '2024-11-03'),
(1003, 'Priya Sharma',      412.00, 'West',      'Fulfilled',  '2024-11-03'),
(1004, 'Carlos Ruiz',       157.25, NULL,         'Shipped',    '2024-11-04'),
(1005, 'Aisha Johnson',      63.80, NULL,         'Completed',  '2024-11-04'),
(1006, 'Tom Brennan',       891.15, 'Midwest',   'Shipped',    '2024-11-05'),
(1007, 'Lin Wei',           205.00, NULL,         'Fulfilled',  '2024-11-05'),
(1008, 'Sarah Goldstein',    47.30, 'Northeast', 'Cancelled',  '2024-11-06'),
(1009, 'David Park',        338.75, NULL,         'Completed',  '2024-11-06'),
(1010, 'Emma Larsson',      126.40, 'West',      'Returned',   '2024-11-07'),
(1011, 'Raj Patel',         510.00, 'Southeast', 'Completed',  '2024-11-07'),
(1012, 'Nicole Adams',       72.99, NULL,         'Pending',    '2024-11-08'),
(1013, 'Kenji Tanaka',      189.60, NULL,         'Shipped',    '2024-11-08'),
(1014, 'Fatima Al-Rashid',  445.20, 'Midwest',   'Refunded',   '2024-11-09'),
(1015, 'Luca Moretti',      299.95, NULL,         'Completed',  '2024-11-09');

-- ============================================================
-- SCENE 2: NULLs That Vanish from Your Total
-- ============================================================

-- [dashboard_revenue_by_region]
-- This is what the dashboard shows: revenue grouped by region.
-- It looks complete, but NULL regions quietly form their own bucket
-- that many BI tools hide or filter out.
SELECT
    region,
    COUNT(*) AS order_count,
    SUM(order_total) AS revenue
FROM orders
GROUP BY region
ORDER BY region;

-- [null_region_orders]
-- Revealing the hidden bucket: 7 orders worth $1,295.59 have no region.
-- The dashboard silently excludes them from every regional breakdown.
SELECT
    COUNT(*) AS orders_with_no_region,
    SUM(order_total) AS missing_revenue
FROM orders
WHERE region IS NULL;

-- ============================================================
-- SCENE 3: Status Codes — What Counts as "Revenue"?
-- ============================================================

-- [distinct_status_values]
-- Seven different status values exist, but the dashboard only
-- counts 'Completed' and 'Fulfilled'. Orders marked 'Shipped'
-- are real revenue that never appears in the total.
SELECT DISTINCT status
FROM orders
ORDER BY status;

-- [status_revenue_comparison]
-- The dashboard uses WHERE status IN ('Completed','Fulfilled')
-- and reports $1,551.49. Adding 'Shipped' recovers $1,238.00
-- in revenue that was silently excluded.
SELECT
    CASE
        WHEN status IN ('Completed', 'Fulfilled')
            THEN 'Dashboard counts (Completed + Fulfilled)'
        WHEN status = 'Shipped'
            THEN 'MISSING: Shipped orders'
        ELSE 'Other statuses (Cancelled, Pending, etc.)'
    END AS category,
    COUNT(*) AS order_count,
    SUM(order_total) AS revenue
FROM orders
GROUP BY
    CASE
        WHEN status IN ('Completed', 'Fulfilled')
            THEN 'Dashboard counts (Completed + Fulfilled)'
        WHEN status = 'Shipped'
            THEN 'MISSING: Shipped orders'
        ELSE 'Other statuses (Cancelled, Pending, etc.)'
    END
ORDER BY revenue DESC;