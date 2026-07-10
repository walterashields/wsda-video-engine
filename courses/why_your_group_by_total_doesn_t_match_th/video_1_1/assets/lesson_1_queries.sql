-- ===========================================================================
-- Lesson: Diagnosing the five silent reasons your GROUP BY total drifts
--         from the dashboard
-- ===========================================================================

-- Orders table: core transactional data
CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    region         TEXT NOT NULL,
    order_date     TEXT NOT NULL,          -- stored as UTC timestamp
    gross_revenue  REAL NOT NULL,
    subtotal       REAL NOT NULL,
    discount_amount REAL,                  -- nullable on purpose
    refund_amount  REAL NOT NULL DEFAULT 0,
    is_test_order  INTEGER NOT NULL DEFAULT 0,  -- 1 = internal test
    status         TEXT NOT NULL DEFAULT 'completed'
);

-- Shipments table: one order can have multiple shipments (split-ship)
CREATE TABLE shipments (
    shipment_id  INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    shipped_date TEXT,
    carrier      TEXT
);

-- ----- Seed: orders (15 rows spanning late Dec 2023 – Jan 2024) ----------

INSERT INTO orders (order_id, region, order_date, gross_revenue, subtotal, discount_amount, refund_amount, is_test_order, status) VALUES
-- January orders (UTC timestamps — some fall on Dec 31 or Feb 1 in ET)
(1001, 'Northeast', '2024-01-01 03:14:00', 42750.00, 40125.00, 2625.00, 0,       0, 'completed'),
(1002, 'West',      '2024-01-03 18:45:00', 31280.50, 29450.00, 1830.50, 0,       0, 'completed'),
(1003, 'Southeast', '2024-01-05 12:30:00', 18990.00, 17500.00, NULL,     0,       0, 'completed'),
(1004, 'Midwest',   '2024-01-07 22:05:00', 67425.00, 63800.00, 3625.00, 4200.00, 0, 'completed'),
(1005, 'West',      '2024-01-10 14:22:00', 53190.75, 50100.00, 3090.75, 0,       0, 'completed'),
(1006, 'Northeast', '2024-01-12 09:58:00', 29475.00, 27800.00, 1675.00, 2950.00, 0, 'completed'),
(1007, 'Southeast', '2024-01-15 16:33:00', 88320.00, 83500.00, 4820.00, 0,       0, 'completed'),
(1008, 'Midwest',   '2024-01-18 01:10:00', 14760.00, 13900.00, 860.00,  0,       0, 'completed'),
(1009, 'West',      '2024-01-20 20:47:00', 105640.00,99800.00, 5840.00, 8500.00, 0, 'completed'),
(1010, 'Northeast', '2024-01-22 11:15:00', 73250.00, 69100.00, 4150.00, 0,       0, 'completed'),
(1011, 'Southeast', '2024-01-25 07:42:00', 46890.00, 44200.00, NULL,     0,       0, 'completed'),
-- Test / refunded rows the dashboard silently excludes
(1012, 'West',      '2024-01-08 13:00:00', 99999.00, 94000.00, 5999.00, 0,       1, 'completed'),   -- test order
(1013, 'Northeast', '2024-01-14 10:20:00', 54350.00, 51200.00, 3150.00, 54350.00,0, 'refunded'),     -- fully refunded
-- Boundary orders: UTC timestamp is Jan but ET equivalent is Dec 31 or Feb 1
(1014, 'Midwest',   '2024-01-01 02:30:00', 38740.00, 36500.00, 2240.00, 0,       0, 'completed'),   -- 9:30 PM Dec 31 ET
(1015, 'Southeast', '2024-02-01 04:15:00', 27580.00, 26000.00, 1580.00, 0,       0, 'completed');   -- 11:15 PM Jan 31 ET

-- ----- Seed: shipments (some orders have 2-3 shipments = row inflation) ---

INSERT INTO shipments (shipment_id, order_id, shipped_date, carrier) VALUES
(5001, 1001, '2024-01-02', 'FedEx'),
(5002, 1002, '2024-01-04', 'UPS'),
(5003, 1002, '2024-01-05', 'UPS'),           -- 2nd shipment
(5004, 1003, '2024-01-06', 'USPS'),
(5005, 1004, '2024-01-08', 'FedEx'),
(5006, 1004, '2024-01-09', 'FedEx'),         -- 2nd shipment
(5007, 1004, '2024-01-10', 'FedEx'),         -- 3rd shipment
(5008, 1005, '2024-01-11', 'UPS'),
(5009, 1006, '2024-01-13', 'FedEx'),
(5010, 1007, '2024-01-16', 'UPS'),
(5011, 1007, '2024-01-17', 'USPS'),          -- 2nd shipment
(5012, 1008, '2024-01-19', 'USPS'),
(5013, 1009, '2024-01-21', 'FedEx'),
(5014, 1009, '2024-01-22', 'FedEx'),         -- 2nd shipment
(5015, 1010, '2024-01-23', 'UPS'),
(5016, 1011, '2024-01-26', 'UPS'),
(5017, 1012, '2024-01-09', 'FedEx'),         -- test order shipment
(5018, 1013, '2024-01-15', 'UPS'),           -- refunded order shipment
(5019, 1014, '2024-01-02', 'USPS'),
(5020, 1015, '2024-02-02', 'FedEx');


-- ===========================================================================
-- SCENE 1: Reproducing the mismatch
-- ===========================================================================

-- [scene1_group_by_total]
-- Naïve GROUP BY on all orders in the date range — produces $1,247,830.25
-- This is what the analyst runs. The dashboard shows $1,093,412.00.
SELECT
    region,
    SUM(gross_revenue) AS region_revenue
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
GROUP BY region

UNION ALL

SELECT
    '** GRAND TOTAL **' AS region,
    SUM(gross_revenue)  AS region_revenue
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01';


-- ===========================================================================
-- SCENE 2: Cause 1 — Duplicate rows from joins (row inflation)
-- ===========================================================================

-- [scene2a_inflated_join]
-- Joining to shipments without deduplication inflates revenue
SELECT
    'Inflated (COUNT *)' AS label,
    COUNT(*)             AS row_count,
    SUM(o.gross_revenue) AS total_revenue
FROM orders o
JOIN shipments s ON s.order_id = o.order_id
WHERE o.order_date >= '2024-01-01'
  AND o.order_date <  '2024-02-01';

-- [scene2b_distinct_check]
-- COUNT(*) vs COUNT(DISTINCT order_id) exposes the inflation
SELECT
    COUNT(*)                    AS total_rows,
    COUNT(DISTINCT o.order_id)  AS distinct_orders,
    COUNT(*) - COUNT(DISTINCT o.order_id) AS extra_rows
FROM orders o
JOIN shipments s ON s.order_id = o.order_id
WHERE o.order_date >= '2024-01-01'
  AND o.order_date <  '2024-02-01';

-- ===========================================================================
-- SCENE 2 continued: Cause 2 — Filter gaps (test orders & refunds)
-- ===========================================================================

-- [scene2c_filter_gap_visible]
-- Show the rows the dashboard excludes but our query includes
SELECT
    order_id,
    region,
    gross_revenue,
    is_test_order,
    status
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND (is_test_order = 1 OR status = 'refunded');

-- [scene2d_filtered_total]
-- After excluding test orders and refunded rows, total drops significantly
SELECT
    region,
    SUM(gross_revenue) AS region_revenue
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded'
GROUP BY region

UNION ALL

SELECT
    '** GRAND TOTAL **',
    SUM(gross_revenue)
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded';


-- ===========================================================================
-- SCENE 3: Cause 3 — NULLs silently excluded from aggregation
-- ===========================================================================

-- [scene3a_sum_with_nulls]
-- SUM(discount_amount) silently skips NULL rows
SELECT
    COUNT(*)                AS total_rows,
    COUNT(discount_amount)  AS rows_with_discount,
    SUM(discount_amount)    AS total_discount_ignoring_nulls
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded';

-- [scene3b_show_null_rows]
-- Reveal the rows where discount_amount IS NULL
SELECT
    order_id,
    region,
    gross_revenue,
    discount_amount
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded'
  AND discount_amount IS NULL;

-- [scene3c_coalesce_fix]
-- COALESCE treats NULLs as zero — total shifts
SELECT
    COUNT(*)                                  AS total_rows,
    SUM(COALESCE(discount_amount, 0))         AS total_discount_with_coalesce,
    SUM(discount_amount)                      AS total_discount_without_coalesce,
    SUM(COALESCE(discount_amount, 0))
      - COALESCE(SUM(discount_amount), 0)     AS difference
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded';


-- ===========================================================================
-- SCENE 4: Cause 4 — Time zone boundary shift
-- ===========================================================================

-- [scene4a_utc_vs_eastern]
-- Show orders whose calendar date changes when converted from UTC to US/Eastern
-- SQLite doesn't have full TZ support, so we simulate ET as UTC-5
SELECT
    order_id,
    order_date                                          AS utc_timestamp,
    datetime(order_date, '-5 hours')                    AS eastern_timestamp,
    strftime('%Y-%m-%d', order_date)                    AS utc_date,
    strftime('%Y-%m-%d', datetime(order_date, '-5 hours')) AS eastern_date,
    gross_revenue
FROM orders
WHERE is_test_order = 0
  AND status != 'refunded'
  AND strftime('%Y-%m-%d', order_date)
   != strftime('%Y-%m-%d', datetime(order_date, '-5 hours'));

-- [scene4b_boundary_impact]
-- Count and sum orders that shift across the Jan boundary when using ET
SELECT
    'Orders shifting OUT of January (UTC Jan → ET Dec/Feb)' AS direction,
    COUNT(*)          AS order_count,
    SUM(gross_revenue) AS revenue_impact
FROM orders
WHERE is_test_order = 0
  AND status != 'refunded'
  AND order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND (strftime('%Y-%m-%d', datetime(order_date, '-5 hours')) < '2024-01-01'
    OR strftime('%Y-%m-%d', datetime(order_date, '-5 hours')) >= '2024-02-01')

UNION ALL

SELECT
    'Orders shifting IN to January (UTC outside Jan → ET Jan)' AS direction,
    COUNT(*)          AS order_count,
    SUM(gross_revenue) AS revenue_impact
FROM orders
WHERE is_test_order = 0
  AND status != 'refunded'
  AND (order_date < '2024-01-01' OR order_date >= '2024-02-01')
  AND strftime('%Y-%m-%d', datetime(order_date, '-5 hours')) >= '2024-01-01'
  AND strftime('%Y-%m-%d', datetime(order_date, '-5 hours')) <  '2024-02-01';


-- ===========================================================================
-- SCENE 4 continued: Cause 5 — Metric definition drift
-- ===========================================================================

-- [scene4c_metric_definition_drift]
-- The SQL analyst uses gross_revenue; the dashboard defines revenue as
-- subtotal - refund_amount.  Show the gap side by side.
SELECT
    region,
    SUM(gross_revenue)                        AS sql_analyst_revenue,
    SUM(subtotal - refund_amount)             AS dashboard_revenue,
    SUM(gross_revenue)
      - SUM(subtotal - refund_amount)         AS definition_gap
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded'
GROUP BY region

UNION ALL

SELECT
    '** GRAND TOTAL **',
    SUM(gross_revenue),
    SUM(subtotal - refund_amount),
    SUM(gross_revenue) - SUM(subtotal - refund_amount)
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date <  '2024-02-01'
  AND is_test_order = 0
  AND status != 'refunded';

-- [scene4d_final_matching_query]
-- The fully corrected query that matches the dashboard: $1,093,412
-- Uses ET date range, excludes test/refunded, uses dashboard metric
SELECT
    region,
    SUM(subtotal - refund_amount) AS dashboard_revenue
FROM orders
WHERE is_test_order = 0
  AND status != 'refunded'
  AND datetime(order_date, '-5 hours') >= '2024-01-01 00:00:00'
  AND datetime(order_date, '-5 hours') <  '2024-02-01 00:00:00'
GROUP BY region

UNION ALL

SELECT
    '** GRAND TOTAL **',
    SUM(subtotal - refund_amount)
FROM orders
WHERE is_test_order = 0
  AND status != 'refunded'
  AND datetime(order_date, '-5 hours') >= '2024-01-01 00:00:00'
  AND datetime(order_date, '-5 hours') <  '2024-02-01 00:00:00';