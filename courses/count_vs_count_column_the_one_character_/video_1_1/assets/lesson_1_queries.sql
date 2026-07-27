-- Orders table: contains 10 orders, 3 of which have no discount code (NULL)
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer    TEXT NOT NULL,
    order_date  TEXT NOT NULL,
    amount      REAL NOT NULL,
    discount_code TEXT  -- nullable: not every order uses a discount
);

INSERT INTO orders (order_id, customer, order_date, amount, discount_code) VALUES
(1,  'Maria Chen',      '2024-11-02', 84.50,  'FALL15'),
(2,  'James Okoro',     '2024-11-03', 129.99, NULL),
(3,  'Priya Sharma',    '2024-11-05', 47.25,  'WELCOME10'),
(4,  'Tom Andersen',    '2024-11-06', 215.00, 'VIP20'),
(5,  'Lucia Reyes',     '2024-11-08', 63.80,  NULL),
(6,  'David Kim',       '2024-11-09', 92.15,  'FALL15'),
(7,  'Sophie Martin',   '2024-11-10', 178.40, 'WELCOME10'),
(8,  'Ali Hassan',      '2024-11-12', 54.99,  'HOLIDAY5'),
(9,  'Elena Volkov',    '2024-11-14', 310.75, NULL),
(10, 'Carlos Mendes',   '2024-11-15', 141.60, 'VIP20');

-- [count_star]
-- COUNT(*) counts every row regardless of column values.
SELECT COUNT(*) AS count_star FROM orders;

-- [count_column]
-- COUNT(discount_code) silently skips NULLs — returning a smaller number.
SELECT COUNT(discount_code) AS count_discount_code FROM orders;

-- [isolate_the_nulls]
-- These are the 3 rows that COUNT(discount_code) silently ignored.
SELECT order_id, customer, order_date, amount, discount_code
  FROM orders
 WHERE discount_code IS NULL;

-- [measure_the_gap]
-- Subtract the two counts to quantify exactly how many NULLs were hidden.
SELECT COUNT(*)                          AS total_rows,
       COUNT(discount_code)              AS rows_with_discount,
       COUNT(*) - COUNT(discount_code)   AS missing_discounts
  FROM orders;