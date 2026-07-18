-- Duplicate Rows — The Silent Inflator
-- This lesson shows how a one-to-many JOIN inflates aggregates,
-- how to diagnose the problem, and how to fix it.

-- Table: customer orders
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date  TEXT NOT NULL,
    order_total REAL NOT NULL
);

-- Table: payments received (an order can have multiple partial payments)
CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    amount       REAL NOT NULL,
    method       TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Seed orders — 8 orders with realistic, varied totals
INSERT INTO orders (order_id, customer_id, order_date, order_total) VALUES
(1001, 501, '2024-03-01', 249.95),
(1002, 502, '2024-03-02', 87.50),
(1003, 503, '2024-03-03', 412.00),
(1004, 501, '2024-03-05', 64.99),
(1005, 504, '2024-03-06', 189.00),
(1006, 505, '2024-03-07', 315.75),
(1007, 506, '2024-03-08', 42.00),
(1008, 502, '2024-03-09', 128.30);

-- Seed payments — some orders have multiple payments (the source of duplication)
-- Order 1001: 3 partial payments
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(1, 1001, '2024-03-01', 100.00, 'credit_card'),
(2, 1001, '2024-03-03', 100.00, 'credit_card'),
(3, 1001, '2024-03-10', 49.95, 'debit_card');

-- Order 1002: 1 payment
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(4, 1002, '2024-03-02', 87.50, 'credit_card');

-- Order 1003: 2 payments
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(5, 1003, '2024-03-03', 200.00, 'bank_transfer'),
(6, 1003, '2024-03-05', 212.00, 'credit_card');

-- Order 1004: 1 payment
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(7, 1004, '2024-03-05', 64.99, 'debit_card');

-- Order 1005: 2 payments
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(8, 1005, '2024-03-06', 100.00, 'credit_card'),
(9, 1005, '2024-03-08', 89.00, 'credit_card');

-- Order 1006: 1 payment
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(10, 1006, '2024-03-07', 315.75, 'bank_transfer');

-- Order 1007: 1 payment
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(11, 1007, '2024-03-08', 42.00, 'debit_card');

-- Order 1008: 3 payments
INSERT INTO payments (payment_id, order_id, payment_date, amount, method) VALUES
(12, 1008, '2024-03-09', 50.00, 'credit_card'),
(13, 1008, '2024-03-11', 50.00, 'credit_card'),
(14, 1008, '2024-03-13', 28.30, 'debit_card');

-- ============================================================
-- SCENE 1: How a JOIN creates duplicates and inflates a SUM
-- ============================================================

-- [duplicate_join_raw_rows]
-- Show the raw joined rows: notice order 1001 appears 3 times,
-- order 1003 twice, etc. The order_total is repeated per payment row.
SELECT
    o.order_id,
    o.order_total,
    p.payment_id,
    p.amount   AS payment_amount,
    p.method
FROM orders o
JOIN payments p ON p.order_id = o.order_id
ORDER BY o.order_id, p.payment_id;

-- [inflated_sum]
-- Naively summing order_total across the joined result.
-- The TRUE total of all orders is 1,489.49.
-- Because of duplicates this query reports an INFLATED number.
SELECT
    SUM(o.order_total) AS inflated_order_total,
    SUM(p.amount)      AS correct_payment_total,
    (SELECT SUM(order_total) FROM orders) AS true_order_total
FROM orders o
JOIN payments p ON p.order_id = o.order_id;

-- ============================================================
-- SCENE 2: Fix — aggregate payments first, THEN join
-- ============================================================

-- [fixed_with_subquery]
-- Pre-aggregate payments in a subquery so each order has exactly one row,
-- then join. The SUM of order_total now matches the true dashboard number.
SELECT
    o.order_id,
    o.order_total,
    pay.total_paid,
    o.order_total - pay.total_paid AS balance_remaining
FROM orders o
JOIN (
    SELECT order_id,
           SUM(amount) AS total_paid
    FROM payments
    GROUP BY order_id
) pay ON pay.order_id = o.order_id
ORDER BY o.order_id;

-- ============================================================
-- SCENE 3: Diagnostic — instantly spot which orders duplicate
-- ============================================================

-- [diagnose_duplicates]
-- Quick diagnostic: join first, then count rows per order_id.
-- Any row_count > 1 means that order's data would be inflated in a SUM.
SELECT
    o.order_id,
    o.order_total,
    COUNT(*) AS row_count
FROM orders o
JOIN payments p ON p.order_id = o.order_id
GROUP BY o.order_id
HAVING COUNT(*) > 1
ORDER BY row_count DESC;