# Crumbs

A food-delivery comparison app that helps students answer one question:
**"Where should I order this meal today?"**

Crumbs compares current Uber Eats and DoorDash prices,
turns receipt screenshots into useful spending insights, and shows users how
much they could have saved by ordering at the better price.

## About

Food-delivery prices change often, menus are inconsistent across platforms, and
receipts are usually trapped in screenshots. This project connects those
pieces into one simple experience:

1. Menus are refreshed automatically.
2. The latest valid prices are organized by restaurant and meal.
3. Users upload receipts instead of manually entering every order.
4. The app compares past orders with today's available prices.

The main goal is not to overwhelm users with raw data. It is to turn messy
delivery information into a quick, understandable recommendation.

## Major Features

- **Side-by-side price comparisons** - Compare matching meals across Uber Eats
  and DoorDash from the Home page.
- **Restaurant and meal browsing** - Filter by restaurant, category, search,
  and individual menu item.
- **Smart comparison eligibility** - Items without a trustworthy match are
  clearly marked and excluded from savings claims.
- **Receipt screenshot upload** - Upload screenshots instead of typing orders
  by hand.
- **AI receipt extraction** - Gemini Vision identifies restaurants, dates,
  items, quantities, prices, and totals.
- **Clean review experience** - Users review a readable summary rather than
  raw JSON or technical model output.
- **Duplicate cleanup** - Exact duplicate orders are detected and removed
  before saving.
- **"Keep the same" insights** - Select a food item from a confirmed receipt
  and see how its current prices compare.
- **Total savings estimate** - See how much a receipt could have saved using
  today's lowest comparable menu prices.
- **Fresh menu data** - Enabled restaurant sources are scraped hourly, with
  failed or empty snapshots excluded from the live catalog.

## How It Works

### Keeping menus fresh

Airflow runs the ingestion pipeline every hour through Google Cloud Composer.
Each enabled Uber Eats or DoorDash source is fetched through ZenRows, parsed,
validated, and stored as a historical menu snapshot.

Raw snapshots are preserved in Amazon S3. Validated menu observations are
loaded into BigQuery, and dbt creates the latest trustworthy price view. The
Streamlit app then reads the latest successful snapshot when users browse the
Home page.

### Turning receipts into insights

When a user uploads a receipt:

1. The image is checked and normalized.
2. A private copy is stored in Amazon S3.
3. Gemini Vision extracts structured order data.
4. Pydantic validates the extracted response.
5. Exact duplicate orders are removed.
6. The user reviews the extracted summary.
7. Only confirmed orders are saved to BigQuery.

The app compares confirmed receipt items against current menu prices. It never
guesses when a restaurant, item, platform, variant, or price is ambiguous.

## Data Engineering Skills

This project was built as an end-to-end data engineering system, not just a
frontend demo.

- **Data ingestion** - Fetching semi-structured menus from third-party
  delivery platforms through ZenRows.
- **Workflow orchestration** - Scheduling and coordinating independent source
  jobs with Airflow and Cloud Composer.
- **ELT modeling** - Loading raw observations into BigQuery and using dbt to
  build validated staging and latest-price models.
- **Data warehousing** - Designing raw, receipt, and latest-price tables for
  analytical queries.
- **Incremental freshness logic** - Keeping historical observations while
  selecting the newest valid menu record for each item and platform.
- **Data quality engineering** - Rejecting empty menus, invalid prices,
  ambiguous cards, mismatched restaurants, and unusable snapshots.
- **Schema enforcement** - Using Pydantic models to validate Gemini's
  structured output before it can reach the warehouse.
- **Deduplication** - Removing exact duplicate receipt orders and preventing
  duplicate saved order records.
- **Object storage design** - Preserving immutable raw menu responses and
  private receipt images in Amazon S3.
- **Parameterized SQL** - Using transactional BigQuery writes for confirmed
  receipt data.
- **Failure isolation** - Allowing one unavailable restaurant source to fail
  without publishing invalid data or blocking successful sources.
- **Cloud deployment** - Separating scheduled ingestion on Cloud Composer from
  the Streamlit frontend on Cloud Run.

## Technologies Used

**Frontend**

- Streamlit
- Python

**Data Engineering**

- Apache Airflow
- Google Cloud Composer
- Google BigQuery
- dbt
- Amazon S3
- ZenRows

**AI and Validation**

- Gemini Vision
- Pydantic
- Pillow and pillow-heif

**Deployment and Operations**

- Docker
- Google Cloud Run
- Google Secret Manager
- AWS and Google cloud credentials through managed environments

## Local Setup

Install dependencies from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configure credentials through a secret manager, cloud login, or a local
`.env` file. Never commit or share `.env` contents. The application expects a
Gemini key through `GEMINI_API_KEY` or `GOOGLE_API_KEY`, plus access to the
configured BigQuery project and S3 bucket.

For Streamlit-hosted deployments, add these values under the app's Secrets
settings using the same names. The app reads Streamlit secrets as well as
environment variables:

```toml
GEMINI_API_KEY = "..."
AWS_ACCESS_KEY_ID = "..."
AWS_SECRET_ACCESS_KEY = "..."
AWS_SESSION_TOKEN = "..." # optional
GEMINI_MODEL = "gemini-2.5-flash" # optional
```

Use Secret Manager or workload identity instead when deploying to Cloud Run.

Start the app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Open `http://localhost:8501`.

Initialize receipt tables if needed:

```powershell
.\.venv\Scripts\python.exe -m receipt_extraction.repository
```

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

## Project Structure

```text
airflow/              Scheduled ingestion and Cloud Composer deployment
config/               Restaurant sources and non-secret defaults
dbt/                  BigQuery staging and latest-price models
frontend/              Streamlit Home and receipt experiences
menu_ingestion/       ZenRows fetching, parsing, and publishing
menu_comparison/      Catalog loading and comparison logic
receipt_extraction/   Image processing, Gemini, schemas, and receipt saves
shared/               Cloud storage, BigQuery, and application settings
sql/                  BigQuery setup and transactional receipt SQL
tests/                Ingestion, extraction, comparison, and UI tests
```

## Lessons Learned

- **Freshness is a product feature.** A price comparison is only useful when
  users can trust when the data was collected.
- **Bad data is worse than missing data.** It is better to hide an uncertain
  comparison than to make a confident but incorrect savings claim.
- **AI needs a contract.** Vision models are useful for extracting messy
  screenshots, but schema validation and human review still matter.
- **Raw data should be preserved.** Keeping immutable source snapshots makes
  failures inspectable and future parser improvements possible.
- **The pipeline and the interface are connected.** Data quality decisions
  directly affect what users see and whether a recommendation is believable.

## More Information

- [`airflow/README.md`](airflow/README.md) - ingestion orchestration
- [`airflow/composer/README.md`](airflow/composer/README.md) - Cloud Composer setup
- [`frontend/README.md`](frontend/README.md) - Streamlit comparison behavior
- [`receipt_extraction/README.md`](receipt_extraction/README.md) - receipt workflow
- [`menu_comparison/README.md`](menu_comparison/README.md) - menu catalog rules
- [`INGESTION.md`](INGESTION.md) - ingestion diagnostics
