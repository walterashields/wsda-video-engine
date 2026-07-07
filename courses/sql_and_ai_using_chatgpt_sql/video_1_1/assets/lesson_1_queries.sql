-- [setup_tables]

-- Create the three tables needed for revenue by customer segment analysis
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    segment TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date DATE NOT NULL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- [insert_sample_data]

-- Populate customers across three distinct segments
INSERT INTO customers (customer_id, customer_name, segment, region, signup_date) VALUES
(1, 'Acme Corporation', 'Enterprise', 'North America', '2021-03-15'),
(2, 'Widget Labs', 'Small Business', 'Europe', '2022-01-10'),
(3, 'Global Logistics Inc.', 'Enterprise', 'North America', '2020-07-22'),
(4, 'Sunrise Bakery', 'Small Business', 'North America', '2023-02-05'),
(5, 'TechForward Solutions', 'Mid-Market', 'Europe', '2021-11-30'),
(6, 'Pinnacle Health Group', 'Enterprise', 'Asia Pacific', '2020-01-18'),
(7, 'Cedar & Stone Design', 'Small Business', 'North America', '2023-06-12'),
(8, 'Momentum Analytics', 'Mid-Market', 'Europe', '2022-04-09'),
(9, 'BlueShore Capital', 'Mid-Market', 'North America', '2021-08-25'),
(10, 'Hartfield Manufacturing', 'Enterprise', 'Asia Pacific', '2019-12-01');

-- Populate orders with varying statuses
INSERT INTO orders (order_id, customer_id, order_date, status) VALUES
(101, 1, '2024-01-15', 'completed'),
(102, 1, '2024-03-22', 'completed'),
(103, 2, '2024-02-10', 'completed'),
(104, 3, '2024-01-28', 'completed'),
(105, 3, '2024-04-05', 'cancelled'),
(106, 4, '2024-03-18', 'completed'),
(107, 5, '2024-02-14', 'completed'),
(108, 5, '2024-04-20', 'completed'),
(109, 6, '2024-01-05', 'completed'),
(110, 6, '2024-02-28', 'completed'),
(111, 6, '2024-04-12', 'completed'),
(112, 7, '2024-03-30', 'completed'),
(113, 8, '2024-01-22', 'completed'),
(114, 9, '2024-02-18', 'completed'),
(115, 9, '2024-04-01', 'completed'),
(116, 10, '2024-03-10', 'completed'),
(117, 10, '2024-04-25', 'completed'),
(118, 2, '2024-04-15', 'refunded'),
(119, 4, '2024-01-08', 'completed'),
(120, 8, '2024-03-28', 'completed');

-- Populate order items with realistic products and prices
INSERT INTO order_items (item_id, order_id, product_name, quantity, unit_price) VALUES
(1001, 101, 'Platform License - Annual', 2, 15000.00),
(1002, 101, 'Premium Support Plan', 1, 5000.00),
(1003, 102, 'API Integration Module', 3, 3500.00),
(1004, 103, 'Starter License - Monthly', 1, 299.00),
(1005, 103, 'Data Storage Add-on', 1, 150.00),
(1006, 104, 'Platform License - Annual', 5, 15000.00),
(1007, 104, 'Training Workshop', 2, 2500.00),
(1008, 105, 'Platform License - Annual', 1, 15000.00),
(1009, 106, 'Starter License - Monthly', 2, 299.00),
(1010, 107, 'Business License - Annual', 1, 7500.00),
(1011, 107, 'Data Storage Add-on', 3, 150.00),
(1012, 108, 'API Integration Module', 1, 3500.00),
(1013, 109, 'Platform License - Annual', 10, 15000.00),
(1014, 109, 'Premium Support Plan', 5, 5000.00),
(1015, 110, 'Training Workshop', 4, 2500.00),
(1016, 111, 'API Integration Module', 6, 3500.00),
(1017, 112, 'Starter License - Monthly', 1, 299.00),
(1018, 113, 'Business License - Annual', 2, 7500.00),
(1019, 113, 'Data Storage Add-on', 2, 150.00),
(1020, 114, 'Business License - Annual', 1, 7500.00),
(1021, 114, 'Premium Support Plan', 1, 5000.00),
(1022, 115, 'API Integration Module', 2, 3500.00),
(1023, 116, 'Platform License - Annual', 3, 15000.00),
(1024, 116, 'Premium Support Plan', 2, 5000.00),
(1025, 117, 'Training Workshop', 3, 2500.00),
(1026, 118, 'Starter License - Monthly', 1, 299.00),
(1027, 119, 'Starter License - Monthly', 1, 299.00),
(1028, 119, 'Data Storage Add-on', 1, 150.00),
(1029, 120, 'Business License - Annual', 1, 7500.00),
(1030, 120, 'API Integration Module', 1, 3500.00);

-- [revenue_by_customer_segment]

-- This is the query generated using the 3-Line Prompt Framework:
--   Line 1 (Role):   "You are a SQL analyst working with a SaaS sales database."
--   Line 2 (Task):   "Write a query to show total revenue by customer segment."
--   Line 3 (Rules):  "Only include completed orders. Join customers, orders, and order_items.
--                      Sort by revenue descending. Use clear column aliases."

-- Revenue by customer segment — joins across three tables
-- Filters to completed orders only, calculates total revenue per segment
SELECT
    c.segment                                    AS customer_segment,
    COUNT(DISTINCT c.customer_id)                AS total_customers,
    COUNT(DISTINCT o.order_id)                   AS total_orders,
    SUM(oi.quantity * oi.unit_price)             AS total_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price)
        / COUNT(DISTINCT c.customer_id), 2)      AS avg_revenue_per_customer
FROM
    customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_items AS oi
        ON o.order_id = oi.order