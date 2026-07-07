-- [ai_generated_query_top5_customers]
-- Step 2a: This is the AI-generated query we paste into our SQL viewer
-- It ranks customers by their total order amount (top 5)
SELECT
    c.customer_id,
    c.customer_name,
    SUM(o.order_amount) AS total_spent,
    COUNT(o.order_id) AS total_orders
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name
ORDER BY total_spent DESC
LIMIT 5;

-- [spot_check_identify_top_customer]
-- Step 2b: Eyeball the results — who came out on top?
-- Let's say "Greenfield Industries" (customer_id = 42) appeared as #1
-- with a total_spent of 184,750.00
-- Now we need to INDEPENDENTLY verify that number

-- [micro_query_verify_top_customer]
-- Step 2c: Micro-query — manually written, simple, and focused
-- We verify the #1 customer's total by writing our own SUM query
-- This query uses NO joins, NO grouping tricks — just a direct check
SELECT
    SUM(order_amount) AS verified_total
FROM orders
WHERE customer_id = 42;

-- [micro_query_verify_with_detail]
-- Step 2d: If the totals don't match, drill deeper to see every row
-- This lets us inspect the individual orders that make up the sum
SELECT
    order_id,
    order_date,
    order_amount
FROM orders
WHERE customer_id = 42
ORDER BY order_date;

-- [micro_query_verify_order_count]
-- Step 2e: Also verify the order count independently
-- A mismatched count can reveal duplicate rows or missing join conditions
SELECT
    COUNT(order_id) AS verified_order_count
FROM orders
WHERE customer_id = 42;

-- [compare_results_side_by_side]
-- Step 2f: Optional — combine the AI result and your verification in one view
-- This makes it easy to compare on screen during a spot-check
SELECT
    'AI Query Result'     AS source,
    184750.00             AS total_spent,
    23                    AS total_orders
UNION ALL
SELECT
    'Manual Micro-Query'  AS source,
    (SELECT SUM(order_amount) FROM orders WHERE customer_id = 42) AS total_spent,
    (SELECT COUNT(order_id)   FROM orders WHERE customer_id = 42) AS total_orders;
-- [schema_prompt_query]
-- Auto-generated placeholder
SELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);


-- [micro_query_verify]
-- Auto-generated placeholder
SELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);


-- [final_verified_query]
-- Auto-generated placeholder
SELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);


-- [ai_explain_query]
-- Auto-generated placeholder
SELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);


-- [bad_ai_query]
-- Auto-generated placeholder
SELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);
