BEGIN TRANSACTION;
MERGE `{project}.receipts.upload_extractions` T
USING (SELECT @session session_id, @upload upload_id) S
ON T.session_id=S.session_id AND T.upload_id=S.upload_id
WHEN MATCHED THEN UPDATE SET confirmed_payload=@payload, raw_uri=@uri, saved_at=CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT VALUES (@session,@upload,@uri,@payload,CURRENT_TIMESTAMP());
DELETE FROM `{project}.receipts.user_orders` WHERE session_id=@session AND upload_id=@upload;
MERGE `{project}.receipts.user_orders` T
USING (
 SELECT DISTINCT JSON_VALUE(o,'$.order_id') order_id, JSON_VALUE(o,'$.restaurant') restaurant,
 JSON_VALUE(o,'$.provider') provider, JSON_VALUE(o,'$.order_reference') order_reference,
 SAFE_CAST(JSON_VALUE(o,'$.order_date') AS DATE) order_date,
 SAFE_CAST(JSON_VALUE(o,'$.total_cents') AS INT64) total_cents,
 JSON_VALUE(o,'$.currency') currency, TO_JSON_STRING(JSON_QUERY(o,'$.items')) items_json
 FROM UNNEST(JSON_QUERY_ARRAY(PARSE_JSON(@orders))) o
) S ON T.session_id=@session AND T.order_id=S.order_id
WHEN NOT MATCHED THEN INSERT VALUES
(@session,@upload,S.order_id,S.restaurant,S.provider,S.order_reference,S.order_date,S.total_cents,S.currency,S.items_json,CURRENT_TIMESTAMP());
COMMIT TRANSACTION;
