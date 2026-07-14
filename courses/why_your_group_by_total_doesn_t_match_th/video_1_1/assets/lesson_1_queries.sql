-- ============================================================
-- LESSON: Three reasons your GROUP BY total never matches the dashboard
-- Focus: Fan-out joins inflating totals & metric definition drift
-- ============================================================

-- Orders table: each row is one customer order with a pre-computed total
CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    region       TEXT NOT NULL,
    order_date   TEXT NOT NULL,
    order_total  REAL NOT NULL
);

-- Order line items: each order can have multiple items (one-to-many)
CREATE TABLE order_items (
    item_id         INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id),
    product_name    TEXT NOT NULL,
    line_item_price REAL NOT NULL,
    quantity        INTEGER NOT NULL,
    discount        REAL NOT NULL DEFAULT 0.0
);

-- ============================================================
-- SEED DATA — 8 orders, 18 line items (some orders have 2-3 items)
-- ============================================================

INSERT INTO orders (order_id, region, order_date, order_total) VALUES
(1001, 'West',      '2024-11-02', 274.50),
(1002, 'East',      '2024-11-03', 189.00),
(1003, 'West',      '2024-11-05', 412.75),
(1004, 'Central',   '2024-11-06', 97.20),
(1005, 'East',      '2024-11-08', 335.60),
(1006, 'Central',   '2024-11-10', 158.40),
(1007, 'West',      '2024-11-12', 89.99),
(1008, 'East',      '2024-11-14', 223.10);

INSERT INTO order_items (item_id, order_id, product_name, line_item_price, quantity, discount) VALUES
-- Order 1001: 3 items → order_total will be counted 3× in naive join
(1, 1001, 'Bluetooth Speaker',    54.50, 1, 0.00),
(2, 1001, 'USB-C Hub',            39.99, 2, 5.48),
(3, 1001, 'Phone Case',           22.00, 1, 0.00),
-- Order 1002: 2 items
(4, 1002, 'Wireless Mouse',       34.50, 2, 0.00),
(5, 1002, 'Laptop Stand',        120.00, 1, 0.00),
-- Order 1003: 3 items
(6, 1003, 'Mechanical Keyboard', 149.99, 1, 12.00),
(7, 1003, 'Desk Mat',             29.99, 2, 0.00),
(8, 1003, 'Monitor Arm',          89.90, 1, 5.00),  -- note: discount applied
-- Order 1004: 1 item (no fan-out for this order)
(9, 1004, 'HDMI Cable',           12.15, 8, 0.00),
-- Order 1005: 2 items
(10, 1005, 'Webcam HD',           79.80, 1, 0.00),
(11, 1005, 'Ring Light',          42.50, 3, 4.90),
-- Order 1006: 3 items
(12, 1006, 'Notebook Pack',       14.70, 3, 0.00),
(13, 1006, 'Gel Pens Set',         8.50, 2, 0.00),
(14, 1006, 'Desk Organizer',      45.00, 1, 0.00),
-- Order 1007: 1 item
(15, 1007, 'Screen Protector',    14.99, 1, 0.00),
(16, 1007, 'Phone Charger',       37.50, 2, 0.00),
-- Order 1008: 2 items
(17, 1008, 'USB Drive 128GB',     18.55, 3, 0.00),
(18, 1008, 'Ethernet Adapter',    34.99, 1, 0.00);


-- ============================================================
-- TEACHING QUERIES
-- ============================================================

-- [fanout_wrong]
-- CULPRIT 1 — The naive join duplicates order rows.
-- Each order row is repeated once per line item, so SUM(order_total)
-- counts an order's total 2× or 3× depending on how many items it has.
-- The TRUE grand total is 1,780.54. Watch it balloon to ~4,100+.
SELECT
    o.region,
    COUNT(*)             AS row_count,
    SUM(o.order_total)   AS inflated_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.region
ORDER BY o.region;


-- [fanout_fixed]
-- FIX: Pre-aggregate orders before joining, so each order is counted once.
-- The subquery gives the true region totals that match the dashboard.
SELECT
    agg.region,
    agg.order_count,
    agg.true_revenue,
    COUNT(oi.item_id)    AS line_item_count
FROM (
    SELECT
        region,
        COUNT(*)           AS order_count,
        SUM(order_total)   AS true_revenue
    FROM orders
    GROUP BY region
) agg
JOIN orders o  ON o.region = agg.region
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY agg.region, agg.order_count, agg.true_revenue
ORDER BY agg.region;


-- [metric_drift_order_total]
-- CULPRIT 3 — Metric definition drift.
-- The "order_total" column was snapshotted at checkout time.
-- The dashboard, however, computes revenue as SUM(price * qty - discount).
-- These two numbers WILL differ if discounts or pricing adjustments exist.
-- Version A: uses the stored order_total (what your SQL usually grabs)
SELECT
    o.region,
    SUM(o.order_total) AS revenue_from_order_total
FROM orders o
GROUP BY o.region
ORDER BY o.region;


-- [metric_drift_line_math]
-- Version B: uses the line-item math the dashboard actually computes.
-- Compare these numbers to the query above — they don't match.
-- This IS the official metric: SUM(line_item_price * quantity - discount).
-- Until your SQL uses the same formula, your totals will always diverge.
SELECT
    o.region,
    ROUND(SUM(oi.line_item_price * oi.quantity - oi.discount), 2)
        AS revenue_from_line_items
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.region
ORDER BY o.region;