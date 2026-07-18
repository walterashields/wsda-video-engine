-- ============================================================
-- Lesson: Date Ranges and Timezone Traps
-- When Tuesday is Still Monday
-- ============================================================

-- Orders table with datetime timestamps (not just dates)
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_total REAL    NOT NULL,
    order_date  TEXT    NOT NULL  -- stored as datetime string
);

-- Orders table with explicit UTC timestamps for timezone lesson
CREATE TABLE orders_utc (
    order_id       INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL,
    order_total    REAL    NOT NULL,
    created_at_utc TEXT    NOT NULL  -- stored as UTC datetime
);

-- ============================================================
-- Seed data for Scene 1: Boundary Problem
-- Several orders land on Jan 31 with times AFTER midnight
-- (i.e., they have a time component like '2024-01-31 14:30:00')
-- and a few land exactly at midnight boundaries.
-- ============================================================

INSERT INTO orders (order_id, customer_id, order_total, order_date) VALUES
(1,  101, 47.50,  '2024-01-01 00:00:00'),
(2,  102, 83.20,  '2024-01-03 09:14:22'),
(3,  103, 19.99,  '2024-01-07 16:45:00'),
(4,  104, 125.00, '2024-01-12 11:30:55'),
(5,  105, 64.75,  '2024-01-18 20:02:10'),
(6,  106, 210.40, '2024-01-22 08:00:00'),
(7,  107, 55.10,  '2024-01-27 23:59:59'),
(8,  108, 92.30,  '2024-01-31 00:00:00'),
(9,  109, 38.60,  '2024-01-31 06:15:00'),
(10, 110, 77.45,  '2024-01-31 14:30:00'),
(11, 111, 153.80, '2024-01-31 19:45:33'),
(12, 112, 41.20,  '2024-01-31 23:58:00');

-- ============================================================
-- Seed data for Scene 2: UTC vs Local Time
-- 14 orders with UTC timestamps between 2024-02-01 00:00 and
-- 2024-02-01 04:59 — these are still Jan 31 in US/Eastern (UTC-5).
-- Plus orders clearly in February even after conversion.
-- ============================================================

INSERT INTO orders_utc (order_id, customer_id, order_total, created_at_utc) VALUES
-- These are Jan 31 Eastern but Feb 1 UTC (the 14 "jumping" orders)
(1,  201, 34.99,  '2024-02-01 00:12:00'),
(2,  202, 89.50,  '2024-02-01 00:45:33'),
(3,  203, 22.10,  '2024-02-01 01:05:00'),
(4,  204, 61.75,  '2024-02-01 01:22:18'),
(5,  205, 45.00,  '2024-02-01 01:50:00'),
(6,  206, 118.30, '2024-02-01 02:10:44'),
(7,  207, 73.20,  '2024-02-01 02:33:00'),
(8,  208, 15.60,  '2024-02-01 02:55:12'),
(9,  209, 99.99,  '2024-02-01 03:08:00'),
(10, 210, 54.40,  '2024-02-01 03:30:00'),
(11, 211, 67.80,  '2024-02-01 03:47:22'),
(12, 212, 130.00, '2024-02-01 04:01:00'),
(13, 213, 28.50,  '2024-02-01 04:15:55'),
(14, 214, 42.90,  '2024-02-01 04:50:00'),
-- These remain in February even after converting to Eastern
(15, 215, 88.10,  '2024-02-01 05:30:00'),
(16, 216, 175.25, '2024-02-01 14:00:00'),
(17, 217, 63.40,  '2024-02-01 18:22:10'),
(18, 218, 97.80,  '2024-02-02 12:00:00'),
(19, 219, 41.15,  '2024-02-03 16:45:00'),
-- Orders clearly in January UTC (and Eastern)
(20, 220, 56.70,  '2024-01-30 15:00:00'),
(21, 221, 82.30,  '2024-01-31 10:00:00'),
(22, 222, 39.90,  '2024-01-31 20:30:00');


-- ============================================================
-- TEACHING QUERIES
-- ============================================================

-- [between_boundary_bug]
-- BUG: BETWEEN with datetime strings misses Jan 31 orders after midnight
-- because '2024-01-31 06:15:00' > '2024-01-31' as a string comparison.
-- Only order_date = '2024-01-31 00:00:00' (exactly) would match.
-- This returns FEWER rows and a LOWER total than expected.
SELECT
    'BETWEEN (buggy)' AS method,
    COUNT(*)           AS order_count,
    ROUND(SUM(order_total), 2) AS revenue
FROM orders
WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31';


-- [half_open_range_fix]
-- FIX: Use a half-open range [start, end).
-- '2024-01-31 23:58:00' < '2024-02-01' is TRUE, so all Jan 31 orders
-- are correctly included regardless of their time component.
SELECT
    'Half-open range (correct)' AS method,
    COUNT(*)                     AS order_count,
    ROUND(SUM(order_total), 2)   AS revenue
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01';


-- [utc_monthly_totals_naive]
-- Naively grouping by UTC month: all 14 late-night Eastern orders
-- are counted in February because their UTC timestamp says Feb 1.
SELECT
    SUBSTR(created_at_utc, 1, 7) AS month_utc,
    COUNT(*)                      AS order_count,
    ROUND(SUM(order_total), 2)    AS revenue
FROM orders_utc
GROUP BY month_utc
ORDER BY month_utc;


-- [utc_to_eastern_fix]
-- After converting UTC → US/Eastern (UTC−5), those 14 orders shift
-- back to January. February's count drops by 14; January's rises by 14.
SELECT
    SUBSTR(datetime(created_at_utc, '-5 hours'), 1, 7) AS month_eastern,
    COUNT(*)                                            AS order_count,
    ROUND(SUM(order_total), 2)                          AS revenue
FROM orders_utc
GROUP BY month_eastern
ORDER BY month_eastern;