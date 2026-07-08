-- Customers table
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL
);

-- Orders table representing sales transactions
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Seed customers
INSERT INTO customers (customer_id, customer_name, region) VALUES
(1, 'Greenfield Manufacturing', 'Northeast'),
(2, 'Apex Logistics', 'Southeast'),
(3, 'Bridgewater Solutions', 'Midwest'),
(4, 'Coastal Dynamics', 'West'),
(5, 'Pinnacle Health Systems', 'Northeast'),
(6, 'Redwood Analytics', 'West'),
(7, 'Summit Energy Corp', 'Southeast'),
(8, 'Trident Marine Services', 'Midwest'),
(9, 'Vanguard Retail Group', 'Northeast'),
(10, 'Horizon Aerospace', 'West');

-- Seed orders with varied, realistic amounts across 2024
INSERT INTO orders (order_id, customer_id, order_date, total_amount) VALUES
-- Greenfield Manufacturing (customer 1): should total 94,870.00
(101, 1, '2024-01-15', 12450.00),
(102, 1, '2024-03-08', 18975.50),
(103, 1, '2024-05-22', 9340.00),
(104, 1, '2024-07-11', 27600.00),
(105, 1, '2024-09-30', 15280.75),
(106, 1, '2024-11-14', 11223.75),
-- Apex Logistics (customer 2): should total 78,411.25
(107, 2, '2024-02-03', 22100.00),
(108, 2, '2024-04-19', 8735.25),
(109, 2, '2024-06-28', 31450.00),
(110, 2, '2024-10-05', 16126.00),
-- Bridgewater Solutions (customer 3): should total 67,295.00
(111, 3, '2024-01-28', 14500.00),
(112, 3, '2024-04-02', 19875.00),
(113, 3, '2024-08-16', 32920.00),
-- Coastal Dynamics (customer 4): should total 53,680.50
(114, 4, '2024-03-14', 28400.00),
(115, 4, '2024-07-09', 15780.50),
(116, 4, '2024-12-01', 9500.00),
-- Pinnacle Health Systems (customer 5): should total 89,124.00
(117, 5, '2024-02-20', 34500.00),
(118, 5, '2024-05-11', 21874.00),
(119, 5, '2024-08-25', 18250.00),
(120, 5, '2024-11-30', 14500.00),
-- Redwood Analytics (customer 6): should total 42,615.75
(121, 6, '2024-01-09', 17890.75),
(122, 6, '2024-06-15', 24725.00),
-- Summit Energy Corp (customer 7): should total 61,340.00
(123, 7, '2024-03-22', 19500.00),
(124, 7, '2024-07-30', 26840.00),
(125, 7, '2024-10-18', 15000.00),
-- Trident Marine Services (customer 8): should total 48,925.50
(126, 8, '2024-04-07', 23450.50),
(127, 8, '2024-09-12', 25475.00),
-- Vanguard Retail Group (customer 9): should total 72,380.00
(128, 9, '2024-02-14', 18950.00),
(129, 9, '2024-05-29', 27430.00),
(130, 9, '2024-08-08', 14500.00),
(131, 9, '2024-11-21', 11500.00),
-- Horizon Aerospace (customer 10): should total 56,750.00
(132, 10, '2024-01-31', 31250.00),
(133, 10, '2024-06-04', 25500.00);

-- [ai_generated_top5_query]
-- This is the AI-generated query: "Show me the top 5 customers by total 2024 revenue"
-- Pasted directly from the AI into the SQL viewer
SELECT
    c.customer_name,
    c.region,
    COUNT(o.order_id)        AS total_orders,
    SUM(o.total_amount)      AS total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY total_revenue DESC
LIMIT 5;

-- [micro_query_spot_check]
-- Step 2 spot-check: manually written micro-query to verify the #1 customer's total
-- We independently SUM only Greenfield Manufacturing's orders to confirm the number matches
SELECT
    SUM(total_amount) AS verified_total
FROM orders
WHERE customer_id = 1
  AND order_date BETWEEN '2024-01-01' AND '2024-12-31';