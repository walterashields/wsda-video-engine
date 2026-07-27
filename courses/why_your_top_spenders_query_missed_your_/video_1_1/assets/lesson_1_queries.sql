-- Customers table: five customers with spending history and activity metrics
CREATE TABLE customers (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    total_spent   REAL NOT NULL,
    last_order_date TEXT NOT NULL,   -- ISO date format YYYY-MM-DD
    order_count   INTEGER NOT NULL
);

-- Use fixed dates so the 90-day filter always works deterministically.
-- We anchor "today" as 2025-07-15 and use that in the filtered query.
INSERT INTO customers (id, name, total_spent, last_order_date, order_count) VALUES
(1, 'Big Corp',        48000.00, '2023-02-14',  1),
(2, 'Sara Martinez',   12350.00, '2025-06-18', 47),
(3, 'Delta Supplies',  31200.00, '2024-01-09',  6),
(4, 'Liam Chen',        8740.50, '2025-05-30', 29),
(5, 'Northgate LLC',   22500.00, '2025-07-01', 14);


-- [naive_top_spender]
-- The query that "looks right": who spent the most overall?
SELECT name,
       total_spent
  FROM customers
 ORDER BY total_spent DESC
 LIMIT 1;


-- [full_table_reveal]
-- Reveal the full picture — Big Corp's single old order vs Sara's 47 recent ones
SELECT name,
       total_spent,
       last_order_date,
       order_count
  FROM customers
 ORDER BY total_spent DESC;


-- [filtered_by_recency_and_frequency]
-- The fix: use a fixed reference date ('2025-07-15') so the 90-day window
-- is deterministic and always returns rows regardless of when the file runs.
-- This keeps customers active within the last 90 days and sorts by frequency.
SELECT name,
       total_spent,
       last_order_date,
       order_count
  FROM customers
 WHERE last_order_date >= DATE('2025-07-15', '-90 days')
 ORDER BY order_count DESC;