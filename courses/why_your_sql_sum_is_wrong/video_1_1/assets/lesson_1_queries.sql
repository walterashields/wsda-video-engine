-- =============================================================
-- Lesson: The JOIN that secretly doubled your revenue
-- =============================================================

-- Orders table: each row is a customer order
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    order_date TEXT NOT NULL
);

-- Payments table: each order can have MULTIPLE payments (split payments, partial refunds, etc.)
CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    payment_amount NUMERIC(10,2) NOT NULL,
    payment_method TEXT NOT NULL,
    paid_date TEXT NOT NULL
);

-- Seed 10 orders with realistic, non-round amounts
INSERT INTO orders (id, customer_name, amount, order_date) VALUES
(1,  'Acme Corp',          53470.25, '2024-01-15'),
(2,  'Birchwood LLC',      28915.80, '2024-01-22'),
(3,  'Crimson Industries', 41387.50, '2024-02-03'),
(4,  'DataSync Inc',       19250.00, '2024-02-14'),
(5,  'Evergreen Co',       67830.75, '2024-03-01'),
(6,  'Falcon Media',       35612.40, '2024-03-11'),
(7,  'Granite Solutions',  44295.10, '2024-03-28'),
(8,  'Horizon Labs',       12780.60, '2024-04-05'),
(9,  'InnovateTech',       58430.00, '2024-04-19'),
(10, 'JetStream Logistics',57920.35, '2024-05-02');

-- Each order has exactly 2 payments — the one-to-many that causes doubling
INSERT INTO payments (id, order_id, payment_amount, payment_method, paid_date) VALUES
(1,  1, 26735.13, 'wire_transfer', '2024-01-15'),
(2,  1, 26735.12, 'wire_transfer', '2024-02-15'),
(3,  2, 10000.00, 'credit_card',   '2024-01-22'),
(4,  2, 18915.80, 'credit_card',   '2024-02-22'),
(5,  3, 20693.75, 'ach',           '2024-02-03'),
(6,  3, 20693.75, 'ach',           '2024-03-03'),
(7,  4,  9625.00, 'credit_card',   '2024-02-14'),
(8,  4,  9625.00, 'credit_card',   '2024-03-14'),
(9,  5, 40000.00, 'wire_transfer', '2024-03-01'),
(10, 5, 27830.75, 'wire_transfer', '2024-04-01'),
(11, 6, 15612.40, 'ach',           '2024-03-11'),
(12, 6, 20000.00, 'check',         '2024-04-11'),
(13, 7, 22147.55, 'credit_card',   '2024-03-28'),
(14, 7, 22147.55, 'credit_card',   '2024-04-28'),
(15, 8,  6390.30, 'ach',           '2024-04-05'),
(16, 8,  6390.30, 'ach',           '2024-05-05'),
(17, 9, 30000.00, 'wire_transfer', '2024-04-19'),
(18, 9, 28430.00, 'wire_transfer', '2024-05-19'),
(19, 10, 28960.18, 'credit_card',  '2024-05-02'),
(20, 10, 28960.17, 'check',        '2024-06-02');

-- [buggy_vs_fixed]
-- The buggy JOIN duplicates each order once per payment, doubling revenue.
-- The fix: pre-aggregate payments so each order matches exactly one row.
SELECT
    'Buggy JOIN'      AS method,
    (SELECT SUM(o.amount)
     FROM orders o
     JOIN payments p ON o.id = p.order_id)  AS reported_revenue,
    (SELECT SUM(amount) FROM orders)        AS actual_revenue,
    (SELECT COUNT(*)
     FROM orders o
     JOIN payments p ON o.id = p.order_id)  AS joined_rows,
    (SELECT COUNT(*) FROM orders)           AS real_orders
UNION ALL
SELECT
    'Fixed (pre-agg)',
    (SELECT SUM(o.amount)
     FROM orders o
     JOIN (SELECT order_id FROM payments GROUP BY order_id) ps
       ON o.id = ps.order_id),
    (SELECT SUM(amount) FROM orders),
    (SELECT COUNT(*)
     FROM orders o
     JOIN (SELECT order_id FROM payments GROUP BY order_id) ps
       ON o.id = ps.order_id),
    (SELECT COUNT(*) FROM orders);