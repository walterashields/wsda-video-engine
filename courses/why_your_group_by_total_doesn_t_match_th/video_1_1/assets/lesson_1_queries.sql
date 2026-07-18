-- ===========================================================================
-- Lesson: The Mismatch Moment — Setting Up the Problem You Will Solve
-- 
-- Scenario: Our "orders" table contains individual orders with totals.
-- A dashboard report was built from a separate summary table that was
-- snapshotted at a different time. Some orders arrived AFTER the dashboard
-- snapshot, so the live query produces different (higher) totals than the
-- dashboard shows. This is the "mismatch moment" we need to diagnose.
-- ===========================================================================

-- Individual customer orders with region assignments
CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    order_date     TEXT NOT NULL,
    customer_name  TEXT NOT NULL,
    region         TEXT NOT NULL,
    order_total    REAL NOT NULL
);

-- The dashboard's frozen snapshot of regional totals (taken end-of-day 2024-03-14)
CREATE TABLE dashboard_snapshot (
    region         TEXT PRIMARY KEY,
    reported_total REAL NOT NULL,
    snapshot_date  TEXT NOT NULL
);

-- Seed realistic order data — note that some orders have dates AFTER the
-- dashboard snapshot date of 2024-03-14, which is the root cause of the gap.
INSERT INTO orders (order_id, order_date, customer_name, region, order_total) VALUES
    (1001, '2024-03-01', 'Greenleaf Corp',       'Northeast', 4250.00),
    (1002, '2024-03-03', 'Birchwood LLC',         'West',      1875.50),
    (1003, '2024-03-05', 'Redstone Industries',   'South',     3120.75),
    (1004, '2024-03-07', 'Maple & Sons',          'Northeast', 2980.00),
    (1005, '2024-03-08', 'Pacific Trading Co',    'West',      5430.25),
    (1006, '2024-03-10', 'Sunbelt Logistics',     'South',     1745.00),
    (1007, '2024-03-11', 'Harbor Freight Direct',  'Northeast', 3615.80),
    (1008, '2024-03-12', 'Canyon Partners',       'West',      2290.00),
    (1009, '2024-03-13', 'Evergreen Supply',       'South',     4185.50),
    (1010, '2024-03-14', 'Summit Health Group',    'Northeast', 1520.00),
    -- These three orders arrived AFTER the dashboard snapshot was taken:
    (1011, '2024-03-15', 'Northwind Traders',      'Northeast', 2875.40),
    (1012, '2024-03-16', 'Coastal Dynamics',       'West',      3310.00),
    (1013, '2024-03-17', 'Delta Farms Inc',        'South',     1960.25);

-- Dashboard snapshot totals — these only reflect orders through 2024-03-14
INSERT INTO dashboard_snapshot (region, reported_total, snapshot_date) VALUES
    ('Northeast', 12365.80, '2024-03-14'),
    ('West',       9595.75, '2024-03-14'),
    ('South',      9051.25, '2024-03-14');


-- ===========================================================================
-- TEACHING QUERIES
-- ===========================================================================

-- [live_totals_by_region]
-- The instructor's first move: query the live orders table for regional totals.
-- These numbers will NOT match the dashboard because the table has grown
-- since the snapshot was taken.
SELECT
    region,
    SUM(order_total) AS live_total,
    COUNT(*)         AS order_count
FROM orders
GROUP BY region
ORDER BY region;

-- [dashboard_vs_live_comparison]
-- Place the dashboard's frozen totals next to the live totals in one result
-- set so the gap is immediately visible on screen.
SELECT
    d.region,
    d.reported_total   AS dashboard_total,
    SUM(o.order_total) AS live_total,
    ROUND(SUM(o.order_total) - d.reported_total, 2) AS gap
FROM dashboard_snapshot d
JOIN orders o ON o.region = d.region
GROUP BY d.region
ORDER BY d.region;

-- [orders_causing_the_gap]
-- Isolate the specific rows responsible: orders that arrived AFTER the
-- dashboard snapshot date. This is the "aha" moment — the mismatch is
-- caused by late-arriving data, not a formula error.
SELECT
    o.order_id,
    o.order_date,
    o.customer_name,
    o.region,
    o.order_total
FROM orders o
JOIN dashboard_snapshot d ON d.region = o.region
WHERE o.order_date > d.snapshot_date
ORDER BY o.order_date;

-- [corrected_totals_matching_snapshot]
-- Reproduce the dashboard's numbers exactly by filtering to the same
-- date window the snapshot used. This confirms the root cause and
-- sets up the lesson's next chapter: how to prevent this drift.
SELECT
    region,
    SUM(order_total) AS corrected_total
FROM orders
WHERE order_date <= '2024-03-14'
GROUP BY region
ORDER BY region;