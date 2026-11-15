# Frontend

Basic Streamlit screenshot upload, JSON review, save and session summaries. See receipt_extraction/README.md for setup.

Run `python -m streamlit run frontend/app.py` from the project root.

Home displays individual menu items in a swipeable carousel with previous/next
arrows and clickable position dots. Comparable matches show green negative and
red positive differences against the other app's price. Direct delivery prices
are explicitly unavailable; unmatched items are excluded from the carousel.
Scroll down and choose a restaurant, category and meal to compare its enabled
listings in `config/sources.json` side by side, see prices, snapshot freshness
and partial-coverage notices, or open the original website.
Disabled listings are excluded. Listings without a successful snapshot remain
visible in the meal selector with an explicit “comparison unavailable” label;
the selector defaults to the first comparable meal when one exists.
Matches use reviewed source IDs/names where available, then unique exact item
names within the same restaurant (case and whitespace normalized; sizes/counts
preserved). Duplicate names, starting prices and mismatched fulfillment modes
never receive savings claims. Unmatched listings remain available for review
but are excluded from the Home carousel by default. Search and category
filters are available.
The Upload a receipt shortcut opens the existing receipt workflow.

The catalog uses one read-only BigQuery query and a 15-minute cache. Refresh saved
menus clears that cache; it never triggers scraping. Each source uses its latest
successful whole snapshot, identified by provider, store, URL, currency and
fulfillment mode. Google Application Default Credentials must have read access
to the raw menu observations and ingestion runs tables in `hackumass26`.
