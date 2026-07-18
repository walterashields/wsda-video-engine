-- =============================================================
-- Lesson: Metric Definitions and the Capstone Debugging Exercise
-- =============================================================

-- Orders table: each row is one customer order
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    order_total REAL NOT NULL,
    discount REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed'
);

-- Order items table: line items within each order (one order can have multiple items)
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Refunds table: some orders were partially or fully refunded
CREATE TABLE refunds (
    refund_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    refund_date TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Regions table: maps customers to sales regions
CREATE TABLE regions (
    customer_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL
);

-- -------------------------------------------------------
-- Seed data: orders for Q1 2024
-- -------------------------------------------------------
INSERT INTO orders (order_id, customer_id, order_date, order_total, discount, tax, status) VALUES
(1001, 10, '2024-01-05', 12450.00, 1245.00, 1008.45, 'completed'),
(1002, 11, '2024-01-12', 8720.50,  436.03,  745.30,  'completed'),
(1003, 12, '2024-01-19', 34500.00, 3450.00, 2794.50, 'completed'),
(1004, 13, '2024-01-28', 6890.00,  0.00,    620.10,  'completed'),
(1005, 14, '2024-02-03', 45200.00, 6780.00, 3457.80, 'completed'),
(1006, 15, '2024-02-14', 19300.00, 1930.00, 1563.30, 'completed'),
(1007, 10, '2024-02-22', 27650.00, 2765.00, 2239.65, 'completed'),
(1008, 16, '2024-03-01', 15800.00, 790.00,  1351.90, 'completed'),
(1009, 17, '2024-03-08', 52100.00, 7815.00, 3985.65, 'completed'),
(1010, 18, '2024-03-15', 9480.00,  474.00,  810.54,  'completed'),
(1011, 11, '2024-03-22', 41500.00, 4150.00, 3361.50, 'completed'),
(1012, 19, '2024-03-29', 22750.00, 2275.00, 1842.75, 'cancelled'),
(1013, 20, '2024-03-30', 18230.00, 1823.00, 1476.63, 'completed'),
(1014, 14, '2024-03-31', 33210.00, 4981.50, 2540.57, 'completed');

-- Order items — some orders have multiple items (this creates the JOIN duplication trap)
INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) VALUES
(1,  1001, 201, 3,  2500.00),
(2,  1001, 202, 1,  4950.00),
(3,  1002, 203, 2,  4360.25),
(4,  1003, 201, 10, 3450.00),
(5,  1004, 204, 1,  6890.00),
(6,  1005, 205, 4,  8500.00),
(7,  1005, 206, 2,  4600.00),
(8,  1006, 207, 1, 19300.00),
(9,  1007, 201, 5,  3800.00),
(10, 1007, 208, 2,  4825.00),
(11, 1008, 209, 2,  7900.00),
(12, 1009, 205, 6,  8683.33),
(13, 1010, 210, 3,  3160.00),
(14, 1011, 201, 8,  3500.00),
(15, 1011, 211, 3,  4166.67),
(16, 1012, 212, 5,  4550.00),
(17, 1013, 213, 1, 18230.00),
(18, 1014, 205, 3,  7800.00),
(19, 1014, 214, 2,  5505.00);

-- Refunds
INSERT INTO refunds (refund_id, order_id, refund_amount, refund_date) VALUES
(1, 1003, 6900.00, '2024-02-10'),
(2, 1006, 4825.00, '2024-03-01'),
(3, 1009, 8683.33, '2024-03-20');

-- Region mappings
INSERT INTO regions (customer_id, region) VALUES
(10, 'North'), (11, 'South'), (12, 'North'), (13, 'East'),
(14, 'West'),  (15, 'South'), (16, 'East'),  (17, 'West'),
(18, 'North'), (19, 'South'), (20, 'East');


-- =============================================================
-- SCENE 1: Revenue vs Gross Revenue vs Net Revenue
-- Same word — three very different numbers.
-- =============================================================

-- [gross_revenue]
-- Gross revenue: raw order totals before any deductions
SELECT
    'Gross Revenue' AS metric,
    SUM(order_total) AS total
FROM orders
WHERE status = 'completed';

-- [net_revenue]
-- Net revenue: after discounts but before tax deductions
-- And net-net revenue: after both discounts and taxes
-- Shows how the same word "Revenue" can mean three things
SELECT
    'Gross Revenue'    AS metric,
    SUM(order_total)   AS total
FROM orders
WHERE status = 'completed'
UNION ALL
SELECT
    'Net Revenue (after discounts)',
    SUM(order_total - discount)
FROM orders
WHERE status = 'completed'
UNION ALL
SELECT
    'Net-Net Revenue (after discounts & tax)',
    SUM(order_total - discount - tax)
FROM orders
WHERE status = 'completed';


-- =============================================================
-- SCENE 3: Capstone Debugging Exercise
-- The "broken" query has FIVE bugs that inflate the result.
-- Bug 1: JOIN to order_items duplicates orders with multiple items
-- Bug 2: Missing WHERE status = 'completed' (includes cancelled order 1012)
-- Bug 3: Uses order_total instead of (order_total - discount) — wrong metric
-- Bug 4: No date filter — should be Q1 completed only, already covered
-- Bug 5: Doesn't subtract refunds
--
-- We show the broken query, then the fixed query.
-- =============================================================

-- [capstone_broken_query]
-- THE BROKEN QUERY — produces an inflated total
-- (This is what the learner sees in capstone_start.sql)
-- Problems:
--   1. JOIN to order_items duplicates multi-item orders
--   2. Includes cancelled orders (no status filter)
--   3. Uses gross order_total, not net (order_total - discount)
--   4. Doesn't subtract refunds
--   5. Date range is missing (minor here since all data is Q1, but
--      the cancelled order and metric choice cause the big gap)
SELECT
    'Broken Dashboard Revenue' AS label,
    SUM(o.order_total) AS reported_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id;


-- [capstone_fixed_query]
-- THE CORRECTED QUERY — matches the expected dashboard number
-- Fixes applied:
--   1. Removed the JOIN to order_items (eliminates duplicates)
--   2. Added WHERE status = 'completed'
--   3. Uses (order_total - discount) for net revenue
--   4. Subtracts refunds with a correlated subquery
--   5. Explicit date range for Q1 2024
SELECT
    'Corrected Net Revenue (Q1 2024)' AS label,
    SUM(
        (o.order_total - o.discount)
        - COALESCE((SELECT SUM(r.refund_amount)
                     FROM refunds r
                     WHERE r.order_id = o.order_id), 0)
    ) AS actual_revenue
FROM orders o
WHERE o.status = 'completed'
  AND o.order_date >= '2024-01-01'
  AND o.order_date < '2024-04-01';