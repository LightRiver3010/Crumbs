# Screenshot MVP
From the project root in PowerShell:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m receipt_extraction.repository
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address localhost
```
The setup command creates the separate receipts dataset and two tables. Local AWS delivery-dev and Google ADC credentials must work. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in .env; optional GEMINI_MODEL overrides gemini-3.8-flash. Never commit credentials.

Files: images.py validates/converts still PNG/JPEG/WebP/HEIC/HEIF/BMP/TIFF/GIF; gemini_client.py calls the model; schemas.py validates output; pipeline.py uploads, extracts and removes exact duplicate orders; repository.py saves confirmed data; analytics.py queries current-session summaries. frontend/app.py provides upload, summary review and save. shared/storage.py and shared/bigquery.py hold cloud connections.

Images are normalized to PNG without EXIF and stored at private/receipts/<session>/<hash>.png. The prefix alone does not enforce privacy: keep S3 Block Public Access enabled and restrict IAM. No lifecycle rule is installed; configure retention for this prefix before real users. Uploads remain in S3 even if Gemini fails. No address/payment fields are requested, but screenshots can contain them.

Gemini is invoked only on an explicit Extract click, never a normal Streamlit rerun. The active successful draft is reused. Re-uploading after changing files/restarting may call Gemini again. Exact duplicate orders within an extraction are removed before review; save retries replace that upload's rows transactionally. Visible provider/order references deduplicate across screenshots. Concurrent writes are not supported in this local MVP.

Only confirmed payloads are persisted; failed/unconfirmed model attempts are not audited yet. No login: session identity is temporary and not a production authorization mechanism. Do not expose this app publicly before adding authentication and authorization. Benchmark import/aggregation is a documented scaffold, not fabricated comparisons.

## Personal insights and savings
The receipt tab accepts multiple images. Each successful extraction is cached by image hash for the browser session; adjusting savings controls does not call Gemini. Review/save remains per screenshot. Provider/order references deduplicate in the warehouse; users can deselect overlapping orders in insights. Deselecting affects current analysis only, not stored data.

insights.py computes meal appearances per order, restaurant frequency, weekdays, spending projections and dining-hall scenarios. frontend/receipt_savings.py renders these and the two routes. Unknown dates are excluded from weekday facts; unknown totals/currencies block projections rather than silently extrapolating incomplete spending.

Habit choices mean normal order frequency relative to the screenshot sample. Users confirm an inclusive reporting period (including zero-order days); usually more/less additionally requires a numeric weekly frequency in the corresponding direction. Monthly projections use 365/12 days and assume the sample's average order value. Actual receipt dates/facts are never stretched. No BLS/population comparison is active.

Dining swaps require confirmed single-person delivery orders with known USD totals strictly above $10. The slider is 0 to the selected eligible order count, replacing most expensive first. Meal plan assumes available swipes at $0 marginal cash cost; otherwise $19 per meal is a user-requested assumption. Negative savings display additional cost.

Keep the same starts with food items found in the confirmed receipts, then lets the user choose a configured restaurant and exact saved menu match. It compares current Uber Eats and DoorDash menu prices, assuming unchanged historic menu prices. Fees, discounts, tips and taxes are excluded. Coverage is explicit and unmatched items are not treated as zero savings. These scenarios are alternatives and must not be summed.
