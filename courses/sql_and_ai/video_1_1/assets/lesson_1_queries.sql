-- Customers table: stores customer information
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date TEXT NOT NULL
);

-- Orders table: stores individual orders placed by customers
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Seed realistic customer data
INSERT INTO customers (customer_id, customer_name, region, signup_date) VALUES
(1, 'Greenfield Manufacturing', 'Northeast', '2021-03-15'),
(2, 'Apex Digital Solutions', 'West', '2020-11-02'),
(3, 'Lakewood Medical Group', 'Southeast', '2022-01-20'),
(4, 'Summit Financial Partners', 'Midwest', '2019-07-08'),
(5, 'Coastal Freight Logistics', 'West', '2021-09-14'),
(6, 'Redwood Analytics Corp', 'Northeast', '2023-02-28'),
(7, 'Prairie Wind Energy', 'Midwest', '2020-05-11'),
(8, 'Bayside Hospitality Group', 'Southeast', '2022-06-30'),
(9, 'Iron Bridge Construction', 'Northeast', '2021-12-01'),
(10, 'Meridian Software Inc', 'West', '2019-04-22');

-- Seed realistic order data (varied amounts, multiple orders per customer)
INSERT INTO orders (order_id, customer_id, order_date, total_amount, status) VALUES
-- Greenfield Manufacturing: 5 orders totaling 48,735.50
(101, 1, '2024-01-12', 12450.00, 'completed'),
(102, 1, '2024-02-03', 8725.50, 'completed'),
(103, 1, '2024-03-18', 15200.00, 'completed'),
(104, 1, '2024-04-22', 6890.00, 'completed'),
(105, 1, '2024-05-09', 5470.00, 'completed'),
-- Apex Digital Solutions: 4 orders totaling 41,980.00
(106, 2, '2024-01-08', 14500.00, 'completed'),
(107, 2, '2024-02-14', 9830.00, 'completed'),
(108, 2, '2024-03-29', 11250.00, 'completed'),
(109, 2, '2024-05-15', 6400.00, 'completed'),
-- Lakewood Medical Group: 4 orders totaling 37,615.75
(110, 3, '2024-01-22', 11375.75, 'completed'),
(111, 3, '2024-02-28', 8940.00, 'completed'),
(112, 3, '2024-04-05', 9800.00, 'completed'),
(113, 3, '2024-05-20', 7500.00, 'completed'),
-- Summit Financial Partners: 3 orders totaling 33,125.00
(114, 4, '2024-01-30', 15625.00, 'completed'),
(115, 4, '2024-03-12', 9500.00, 'completed'),
(116, 4, '2024-05-01', 8000.00, 'completed'),
-- Coastal Freight Logistics: 4 orders totaling 29,870.25
(117, 5, '2024-01-15', 7250.25, 'completed'),
(118, 5, '2024-02-20', 6420.00, 'completed'),
(119, 5, '2024-03-30', 8900.00, 'completed'),
(120, 5, '2024-04-28', 7300.00, 'completed'),
-- Redwood Analytics Corp: 2 orders totaling 18,350.00
(121, 6, '2024-02-10', 10850.00, 'completed'),
(122, 6, '2024-04-15', 7500.00, 'completed'),
-- Prairie Wind Energy: 3 orders totaling 24,690.00
(123, 7, '2024-01-05', 9150.00, 'completed'),
(124, 7, '2024-03-08', 8540.00, 'completed'),
(125, 7, '2024-05-22', 7000.00, 'completed'),
-- Bayside Hospitality Group: 2 orders totaling 13,275.00
(126, 8, '2024-02-18', 5775.00, 'completed'),
(127, 8, '2024-04-10', 7500.00, 'completed'),
-- Iron Bridge Construction: 3 orders totaling 27,430.00
(128, 9, '2024-01-25', 11200.00, 'completed'),
(129, 9, '2024-03-14', 9730.00, 'completed'),
(130, 9, '2024-05-06', 6500.00, 'completed'),
-- Meridian Software Inc: 3 orders totaling 22,185.00
(131, 10, '2024-01-18', 8435.00, 'completed'),
(132, 10, '2024-03-22', 7250.00, 'completed'),
(133, 10, '2024-04-30', 6500.00, 'completed');


-- [ai_generated_top5_query]
-- This is the "AI-generated" query: Top 5 customers by total revenue in 2024.
-- In the lesson, we pretend an AI wrote this query and we pasted it in to run.
SELECT
    c.customer_name,
    c.region,
    COUNT(o.order_id)        AS total_orders,
    ROUND(SUM(o.total_amount), 2) AS total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= '2024-01-01'
  AND o.order_date <  '2025-01-01'
  AND o.status = 'completed'
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY total_revenue DESC
LIMIT 5;


-- [micro_query_spot_check]
-- Spot-check: manually verify the #1 customer's total by writing a simple,
-- hard-to-get-wrong micro-query. If this SUM matches the top row above,
-- we gain confidence the AI query is correct.
SELECT
    ROUND(SUM(total_amount), 2) AS verified_total
FROM orders
WHERE customer_id = 1
  AND order_date >= '2024-01-01'
  AND order_date <  '2025-01-01'
  AND status = 'completed';