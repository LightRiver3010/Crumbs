SELECT COALESCE(restaurant, 'Unknown restaurant') restaurant, currency,
COUNT(*) order_count, COUNT(total_cents) orders_with_known_total,
SUM(total_cents)/100.0 total_spent, AVG(total_cents)/100.0 average_order_total
FROM `{project}.receipts.user_orders`
WHERE session_id=@session
GROUP BY restaurant,currency ORDER BY order_count DESC;
