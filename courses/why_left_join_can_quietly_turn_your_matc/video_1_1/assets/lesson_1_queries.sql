-- =============================================================
-- Lesson: How LEFT JOIN Quietly Turns Your Matches into NULLs
--         — the WHERE-Clause Trap and How to Fix It
-- =============================================================

-- Customers table: holds customer information
CREATE TABLE customers (
    customer_id  INTEGER,
    customer_name TEXT,
    region        TEXT
);

-- Orders table: holds order/revenue data, references customers
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date  TEXT,
    amount      NUMERIC
);

-- Seed customers
INSERT INTO customers (customer_id, customer_name, region) VALUES
    (101, 'Bright Elm Bakery',    'Northeast'),
    (102, 'Copper Fox Brewing',   'Midwest'),
    (103, 'Dune & Sage Goods',    'West'),
    (104, 'Evergreen Solar Co.',  'Southeast'),
    (105, 'Finch & Fern Café',    'Northeast'),
    (106, 'Golden Hive Honey',    'Midwest');

-- Seed orders — some reference valid customers, two have NULL customer_id,
-- and order 9 references customer_id 999 which does NOT exist.
INSERT INTO orders (order_id, customer_id, order_date, amount) VALUES
    (1,  101,  '2024-11-03',  249.50),
    (2,  102,  '2024-11-05',   87.20),
    (3,  103,  '2024-11-07',  412.00),
    (4,  104,  '2024-11-08',  158.75),
    (5,  105,  '2024-11-10', 1340.00),
    (6,  101,  '2024-11-12',  310.60),
    (7,  106,  '2024-11-14',   73.90),
    (8,  NULL, '2024-11-15',  520.00),
    (9,  999,  '2024-11-17',  195.30),
    (10, NULL, '2024-11-19',   64.80),
    (11, 102,  '2024-11-21',  445.10);


-- =============================================================
-- [left_join_baseline]
-- The basic LEFT JOIN: every order is kept, but orders 8 & 10
-- (NULL customer_id) and order 9 (customer 999 doesn't exist)
-- come back with NULL customer_name. This is the expected
-- behaviour — LEFT JOIN preserves unmatched left-side rows
-- and fills right-side columns with NULL.
-- =============================================================
SELECT
    o.order_id,
    o.customer_id,
    c.customer_name,
    c.region,
    o.amount
FROM orders AS o
LEFT JOIN customers AS c
    ON o.customer_id = c.customer_id
ORDER BY o.order_id;


-- =============================================================
-- [where_destroys_left_join]
-- THE TRAP: adding WHERE c.region = 'Northeast' silently turns
-- the LEFT JOIN into an INNER JOIN. Unmatched rows have
-- region = NULL, which fails the WHERE test, so they vanish.
-- We started with 11 orders — now only 3 rows survive.
-- =============================================================
SELECT
    o.order_id,
    o.customer_id,
    c.customer_name,
    c.region,
    o.amount
FROM orders AS o
LEFT JOIN customers AS c
    ON o.customer_id = c.customer_id
WHERE c.region = 'Northeast'
ORDER BY o.order_id;


-- =============================================================
-- [fix_filter_in_on_clause]
-- THE FIX: move the filter into the ON clause. Now every order
-- row is preserved (all 11). Non-Northeast matches simply show
-- NULL for customer columns instead of disappearing.
-- =============================================================
SELECT
    o.order_id,
    o.customer_id,
    c.customer_name,
    c.region,
    o.amount
FROM orders AS o
LEFT JOIN customers AS c
    ON o.customer_id = c.customer_id
   AND c.region = 'Northeast'
ORDER BY o.order_id;


-- =============================================================
-- [revenue_comparison]
-- Why it matters: the wrong query under-counts total revenue.
-- Compare the sum from the broken WHERE version (only Northeast
-- orders) vs. the full dataset. Moving the filter to ON keeps
-- every dollar while still isolating Northeast customer info.
-- =============================================================
SELECT
    'WHERE (broken)'     AS approach,
    SUM(sub.amount)      AS total_revenue,
    COUNT(*)             AS row_count
FROM (
    SELECT o.amount
    FROM orders AS o
    LEFT JOIN customers AS c
        ON o.customer_id = c.customer_id
    WHERE c.region = 'Northeast'
) AS sub

UNION ALL

SELECT
    'ON clause (fixed)'  AS approach,
    SUM(sub.amount)      AS total_revenue,
    COUNT(*)             AS row_count
FROM (
    SELECT o.amount
    FROM orders AS o
    LEFT JOIN customers AS c
        ON o.customer_id = c.customer_id
       AND c.region = 'Northeast'
) AS sub;