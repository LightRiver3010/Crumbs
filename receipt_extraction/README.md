# Screenshot MVP
From the project root in PowerShell:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m receipt_extraction.repository
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address localhost
```
The setup command creates the separate receipts dataset and two tables. Local AWS delivery-dev and Google ADC credentials must work. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in .env; optional GEMINI_MODEL overrides gemini-3.8-flash. Never commit credentials.

Files: images.py validates/converts still PNG/JPEG/WebP/HEIC/HEIF/BMP/TIFF/GIF; gemini_client.py calls the model; schemas.py validates output; pipeline.py uploads and extracts; repository.py saves confirmed data; analytics.py queries current-session summaries. frontend/app.py provides upload, editable JSON review and save. shared/storage.py and shared/bigquery.py hold cloud connections.

Images are normalized to PNG without EXIF and stored at private/receipts/<session>/<hash>.png. The prefix alone does not enforce privacy: keep S3 Block Public Access enabled and restrict IAM. No lifecycle rule is installed; configure retention for this prefix before real users. Uploads remain in S3 even if Gemini fails. No address/payment fields are requested, but screenshots can contain them.

Gemini is invoked only on an explicit Extract click, never a normal Streamlit rerun. The active successful draft is reused. Re-uploading after changing files/restarting may call Gemini again. Save retries replace that upload's rows transactionally. Visible provider/order references deduplicate across screenshots; without those, users must remove overlap manually. Concurrent writes are not supported in this local MVP.

Only confirmed payloads are persisted; failed/unconfirmed model attempts are not audited yet. No login: session identity is temporary and not a production authorization mechanism. Do not expose this app publicly before adding authentication and authorization. Benchmark import/aggregation is a documented scaffold, not fabricated comparisons.
