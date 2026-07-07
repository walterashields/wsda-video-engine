-- Table representing customers
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region        TEXT NOT NULL
);

-- Table representing orders placed by customers
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date  TEXT NOT NULL,
    total_amount REAL NOT NULL
);

-- Seed customers
INSERT INTO customers (customer_id, customer_name, region) VALUES
(1, 'Greenfield Industries',  'Northeast'),
(2, 'Apex Logistics',         'West'),
(3, 'Summit Health Partners',  'Southeast'),
(4, 'Cascade Manufacturing',   'Midwest'),
(5, 'BrightPath Education',    'West'),
(6, 'Ironclad Security',       'Northeast'),
(7, 'TerraFirma Construction', 'Southeast'),
(8, 'NovaWave Media',          'West'),
(9, 'Pinecrest Foods',         'Midwest'),
(10, 'Atlas Marine Supply',    'Northeast');

-- Seed orders — varied realistic amounts across 2024
INSERT INTO orders (order_id, customer_id, order_date, total_amount) VALUES
-- Greenfield Industries  (expect total: 4825 + 7190 + 3340 + 5685 + 2910 = 23950)
(101, 1, '2024-01-14', 4825.00),
(102, 1, '2024-03-08', 7190.00),
(103, 1, '2024-06-22', 3340.00),
(104, 1, '2024-09-11', 5685.00),
(105, 1, '2024-11-03', 2910.00),
-- Apex Logistics  (expect total: 22430)
(106, 2, '2024-02-19', 6430.00),
(107, 2, '2024-04-05', 3875.00),
(108, 2, '2024-07-17', 8250.00),
(109, 2, '2024-10-28', 3875.00),
-- Summit Health Partners  (expect total: 19560)
(110, 3, '2024-01-30', 5120.00),
(111, 3, '2024-05-14', 7890.00),
(112, 3, '2024-08-09', 6550.00),
-- Cascade Manufacturing  (expect total: 17315)
(113, 4, '2024-02-02', 4315.00),
(114, 4, '2024-06-18', 6400.00),
(115, 4, '2024-09-25', 3100.00),
(116, 4, '2024-12-01', 3500.00),
-- BrightPath Education  (expect total: 15720)
(117, 5, '2024-03-12', 5720.00),
(118, 5, '2024-07-29', 4500.00),
(119, 5, '2024-11-15', 5500.00),
-- Ironclad Security  (expect total: 12835)
(120, 6, '2024-04-10', 4235.00),
(121, 6, '2024-08-22', 8600.00),
-- TerraFirma Construction  (expect total: 11390)
(122, 7, '2024-01-08', 3890.00),
(123, 7, '2024-05-30', 7500.00),
-- NovaWave Media  (expect total: 9875)
(124, 8, '2024-06-04', 4125.00),
(125, 8, '2024-10-19', 5750.00),
-- Pinecrest Foods  (expect total: 8460)
(126, 9, '2024-03-25', 3460.00),
(127, 9, '2024-09-07', 5000.00),
-- Atlas Marine Supply  (expect total: 6950)
(128, 10, '2024-07-12', 6950.00);


-- =================================================================
-- TEACHING QUERIES
-- =================================================================

-- [ai_generated_top5_query]
-- This is the "AI-generated" query the narrator pastes into the SQL viewer.
-- It ranks all customers by their 2024 total spend and returns the top 5.
SELECT
    c.customer_name,
    c.region,
    COUNT(o.order_id)        AS order_count,
    SUM(o.total_amount)      AS total_spend
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.order_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY total_spend DESC
LIMIT 5;


-- [micro_query_spot_check]
-- The manually written micro-query to independently verify the #1 customer's total.
-- The narrator checks: does this simple SUM match the 23950.00 shown in the top-5 list?
SELECT
    SUM(total_amount) AS verified_total
FROM orders
WHERE customer_id = (
    SELECT customer_id
    FROM customers
    WHERE customer_name = 'Greenfield Industries'
);