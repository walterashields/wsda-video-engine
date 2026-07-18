-- Lesson: AI wrote perfect SQL — then nuked my data
-- Scenario: AI generates a DELETE to remove inactive customers,
-- but the WHERE clause logic is wrong (AND vs OR), catching
-- far more rows than intended. We SELECT first to catch the mistake.

-- Customers table with realistic data
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL,
    signup_date   TEXT NOT NULL,
    last_order_date TEXT,          -- NULL means they never ordered
    status        TEXT NOT NULL    -- 'active', 'inactive', 'suspended'
);

INSERT INTO customers (customer_id, full_name, email, signup_date, last_order_date, status) VALUES
(1,  'Maria Chen',        'maria.chen@gmail.com',      '2021-03-14', '2024-11-02', 'active'),
(2,  'James Okafor',      'j.okafor@outlook.com',      '2022-07-21', '2024-10-18', 'active'),
(3,  'Priya Sharma',      'priya.s@yahoo.com',         '2020-01-09', '2023-01-15', 'inactive'),
(4,  'Carlos Medina',     'cmedina@hotmail.com',       '2023-05-30', '2024-12-01', 'active'),
(5,  'Fatima Al-Rashid',  'fatima.ar@gmail.com',       '2019-11-22', NULL,         'inactive'),
(6,  'Liam Nguyen',       'liam.ng@proton.me',         '2022-02-14', '2024-09-05', 'active'),
(7,  'Sofia Petrov',      'spetrov@gmail.com',         '2021-08-03', '2024-08-22', 'active'),
(8,  'David Kim',         'david.kim@icloud.com',      '2023-11-11', '2024-11-30', 'active'),
(9,  'Amara Johnson',     'amara.j@outlook.com',       '2020-06-17', '2022-12-01', 'inactive'),
(10, 'Ravi Patel',        'ravi.p@yahoo.com',          '2018-04-05', NULL,         'suspended'),
(11, 'Emma Larsson',      'emma.l@gmail.com',          '2024-01-20', '2024-12-03', 'active'),
(12, 'Tomoko Hayashi',    'tomoko.h@outlook.com',      '2021-09-28', '2024-07-14', 'active');

-- ============================================================
-- INTENT: "Delete customers who are inactive AND have not
-- ordered since before 2023."
--
-- The AI wrote:  DELETE FROM customers
--                WHERE status = 'inactive'
--                   OR last_order_date < '2023-01-01';
--
-- The bug: OR instead of AND.  This matches anyone who is
-- inactive (regardless of order date) PLUS anyone whose last
-- order is old (regardless of status) — catching active
-- customers too.
-- ============================================================

-- [bad_select_before_delete]
-- Step 1: Run the AI's WHERE clause as a SELECT first.
-- This reveals the damage BEFORE any rows are deleted.
-- Notice it returns active customers (rows you'd lose!).
SELECT customer_id,
       full_name,
       status,
       last_order_date
  FROM customers
 WHERE status = 'inactive'
    OR last_order_date < '2023-01-01';

-- [why_its_wrong]
-- Look at each matched row and WHY it matched.
-- Active customers matched only because of the OR condition
-- on last_order_date — they are NOT inactive.
SELECT customer_id,
       full_name,
       status,
       last_order_date,
       CASE
         WHEN status = 'inactive' AND last_order_date < '2023-01-01' THEN '✓ truly cleanup target'
         WHEN status = 'inactive'                                     THEN '⚠ inactive but recent order'
         WHEN last_order_date < '2023-01-01'                          THEN '✗ ACTIVE customer — would be NUKED'
         WHEN last_order_date IS NULL                                 THEN '⚠ no order date at all'
       END AS diagnosis
  FROM customers
 WHERE status = 'inactive'
    OR last_order_date < '2023-01-01';

-- [fixed_select_before_delete]
-- Step 2: Fix the logic — AND instead of OR.
-- Now only genuinely inactive customers with stale orders appear.
SELECT customer_id,
       full_name,
       status,
       last_order_date
  FROM customers
 WHERE status = 'inactive'
   AND (last_order_date < '2023-01-01' OR last_order_date IS NULL);

-- [confirm_table_intact]
-- Step 3: Because we SELECT-ed first, nothing was deleted.
-- All 12 rows are still safe.
SELECT COUNT(*) AS total_customers_still_safe
  FROM customers;